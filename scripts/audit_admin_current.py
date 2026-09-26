"""Audit current map-layer JSON independently at its one-decimal precision."""
import concurrent.futures
import contextlib
import io
import json

import rasterstats
import process_rainfall as rainfall
from audit_admin_perfile import INPUTS, ROOT, STAGE, sha, assign_settings
from audit_admin_sampling import compare
from cached_admin_zonal import cached_masks, prepared_features
from fetch_boundaries import COUNTRY_CONFIG


def determine(task):
    country, path = task
    old = json.loads(path.read_text())
    tif = INPUTS / 'production-archive' / country / 'tifs' / path.with_suffix('.tif').name
    rainfall.COUNTRY_BOUNDARIES[country] = {
        level: STAGE / spec['out_name'] for level, spec in COUNTRY_CONFIG[country]['levels'].items()}
    original = rasterstats.zonal_stats
    matches, checks = [], []
    try:
        for touched in (False, True):
            def zonal(features, *args, **kwargs):
                kwargs['all_touched'] = touched
                identity = (country, features[0]['properties']['admin_level'])
                with cached_masks():
                    return original(prepared_features(identity, features), *args, **kwargs)
            rasterstats.zonal_stats = zonal
            with contextlib.redirect_stdout(io.StringIO()):
                result = rainfall.compute_zonal_stats(tif, country)
            changes = compare(old['zonal_stats'], result, country)
            if not changes:
                matches.append(touched)
            checks.append({'all_touched': touched, 'different_areas': len(changes), 'examples': changes[:2]})
    finally:
        rasterstats.zonal_stats = original
    return {'environment': 'production', 'country': country, 'file': path.name,
            'year': old['year'], 'month': old['month'], 'source_sha256': sha(path),
            'raster_sha256': sha(tif), 'matches': matches, 'checks': checks}


def main():
    target = ROOT / 'docs/admin-current-provenance.json'
    if target.exists():
        raise FileExistsError(target)
    tasks = []
    for country, cfg in COUNTRY_CONFIG.items():
        directory = INPUTS / 'production-processed' / cfg['processed_dir'].name
        tasks.extend((country, path) for path in sorted(directory.glob('chirps-*.json')))
    rows = []
    failed = False
    with concurrent.futures.ProcessPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(determine, task) for task in tasks]
        for future in concurrent.futures.as_completed(futures):
            row = future.result()
            rows.append(row)
            if not row['matches']:
                failed = True
                print('UNMATCHED ' + json.dumps(row), flush=True)
                for pending in futures:
                    pending.cancel()
                break
            if len(rows) % 20 == 0:
                print(f'{len(rows)}/{len(tasks)} current layers audited', flush=True)
    if not failed:
        assign_settings(rows)
    with target.open('x') as f:
        json.dump({'passed': not failed, 'planned_files': len(tasks), 'checked_files': len(rows),
                   'precision': 1, 'files': sorted(rows, key=lambda r: (r['country'], r['file']))}, f, indent=2)
    if failed:
        raise SystemExit('STOP: current-layer values cannot be reproduced')
    print(f'PASS {len(rows)} current layers', flush=True)


if __name__ == '__main__':
    main()
