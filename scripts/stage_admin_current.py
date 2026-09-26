"""Stage corrected boundaries/current layers without modifying served files."""
import argparse
import contextlib
import io
import json

import rasterstats
import process_rainfall as rainfall
from admin_keys import feature_keys
from audit_admin_perfile import INPUTS, ROOT, STAGE, sha
from audit_admin_sampling import compare
from cached_admin_zonal import cached_masks, prepared_features
from derive_admin_replay import write_new
from fetch_boundaries import COUNTRY_CONFIG


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--environment', required=True, choices=['local', 'production'])
    args = parser.parse_args()
    manifest = json.loads((ROOT / 'docs/admin-current-provenance.json').read_text())
    if not manifest['passed'] or manifest['checked_files'] != manifest['planned_files']:
        raise ValueError('Complete current-layer determination required')
    base = ROOT / 'data/admin-remediation-output' / args.environment
    original_zonal = rasterstats.zonal_stats
    evidence = []
    for country, cfg in COUNTRY_CONFIG.items():
        directory = base / 'data' / cfg['processed_dir'].name
        for level, spec in cfg['levels'].items():
            source = STAGE / spec['out_name']
            write_new(directory / spec['out_name'], json.loads(source.read_text()))
        latest = json.loads(sorted((base / 'data/archive' / country / 'stats').glob('*.json'))[-1].read_text())
        limit = (latest['year'], latest['month'])
        rainfall.COUNTRY_BOUNDARIES[country] = {level: STAGE / spec['out_name'] for level, spec in cfg['levels'].items()}
        rows = [r for r in manifest['files'] if r['country'] == country and (r['year'], r['month']) <= limit]
        for row in rows:
            source = INPUTS / 'production-processed' / cfg['processed_dir'].name / row['file']
            tif = INPUTS / 'production-archive' / country / 'tifs' / source.with_suffix('.tif').name
            if sha(source) != row['source_sha256'] or sha(tif) != row['raster_sha256']:
                raise ValueError('Current-layer input changed since audit')
            old = json.loads(source.read_text())
            def zonal(features, *a, **kw):
                kw['all_touched'] = row['selected_all_touched']
                identity = (country, features[0]['properties']['admin_level'])
                with cached_masks():
                    return original_zonal(prepared_features(identity, features), *a, **kw)
            rasterstats.zonal_stats = zonal
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    new = rainfall.compute_zonal_stats(tif, country)
            finally:
                rasterstats.zonal_stats = original_zonal
            if compare(old['zonal_stats'], new, country):
                raise ValueError(f'Current-layer exact equality failed: {country}/{row["file"]}')
            for level, values in new.items():
                geo = json.loads((directory / cfg['levels'][level]['out_name']).read_text())
                if set(values) != set(feature_keys(geo['features'])):
                    raise ValueError('Boundary/statistic keys do not match')
            old['zonal_stats'] = new
            target = directory / row['file']
            write_new(target, old)
            evidence.append({'country': country, 'file': row['file'], 'sha256': sha(target),
                             'all_touched': row['selected_all_touched']})
        print(f'{country}: {len(rows)} current layers staged and verified', flush=True)
    write_new(ROOT / 'docs' / f'admin-current-replay-{args.environment}.json',
              {'passed': True, 'environment': args.environment, 'files': evidence})


if __name__ == '__main__':
    main()
