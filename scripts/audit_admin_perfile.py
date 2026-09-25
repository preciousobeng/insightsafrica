"""Empirical per-file sampling manifest. Never writes regenerated archive data."""
import concurrent.futures
import contextlib
import hashlib
import io
import json
import platform
from pathlib import Path

from audit_admin_sampling import compare
from fetch_boundaries import COUNTRY_CONFIG
import fetch_chirps_archive as archive

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / 'data/admin-remediation-inputs'
STAGE = ROOT / 'data/admin-remediation-stage'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def determine(task):
    country, filename, sources = task
    tif = INPUTS / 'production-archive' / country / 'tifs' / Path(filename).with_suffix('.tif').name
    archive.COUNTRY_BOUNDARIES[country] = {
        level: STAGE / spec['out_name'] for level, spec in COUNTRY_CONFIG[country]['levels'].items()}
    original_zonal = archive.zonal_stats
    candidates = {}
    try:
        for touched in (False, True):
            def zonal(*args, **kwargs):
                kwargs['all_touched'] = touched
                return original_zonal(*args, **kwargs)
            archive.zonal_stats = zonal
            with contextlib.redirect_stdout(io.StringIO()):
                candidates[touched] = archive.compute_stats(tif, country)
    finally:
        archive.zonal_stats = original_zonal
    rows = []
    # Each environment is compared independently. Only raster calculation is shared.
    for environment, path_string in sources:
        path = Path(path_string)
        old = json.loads(path.read_text())
        checks = []
        matches = []
        for touched, candidate in candidates.items():
            changes = compare(old['zonal_stats'], candidate, country)
            if not changes:
                matches.append(touched)
            checks.append({'all_touched': touched, 'different_areas': len(changes), 'examples': changes[:2]})
        rows.append({'environment': environment, 'country': country, 'file': filename,
                     'year': old['year'], 'month': old['month'],
                     'source_sha256': sha(path), 'raster_sha256': sha(tif),
                     'matches': matches, 'checks': checks,
                     'source_counts': {level: len(areas) for level, areas in old['zonal_stats'].items()},
                     'source_null_means': {level: [key for key, stat in areas.items() if stat['mean'] is None]
                                           for level, areas in old['zonal_stats'].items()}})
    return rows


def assign_settings(rows):
    """For indeterminate files use nearest determinate month, earlier on a tie."""
    if any(not row['matches'] for row in rows):
        raise ValueError('Unmatched files prohibit regeneration')
    for environment in ('local', 'production'):
        for country in COUNTRY_CONFIG:
            group = sorted([r for r in rows if r['environment'] == environment and r['country'] == country],
                           key=lambda r: (r['year'], r['month']))
            known = [r for r in group if len(r['matches']) == 1]
            for row in group:
                if len(row['matches']) == 1:
                    row['selected_all_touched'] = row['matches'][0]
                    row['determination'] = 'exact_unique'
                else:
                    if not known:
                        raise ValueError(f'No determinate neighbour: {environment}/{country}')
                    index = row['year'] * 12 + row['month']
                    neighbour = min(known, key=lambda r: (abs(r['year'] * 12 + r['month'] - index), r['year'], r['month']))
                    row['selected_all_touched'] = neighbour['matches'][0]
                    row['determination'] = 'indeterminate_both_match'
                    row['neighbour_file'] = neighbour['file']


def main():
    out = ROOT / 'docs/admin-perfile-provenance.json'
    journal = ROOT / 'docs/admin-perfile-audit.jsonl'
    if out.exists() or journal.exists():
        raise FileExistsError('Per-file evidence already exists; do not overwrite it')
    tasks = {}
    for environment in ('local', 'production'):
        for country in COUNTRY_CONFIG:
            for path in sorted((INPUTS / f'{environment}-archive' / country / 'stats').glob('*.json')):
                tasks.setdefault((country, path.name), []).append((environment, str(path)))
    rows = []
    failed = False
    with journal.open('x') as log, concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(determine, (country, name, sources)): (country, name)
                   for (country, name), sources in tasks.items()}
        for index, future in enumerate(concurrent.futures.as_completed(futures), 1):
            task_rows = future.result()
            for row in task_rows:
                rows.append(row)
                log.write(json.dumps(row, ensure_ascii=False) + '\n')
            log.flush()
            if any(not row['matches'] for row in task_rows):
                print('UNMATCHED ' + json.dumps(task_rows, ensure_ascii=False), flush=True)
                failed = True
                for pending in futures:
                    pending.cancel()
                break
            if index % 25 == 0:
                print(f'Audited {index}/{len(tasks)} raster-months; {len(rows)} independent file comparisons', flush=True)
    if not failed:
        assign_settings(rows)
    transitions = []
    for environment in ('local', 'production'):
        for country in COUNTRY_CONFIG:
            group = sorted([r for r in rows if r['environment'] == environment and r['country'] == country],
                           key=lambda r: (r['year'], r['month']))
            for prior, current in zip(group, group[1:]):
                if current.get('selected_all_touched') != prior.get('selected_all_touched'):
                    transitions.append({'environment': environment, 'country': country,
                                        'first_month_new_setting': f"{current['year']}-{current['month']:02d}",
                                        'from': prior['selected_all_touched'], 'to': current['selected_all_touched']})
    result = {'passed': not failed, 'python_version': platform.python_version(),
              'scope': 'Exact mean/max/min and null equality; Côte d’Ivoire adm2 excluded; no regeneration',
              'methodology_finding': 'Production sampling changes within time series; preserved here, alignment deferred to methodology v2.',
              'boundary_sha256': {p.name: sha(p) for p in sorted(STAGE.glob('*.geojson'))},
              'planned_file_comparisons': sum(len(s) for s in tasks.values()),
              'completed_file_comparisons': len(rows), 'transitions': transitions,
              'files': sorted(rows, key=lambda r: (r['environment'], r['country'], r['file']))}
    with out.open('x') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in result.items() if k not in ('files', 'boundary_sha256')}), flush=True)
    if failed:
        raise SystemExit('STOP: unmatched file; no regeneration')


if __name__ == '__main__':
    main()
