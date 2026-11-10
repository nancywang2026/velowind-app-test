"""Bounded, read-only evidence collection. No model-selected commands or device IO."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from .store import APP, git, redact

MAX_FILE = 1_000_000
MAX_SNAPSHOT = 12_000_000


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def allowed_path(name):
    path = Path(name)
    return (not path.is_absolute() and '..' not in path.parts and name.startswith(APP + '/')
            and path.suffix in {'.py', '.md', '.yaml', '.yml'})


def capture_sources(repo):
    """Capture before execution, including dirty/untracked automation (never private configs)."""
    root = Path(repo).resolve()
    files, missing, total = {}, [], 0
    for folder in ['velowind_appium', 'tests', 'docs/test-fixes']:
        for path in sorted((root / APP / folder).rglob('*')):
            name = str(path.relative_to(root))
            if not allowed_path(name) or not path.is_file():
                continue
            if path.is_symlink() or not path.resolve().is_relative_to(root):
                missing.append(name + ': symlink rejected')
                continue
            if path.stat().st_size > MAX_FILE or total + path.stat().st_size > MAX_SNAPSHOT:
                missing.append(name + ': snapshot budget exceeded')
                continue
            raw = path.read_text(encoding='utf-8')
            content = redact(raw)
            files[name] = {'content': content, 'sha256': digest(content), 'original_sha256': digest(raw)}
            total += len(raw.encode())
    return {'files': files, 'missing': missing, 'kind': 'test-session-start'}


def has_blockers(diagnosis):
    # Old decisions remain conservative; a string uncertainty has no blocking classification.
    return any(isinstance(x, str) or x.get('blocking', True) for x in diagnosis.get('uncertainties', []))


class Evidence:
    def __init__(self, repo, directory, job, config, source=None):
        self.repo, self.directory = Path(repo).resolve(), Path(directory).resolve()
        self.payload, self.config = job['payload'], config
        self.source = Path(source).resolve() if source is not None else None
        self.limit = max(4000, min(int(config.get('context_chars', 100000)), 200000))
        self.used = 0
        self.items, self.seen = [], set()
        self.images = []
        self.cache = {}
        manifest = self.directory / 'source-snapshot.json'
        self.snapshot = json.loads(manifest.read_text()) if manifest.is_file() and not manifest.is_symlink() else None

    def read(self, name):
        if not allowed_path(name):
            raise ValueError('Path outside allowed automation sources')
        if name in self.cache:
            return self.cache[name]
        if self.source is not None:
            path = (self.source / name).resolve()
            if not path.is_relative_to(self.source) or not path.is_file() or path.stat().st_size > MAX_FILE:
                raise ValueError('Invalid repair source')
            text, version = path.read_text(), 'repair-worktree'
        elif self.snapshot is not None:
            entry = self.snapshot['files'].get(name)
            if not entry or digest(entry['content']) != entry['sha256']:
                raise ValueError('Unavailable or changed failure snapshot')
            text, version = entry['content'], self.snapshot.get('kind', 'unknown-snapshot')
        else:
            # Historical dirty jobs have no exact runtime source. Never substitute HEAD.
            if self.payload.get('dirty') or self.payload.get('source_changed_during_run'):
                raise ValueError('Historical dirty runtime source unavailable; no snapshot')
            text = git(self.repo, 'show', self.payload['commit'] + ':' + name)
            version = 'commit:' + self.payload['commit']
        if len(text.encode()) > MAX_FILE:
            raise ValueError('Source file exceeds budget')
        self.cache[name] = (text, version)
        return text, version

    def add(self, key, kind, content=None, **meta):
        if key in self.seen:
            return False
        self.seen.add(key)
        record = dict(id=key, kind=kind, **meta)
        if content is not None:
            content = redact(content)
            record['sha256'] = digest(content)
            if self.used + len(content) > self.limit:
                record.update(status='unavailable', reason='Context budget exceeded; content not silently truncated')
            else:
                record.update(status='obtained', content=content)
                self.used += len(content)
        self.items.append(record)
        return record.get('status') == 'obtained'

    def file(self, name, symbol='', line=None, depth=0):
        key = name + (':' + symbol if symbol else ':' + str(line) if line else '')
        if key in self.seen:
            return False
        try:
            text, version = self.read(name)
            if not name.endswith('.py'):
                return self.add(key, 'document', text, path=name, version=version)
            tree = ast.parse(text)
            functions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
            matches = [n for n in functions if (n.name == symbol if symbol else line and n.lineno <= line <= n.end_lineno)]
            if not matches:
                if symbol or line:
                    raise ValueError('Symbol/line not available in this source version')
                return self.add(key, 'source', text, path=name, version=version, start=1, end=len(text.splitlines()))
            node = min(matches, key=lambda n: n.end_lineno - n.lineno)
            key = name + ':' + node.name
            start = min([node.lineno] + [d.lineno for d in getattr(node, 'decorator_list', [])])
            content = '\n'.join(text.splitlines()[start - 1:node.end_lineno])
            obtained = self.add(key, 'source_function', content, path=name, symbol=node.name,
                                start=start, end=node.end_lineno, version=version, file_sha256=digest(text))
            if obtained and depth < 2:
                calls = list(dict.fromkeys(ast.unparse(n.func) for n in ast.walk(node) if isinstance(n, ast.Call)))
                local = {n.name for n in functions}
                imports = {}
                for n in ast.walk(tree):
                    if isinstance(n, ast.ImportFrom):
                        base = name.rsplit('/', 1)[0] if n.level else APP
                        if n.level:
                            for _ in range(n.level - 1):
                                base = base.rsplit('/', 1)[0]
                        module = (n.module or '').replace('.', '/')
                        for alias in n.names:
                            imports[alias.asname or alias.name] = (base + '/' + module + '.py', alias.name)
                            if not module:
                                imports[alias.asname or alias.name] = (base + '/' + alias.name + '.py', '')
                    elif isinstance(n, ast.Import):
                        for alias in n.names:
                            imports[alias.asname or alias.name] = (APP + '/' + alias.name.replace('.', '/') + '.py', '')
                for call in calls[:24]:
                    if call in local:
                        self.file(name, call, depth=depth + 1)
                    elif call.split('.')[0] in imports:
                        path, imported = imports[call.split('.')[0]]
                        target = call.split('.')[-1] if '.' in call else imported
                        if imported and '.' in call:
                            # `from package import module` may refer to a submodule.
                            submodule = path[:-3] + '/' + imported + '.py'
                            try:
                                self.read(submodule)
                                path = submodule
                            except Exception:
                                pass
                        if allowed_path(path):
                            self.file(path, target, depth=depth + 1)
                # Preserve module imports/constants, without copying unrelated large functions.
                prelude = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom, ast.Assign, ast.AnnAssign))]
                segments = [ast.get_source_segment(text, n) or '' for n in prelude]
                self.add(name + ':module-context', 'source_constants', '\n'.join(segments), path=name, version=version)
            return obtained
        except Exception as error:
            return self.add(key, 'source', status='unavailable', path=name, reason=redact(str(error))[:300])

    def artifact(self, kind):
        key = 'failure-' + kind.lower()
        if key in self.seen:
            return False
        try:
            path = Path(self.payload.get('artifacts', {})[kind]).resolve()
            if not path.is_relative_to(self.directory) or not path.is_file() or path.stat().st_size > 2_000_000:
                raise ValueError('Artifact outside job or exceeds budget')
            if kind == 'XML':
                raw = path.read_text()
                if '<!DOCTYPE' in raw or '<!ENTITY' in raw:
                    raise ValueError('XML declarations rejected')
                root = ET.fromstring(raw)
                rows = []
                # Keep ancestry, sibling order and bounds; drop uncontrolled user/credential fields.
                allowed = {'type', 'class', 'resource-id', 'package', 'name', 'label', 'value', 'text', 'content-desc',
                           'bounds', 'x', 'y', 'width', 'height', 'visible', 'displayed', 'enabled', 'selected', 'clickable', 'index'}
                def visit(node, parent=None):
                    index = len(rows)
                    attrs = {k: redact(v) for k, v in node.attrib.items() if k in allowed}
                    marker = ' '.join(str(node.attrib.get(k, '')) for k in ['resource-id', 'type', 'class', 'name'])
                    sensitive = node.attrib.get('password') == 'true' or re.search(r'(?i)password|token|secret|edittext|textfield|comment.*(?:body|content)|message.*(?:body|content)', marker)
                    if sensitive:
                        for k in {'text', 'value', 'label', 'content-desc'} & attrs.keys():
                            attrs[k] = '[PRIVATE_CONTENT]'
                    rows.append({'node': index, 'parent': parent, 'tag': node.tag, 'attributes': attrs})
                    for child in node:
                        visit(child, index)
                visit(root)
                node_count = len(rows)
                xml_budget = min(40000, self.limit // 2)
                encoded = json.dumps(rows, ensure_ascii=False)
                if len(encoded) > xml_budget:
                    # Target/selected nodes plus their ancestors and adjacent siblings first.
                    tokens = set(re.findall(r'[a-z]{4,}', self.payload.get('error', '').lower().replace('_', ' ')))
                    focus = []
                    for row in rows:
                        attrs = row['attributes']
                        values = ' '.join(attrs.values()).lower()
                        if attrs.get('selected') == 'true' or any(t in values for t in tokens):
                            focus.append(row['node'])
                    preferred = set()
                    for index in focus:
                        parent = rows[index]['parent']
                        preferred.add(index)
                        preferred.update(r['node'] for r in rows if r['parent'] == parent)
                        while parent is not None:
                            preferred.add(parent)
                            parent = rows[parent]['parent']
                    chosen, used = {}, 2
                    for index in list(dict.fromkeys(focus + sorted(preferred) + [r['node'] for r in rows])):
                        if index in chosen:
                            continue
                        family = []
                        cursor = index
                        while cursor is not None and cursor not in chosen:
                            family.append(cursor)
                            cursor = rows[cursor]['parent']
                        size = sum(len(json.dumps(rows[i], ensure_ascii=False)) + 2 for i in family)
                        if used + size <= xml_budget:
                            chosen.update((i, rows[i]) for i in family)
                            used += size
                    rows = [chosen[i] for i in sorted(chosen)]
                    encoded = json.dumps(rows, ensure_ascii=False)
                return self.add(key, 'failure_xml', encoded,
                                version='captured-failure', original_sha256=digest(raw), nodes=node_count,
                                omitted_nodes=node_count - len(rows), selection='target/selected nodes, ancestry and siblings then remaining nodes')
            if kind == 'PNG':
                review_path = self.directory / 'reviewed-evidence.json'
                if not review_path.is_file() or review_path.is_symlink():
                    raise ValueError('Screenshot not privacy/relevance reviewed; XML remains available')
                review = json.loads(review_path.read_text())
                for entry in review.get('screenshots', []):
                    candidate = Path(entry['path']).resolve()
                    if (candidate.is_relative_to(self.directory) and candidate.suffix.lower() == '.png'
                            and candidate.is_file() and candidate.stat().st_size <= 10_000_000
                            and entry.get('privacy_reviewed') is True and entry.get('related') is True
                            and hashlib.sha256(candidate.read_bytes()).hexdigest() == entry.get('sha256')):
                        from PIL import Image
                        with Image.open(candidate) as img:
                            if img.format != 'PNG':
                                continue
                            img.verify()
                        self.images.append(str(candidate))
                if not self.images:
                    raise ValueError('No valid reviewed image; XML remains available')
                return self.add(key, 'failure_image', status='obtained', image_paths=self.images[:],
                                version='reviewed-captured-failure')
            raise ValueError('Unsupported artifact')
        except Exception as error:
            return self.add(key, 'artifact', status='unavailable', reason=redact(str(error))[:300])

    def initial(self):
        payload = self.payload
        self.artifact('XML')
        self.artifact('PNG')
        # Innermost stack frames first. AST selects the complete function at each line.
        frames = re.findall(r'(apps/velowind-app/appium/[\w./-]+\.py)[\"\']?(?::|, line )(\d+)', payload['error'])
        for name, line in reversed(list(dict.fromkeys(frames))):
            self.file(name, line=int(line))
        name, _, function = payload['nodeid'].partition('::')
        self.file(name, symbol=function.split('[')[0] if function else '')
        # Related test data and history chosen by the test/error and the history index, not a canned answer.
        try:
            text, _ = self.read(name)
            tokens = set(re.findall(r'[a-zA-Z][a-zA-Z_]{3,}', (name + ' ' + payload['error']).replace('_', ' ')))
            for data in re.findall(r'[\w./-]+\.ya?ml', text):
                if not data.startswith(APP):
                    data = name.rsplit('/', 1)[0] + '/' + data
                self.file(data)
        except Exception:
            tokens = set(re.findall(r'[a-zA-Z][a-zA-Z_]{3,}', name))
        # Locate adjacent YAML fixtures in the captured snapshot or clean commit tree.
        names = list(self.snapshot['files']) if self.snapshot else []
        if not names and not payload.get('dirty'):
            try:
                names = git(self.repo, 'ls-tree', '-r', '--name-only', payload['commit'], '--', APP).splitlines()
            except Exception:
                pass
        for data in names:
            if data.endswith(('.yaml', '.yml')) and '/testdata/' in data and any(t in data for t in tokens):
                self.file(data)
        index = APP + '/docs/test-fixes/README.md'
        try:
            # Historical old jobs may use present documentation, explicitly marked as supplemental.
            text, version = self.read(index)
        except Exception:
            path = self.repo / index
            text = path.read_text() if path.is_file() and path.resolve().is_relative_to(self.repo / APP / 'docs/test-fixes') and path.stat().st_size <= MAX_FILE else ''
            version = 'current-history-supplement; not runtime source'
        self.add('history-index', 'history', text, path=index, version=version)
        ranked = []
        query = (name + ' ' + payload['error']).lower().replace('_', ' ')
        for row in text.splitlines():
            links = re.findall(r'\]\(([^)#]+\.md)(?:#[^)]*)?\)', row)
            score = sum(len(t) for t in set(re.findall(r'[a-z]{4,}|[\u4e00-\u9fff]{2,}', row.lower().replace('-', ' '))) if t in query)
            if payload.get('platform', '') in row.lower():
                score += 15
            if score:
                ranked.extend((score, link) for link in links)
        for _, link in sorted(ranked, reverse=True)[:3]:
            self.history(APP + '/docs/test-fixes/' + link)
        for name in self.config.get('context_files', [])[:12]:
            self.file(name)
        context = self.directory / 'reviewed-context.json'
        if context.is_file() and not context.is_symlink() and context.stat().st_size <= 30000:
            self.add('reviewed-context', 'reviewed_context', context.read_text(), version='local-review')
        return self.context()

    def history(self, path):
        if not path.startswith(APP + '/docs/test-fixes/') or not allowed_path(path) or not path.endswith('.md'):
            return self.add(path, 'history', status='rejected', reason='History outside allowed directory')
        try:
            text, version = self.read(path)
        except Exception:
            local = (self.repo / path).resolve()
            if not local.is_relative_to(self.repo / APP / 'docs/test-fixes') or not local.is_file() or local.stat().st_size > MAX_FILE:
                return self.add(path, 'history', status='unavailable', reason='History not available')
            text, version = local.read_text(), 'current-history-supplement; not runtime source'
        return self.add(path, 'history', text, path=path, version=version)

    def request(self, request):
        kind = request.get('kind')
        if kind == 'source_function':
            if not request.get('symbol'):
                return self.add(json.dumps(request, sort_keys=True), 'request', status='rejected', reason='Function symbol required')
            if request.get('version') != 'failure':
                return self.add(json.dumps(request, sort_keys=True), 'request', status='rejected', reason='Only failure snapshot allowed')
            return self.file(request.get('path', ''), request.get('symbol', ''))
        if kind == 'history':
            return self.history(request.get('path', ''))
        if kind == 'test_data':
            path = request.get('path', '')
            if '/testdata/' in path and path.endswith(('.yaml', '.yml')):
                return self.file(path)
        if kind in {'failure_xml', 'failure_image'}:
            return self.artifact('XML' if kind == 'failure_xml' else 'PNG')
        return self.add(json.dumps(request, sort_keys=True), 'request', status='rejected', reason='Unsupported request; no commands or device operations')

    def context(self):
        return {'failure': {k: v for k, v in self.payload.items() if k != 'artifacts'},
                'evidence': self.items, 'reviewed_images': self.images,
                'source_notice': 'Runtime source requires session snapshot or clean commit. Current history is supplemental only.',
                'budget': {'used_chars': self.used, 'limit_chars': self.limit},
                'snapshot_missing': self.snapshot.get('missing', []) if self.snapshot else ['No session snapshot; clean commit fallback only']}
