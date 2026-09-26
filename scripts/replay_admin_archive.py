"""Regenerate only into new staging directories from an accepted full manifest."""
import argparse
import concurrent.futures
import contextlib
import io
import json
from pathlib import Path

from admin_keys import parse_key
from audit_admin_perfile import INPUTS, ROOT, STAGE, sha
from audit_admin_sampling import compare
from fetch_boundaries import COUNTRY_CONFIG
from cached_admin_zonal import cached_masks, prepared_features
import fetch_chirps_archive as archive


def replay(row):
    environment, country, filename = row['environment'], row['country'], row['file']
    source = INPUTS / f'{environment}-archive' / country / 'stats' / filename
    tif = INPUTS / 'production-archive' / country / 'tifs' / Path(filename).with_suffix('.tif').name
    if sha(source) != row['source_sha256'] or sha(tif) != row['raster_sha256']:
        raise ValueError(f'Input changed since determination: {environment}/{country}/{filename}')
    archive.COUNTRY_BOUNDARIES[country] = {
        level: STAGE / spec['out_name'] for level, spec in COUNTRY_CONFIG[country]['levels'].items()}
    original_zonal = archive.zonal_stats
    try:
        def zonal(*args, **kwargs):
            kwargs['all_touched'] = row['selected_all_touched']
            features, *remaining = args
            identity = (country, features[0]['properties']['admin_level'])
            prepared = prepared_features(identity, features)
            with cached_masks():
                return original_zonal(prepared, *remaining, **kwargs)
        archive.zonal_stats = zonal
        with contextlib.redirect_stdout(io.StringIO()):
            calculated = archive.compute_stats(tif, country)
    finally:
        archive.zonal_stats = original_zonal
    payload = json.loads(source.read_text())
    old = payload['zonal_stats']
    # Preserve the explicitly excluded missing South Africa level; never fill gaps.
    new = {level: calculated[level] for level in old}
    changes = compare(old, new, country)
    if changes:
        raise ValueError(f'Exact equality failed: {environment}/{country}/{filename}: {changes[:2]}')
    levels = {}
    for level, areas in new.items():
        for key in areas:
            parse_key(key)
        expected_count = 33 if country == 'ivorycoast' and level == 'regions' else len(old[level])
        if len(areas) != expected_count:
            raise ValueError(f'Unexpected area count: {country}/{level}/{filename}')
        levels[level] = {'before_count': len(old[level]), 'after_count': len(areas),
                         'removed_keys': sorted(old[level].keys() - areas.keys()),
                         'added_keys': sorted(areas.keys() - old[level].keys()),
                         'protected_values_equal': not (country == 'ivorycoast' and level == 'regions')}
    payload['zonal_stats'] = new
    target = ROOT / 'data/admin-remediation-output' / environment / 'data/archive' / country / 'stats' / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('x') as f:
        json.dump(payload, f, ensure_ascii=False, separators=(',', ':'))
    if json.loads(target.read_text()) != payload:
        raise ValueError(f'Output read-back failed: {target}')
    return {'country': country, 'file': filename, 'sha256': sha(target), 'levels': levels}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--environment', required=True, choices=['local', 'production'])
    args = parser.parse_args()
    manifest_path = ROOT / 'docs/admin-perfile-provenance.json'
    manifest = json.loads(manifest_path.read_text())
    if not manifest['passed'] or manifest['completed_file_comparisons'] != manifest['planned_file_comparisons']:
        raise ValueError('Complete passing provenance manifest required')
    for name, expected in manifest['boundary_sha256'].items():
        if sha(STAGE / name) != expected:
            raise ValueError(f'Boundary changed: {name}')
    out = ROOT / 'docs' / f'admin-regeneration-{args.environment}.json'
    if out.exists():
        raise FileExistsError(out)
    rows = [r for r in manifest['files'] if r['environment'] == args.environment]
    results = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(replay, row) for row in rows]
        for index, future in enumerate(concurrent.futures.as_completed(futures), 1):
            try:
                results.append(future.result())
            except Exception:
                for pending in futures:
                    pending.cancel()
                raise
            if index % 50 == 0:
                print(f'{args.environment}: {index}/{len(rows)} regenerated, exact comparison passed', flush=True)
    with out.open('x') as f:
        json.dump({'passed': True, 'environment': args.environment, 'manifest_sha256': sha(manifest_path),
                   'files': sorted(results, key=lambda r: (r['country'], r['file']))}, f, indent=2)
    print(f'PASS {args.environment}: {len(results)} files; no original data overwritten', flush=True)


if __name__ == '__main__':
    main()
