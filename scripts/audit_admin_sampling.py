"""Read-only sampling determination against separate local/production snapshots.

Compare stored mean/max/min exactly, excluding only the corrupted CIV second
level. Missing levels (including South Africa October 1982) stay excluded.
This audit never writes regenerated statistics or changes sampling defaults.
"""
import argparse
import contextlib
import io
import json
from pathlib import Path

import fetch_chirps_archive as archive
from fetch_boundaries import COUNTRY_CONFIG


def compare(before, after, country):
    differences = []
    for level, areas in before.items():
        if country == 'ivorycoast' and level == 'regions':
            continue
        expected = {key.removeprefix('|'): val for key, val in areas.items()}
        actual = after.get(level, {})
        for key in sorted(expected.keys() | actual.keys()):
            if expected.get(key) != actual.get(key):
                differences.append({'level': level, 'key': key,
                                    'before': expected.get(key), 'after': actual.get(key)})
    return differences


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--full', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    inputs = root / 'data/admin-remediation-inputs'
    stage = root / 'data/admin-remediation-stage'
    output = root / 'docs' / ('admin-sampling-full.json' if args.full else 'admin-sampling-determination.json')
    if output.exists():
        raise FileExistsError(output)
    original_zonal = archive.zonal_stats
    results = []
    all_passed = True
    for environment in ['local', 'production']:
        for country, cfg in COUNTRY_CONFIG.items():
            files = sorted((inputs / f'{environment}-archive' / country / 'stats').glob('*.json'))
            if not files:
                raise RuntimeError(f'No files for {environment}/{country}')
            # Check April and the newest month first, before the historical run.
            anchors = [p for p in files if '.2026.04_' in p.name] + [files[-1], files[0]]
            order = list(dict.fromkeys(anchors + (files if args.full else [])))
            archive.COUNTRY_BOUNDARIES[country] = {
                level: stage / spec['out_name'] for level, spec in cfg['levels'].items()}
            evidence = []
            common = {False, True}
            for path in order:
                old = json.loads(path.read_text())
                tif = inputs / 'production-archive' / country / 'tifs' / path.with_suffix('.tif').name
                if not tif.exists():
                    raise FileNotFoundError(tif)
                matches = []
                checks = []
                for touched in [False, True]:
                    def zonal(*a, **kw):
                        kw['all_touched'] = touched
                        return original_zonal(*a, **kw)
                    archive.zonal_stats = zonal
                    with contextlib.redirect_stdout(io.StringIO()):
                        new = archive.compute_stats(tif, country)
                    changes = compare(old['zonal_stats'], new, country)
                    if not changes:
                        matches.append(touched)
                    checks.append({'all_touched': touched, 'different_areas': len(changes),
                                   'examples': changes[:2]})
                common &= set(matches)
                evidence.append({'file': path.name, 'matches': matches, 'checks': checks})
                if not common:
                    all_passed = False
                    break
                if args.full and len(evidence) % 50 == 0:
                    print(f'{environment}/{country}: {len(evidence)}/{len(files)} checked', flush=True)
            row = {'environment': environment, 'country': country, 'archive_files': len(files),
                   'checked_files': len(evidence), 'common_settings': sorted(common),
                   'passed': len(common) == 1, 'evidence': evidence}
            results.append(row)
            all_passed &= row['passed']
            print(json.dumps({k: v for k, v in row.items() if k != 'evidence'}), flush=True)
            if args.full and not row['passed']:
                break
        if args.full and not all_passed:
            break
    with output.open('x') as f:
        json.dump({'full_audit': args.full, 'passed': all_passed, 'results': results}, f, indent=2)
    if not all_passed:
        raise SystemExit('STOP: no single empirically matching setting; no regeneration performed')


if __name__ == '__main__':
    main()
