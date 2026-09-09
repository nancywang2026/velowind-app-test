"""Persist comparable case/step durations, including imports from older Allure runs."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def write_report(report: dict, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    json_temp = output / 'timings.json.tmp'
    json_temp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    json_temp.replace(output / 'timings.json')
    csv_temp = output / 'timings.csv.tmp'
    with csv_temp.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['case', 'kind', 'name', 'status', 'duration_seconds', 'depth'])
        for case in report['cases']:
            writer.writerow([case['name'], 'case', case['nodeid'], case['status'], case.get('total_seconds'), 0])
            for phase, data in case.get('phases', {}).items():
                writer.writerow([case['name'], 'phase', phase, data['status'], data['duration_seconds'], 0])
            for step in case['steps']:
                writer.writerow([case['name'], step.get('kind', 'step'), step['name'], step['status'], step['duration_seconds'], step.get('depth', 0)])
        for fixture in report.get('fixtures', []):
            writer.writerow([' | '.join(fixture['cases']), fixture['kind'], fixture['name'], fixture['status'], fixture['duration_seconds'], 0])
    csv_temp.replace(output / 'timings.csv')


def import_allure(results: Path) -> dict:
    cases = []
    names = {}
    for path in results.glob('*-result.json'):
        data = json.loads(path.read_text(encoding='utf-8'))
        names[data.get('uuid', path.stem)] = data['name']
        steps = []
        def visit(items, depth=0):
            for step in items:
                steps.append({'name': step['name'], 'status': step.get('status', 'unknown'),
                              'duration_seconds': (step['stop'] - step['start']) / 1000,
                              'depth': depth, 'kind': 'step'})
                visit(step.get('steps', []), depth + 1)
        visit(data.get('steps', []))
        cases.append({'name': data['name'], 'nodeid': data.get('fullName', data['name']),
                      'status': data.get('status', 'unknown'), 'start_ms': data['start'],
                      'total_seconds': None,
                      'phases': {'call': {'status': data.get('status', 'unknown'),
                                          'duration_seconds': (data['stop'] - data['start']) / 1000}},
                      'steps': steps})
    cases.sort(key=lambda case: case['start_ms'])
    fixtures = []
    for path in results.glob('*-container.json'):
        container = json.loads(path.read_text(encoding='utf-8'))
        for phase in ('befores', 'afters'):
            for fixture in container.get(phase, []):
                fixtures.append({'name': fixture['name'], 'kind': f'fixture_{phase}',
                                 'status': fixture.get('status', 'unknown'),
                                 'duration_seconds': (fixture['stop'] - fixture['start']) / 1000,
                                 'cases': [names[child] for child in container.get('children', []) if child in names]})
    environment = results / 'environment.properties'
    return {'schema_version': 1, 'source': str(results), 'measurement': 'allure_wall_clock_ms',
            'limitations': 'Historical Allure call and step times only; setup/teardown and total are unavailable. Nested steps overlap their parents.',
            'environment': environment.read_text(encoding='utf-8') if environment.exists() else '',
            'cases': cases, 'fixtures': fixtures}


def compare_reports(baseline: dict, candidate: dict) -> list[dict]:
    if baseline['measurement'] != candidate['measurement']:
        raise ValueError('Compare runs with the same measurement source (e.g. both imported from Allure).')
    def index(report):
        cases = {}
        for case in report['cases']:
            key = (case['nodeid'], case['name'])
            if key in cases:
                raise ValueError(f'Duplicate case/attempt: {key}; compare individual attempts.')
            cases[key] = case
        return cases
    before, after = index(baseline), index(candidate)
    rows = []
    for key in dict.fromkeys([*before, *after]):
        left, right = before.get(key), after.get(key)
        pairs = [('call', left.get('phases', {}).get('call') if left else None,
                  right.get('phases', {}).get('call') if right else None)]
        # Match repeated step names by occurrence, not just their label.
        def steps(case):
            found, counts = {}, {}
            for step in case['steps'] if case else []:
                name = (step.get('kind', 'step'), step['name'], step.get('depth', 0))
                counts[name] = counts.get(name, 0) + 1
                found[(*name, counts[name])] = step
            return found
        old_steps, new_steps = steps(left), steps(right)
        for step_key in dict.fromkeys([*old_steps, *new_steps]):
            pairs.append((f'{step_key[0]}:{step_key[1]} [depth={step_key[2]}, occurrence={step_key[3]}]',
                          old_steps.get(step_key), new_steps.get(step_key)))
        for name, old, new in pairs:
            old_time = old.get('duration_seconds') if old else None
            new_time = new.get('duration_seconds') if new else None
            eligible = bool(left and right and left['status'] == right['status'] == 'passed'
                            and old and new and old['status'] == new['status'] == 'passed'
                            and old_time is not None and new_time is not None and old_time > 0)
            rows.append({'case': key[1], 'nodeid': key[0], 'metric': name,
                         'baseline_status': left['status'] if left else 'missing',
                         'candidate_status': right['status'] if right else 'missing',
                         'baseline_seconds': old_time, 'candidate_seconds': new_time,
                         'comparable': eligible,
                         'saved_seconds': old_time - new_time if eligible else None,
                         'improvement_percent': (old_time - new_time) / old_time * 100 if eligible else None})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--allure-results', type=Path)
    source.add_argument('--baseline', type=Path)
    parser.add_argument('--candidate', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.allure_results:
        write_report(import_allure(args.allure_results), args.output)
    else:
        if not args.candidate:
            parser.error('--baseline requires --candidate')
        rows = compare_reports(json.loads(args.baseline.read_text()), json.loads(args.candidate.read_text()))
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / 'comparison.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        with (args.output / 'comparison.csv').open('w', encoding='utf-8-sig', newline='') as stream:
            if rows:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)


if __name__ == '__main__':
    main()
