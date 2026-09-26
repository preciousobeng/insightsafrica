"""Verify every protected baseline/anomaly value against the production snapshot."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def protected(levels, country):
    result = {}
    for level, values in levels.items():
        if country == 'ivorycoast' and level == 'regions':
            continue
        canonical = {key.removeprefix('|'): value for key, value in values.items()}
        if len(canonical) != len(values):
            raise ValueError('Identifier collision')
        result[level] = canonical
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--environment', choices=['local', 'production'], required=True)
    args = parser.parse_args()
    staged = ROOT / 'data/admin-remediation-output' / args.environment / 'data/archive'
    original = ROOT / 'data/admin-remediation-inputs/production-archive'
    checked = 0
    for path in sorted(staged.glob('*/*_ltm_1991_2020.json')):
        country = path.parent.name
        before = json.loads((original / path.relative_to(staged)).read_text())
        after = json.loads(path.read_text())
        if set(before['months']) != set(after['months']):
            raise ValueError('Baseline months changed')
        for month in before['months']:
            if protected(before['months'][month], country) != protected(after['months'][month], country):
                raise ValueError(f'Protected baseline changed: {country}/{month}')
        checked += 1
    for path in sorted(staged.glob('*/anomaly/*.json')):
        country = path.parents[1].name
        before = json.loads((original / path.relative_to(staged)).read_text())
        after = json.loads(path.read_text())
        if protected(before['anomaly'], country) != protected(after['anomaly'], country):
            raise ValueError(f'Protected anomaly changed: {country}/{path.name}')
        checked += 1
    expected = 3294 if args.environment == 'production' else 3270
    if checked != expected:
        raise ValueError(f'Incomplete derived inventory: {checked}/{expected}')
    report = {'passed': True, 'environment': args.environment, 'files_checked': checked,
              'comparison': 'All baseline and anomaly values exact outside corrected CIV adm2'}
    with (ROOT / 'docs' / f'admin-derived-equality-{args.environment}.json').open('x') as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps(report))


if __name__ == '__main__':
    main()
