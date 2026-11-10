"""Standalone worker adapter. Chat MCP sessions are not available to a daemon."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import uuid
from urllib.parse import urlencode, urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError('Taiga redirect refused; configure the canonical API URL')


class Taiga:
    def __init__(self, config):
        self.config = config
        self.base = config['api_url'].rstrip('/')
        parsed = urlparse(self.base)
        if parsed.scheme != 'https' and not (parsed.scheme == 'http' and parsed.hostname in {'127.0.0.1', 'localhost'}):
            raise ValueError('Taiga requires HTTPS outside localhost')
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('Credentials/query are not allowed in Taiga API URL')
        self.token = os.environ.get(config.get('token_env', 'VW_TRIAGE_TAIGA_TOKEN'), '')
        if not self.token:
            raise ValueError('Taiga token environment variable is missing')
        self.opener = build_opener(NoRedirect())
        if config.get('project_id') is not None:
            self.project = int(config['project_id'])
        else:
            slug = config.get('project_slug')
            if not isinstance(slug, str) or not slug:
                raise ValueError('Taiga project_id or project_slug is required')
            project = self.request('GET', 'projects/by_slug?' + urlencode({'slug': slug}))
            if not isinstance(project, dict) or project.get('slug') != slug:
                raise ValueError('Taiga project lookup did not match configured slug')
            self.project = int(project['id'])

    def request(self, method, path, data=None, content_type='application/json'):
        body = data if isinstance(data, bytes) else (json.dumps(data).encode() if data is not None else None)
        req = Request(self.base + '/' + path, data=body, method=method,
                      headers={'Authorization': 'Bearer ' + self.token, 'Content-Type': content_type})
        with self.opener.open(req, timeout=30) as response:
            self.response_headers = dict((k.lower(), v) for k, v in response.headers.items())
            return json.loads(response.read())

    def list(self, path, params):
        rows = []
        for page in range(1, 101):
            self.response_headers = {}
            chunk = self.request('GET', path + '?' + urlencode(dict(params, page=page, page_size=100)))
            if not isinstance(chunk, list):
                raise ValueError('Unexpected Taiga list response')
            rows.extend(chunk)
            if not chunk or self.response_headers.get('x-paginated', '').lower() == 'false':
                return rows
            if 'x-pagination-next' in self.response_headers and not self.response_headers['x-pagination-next']:
                return rows
        raise RuntimeError('Taiga pagination limit reached; refusing incomplete duplicate check')

    def submit(self, job, draft, attachments):
        tag = 'ai-triage-' + job['fingerprint']
        marker = 'triage-run:' + job['id']
        matches = self.list('issues', {'project': self.project, 'tags': tag})
        matches = [x for x in matches if not x.get('is_closed')]
        if len(matches) > 1:
            raise ValueError('Multiple matching open bugs; needs human reconciliation')
        description = draft['description'] + '\n\n' + marker
        if matches:
            issue = self.request('GET', 'issues/' + str(matches[0]['id']))
            if marker not in issue.get('description', ''):
                issue = self.request('PATCH', 'issues/' + str(issue['id']), {
                    'version': issue['version'],
                    'description': issue.get('description', '') + '\n\n---\n' + description})
        else:
            data = dict(project=self.project, subject=draft['subject'], description=description, tags=[tag])
            for field in ('status', 'priority', 'severity', 'type'):
                if field in self.config:
                    data[field] = int(self.config[field])
            # A network failure here is recoverable via the same remote tag on resume.
            issue = self.request('POST', 'issues', data)
        existing = self.list('issues/attachments', {'project': self.project, 'object_id': issue['id']})
        for path in attachments:
            path = Path(path)
            content = path.read_bytes()
            attachment_marker = marker + ':' + hashlib.sha256(content).hexdigest()
            if any(x.get('description') == attachment_marker for x in existing):
                continue
            boundary = uuid.uuid4().hex
            body = b''
            for key, value in {'project': self.project, 'object_id': issue['id'], 'description': attachment_marker}.items():
                body += ('--' + boundary + '\r\nContent-Disposition: form-data; name="' + key + '"\r\n\r\n' + str(value) + '\r\n').encode()
            body += ('--' + boundary + '\r\nContent-Disposition: form-data; name="attached_file"; filename="evidence.png"\r\nContent-Type: image/png\r\n\r\n').encode()
            body += content + ('\r\n--' + boundary + '--\r\n').encode()
            existing.append(self.request('POST', 'issues/attachments', body, 'multipart/form-data; boundary=' + boundary))
        return {'id': issue['id'], 'ref': issue['ref'], 'attachments': len(attachments)}
