"""Local-only Phase 3 preflight; fail closed on any protected-value change."""
import contextlib
import io
import json
from pathlib import Path

from fetch_boundaries import COUNTRY_CONFIG
from fetch_chirps_archive import COUNTRY_BOUNDARIES, compute_stats


def main():
    root = Path(__file__).resolve().parents[1]
    inputs = root / 'data/admin-remediation-inputs'
    stage = root / 'data/admin-remediation-stage'
    out = root / 'docs/admin-hierarchy-gate3-preflight.json'
    if out.exists():
        raise FileExistsError(out)
    results = []
    for country, level in [('capeverde', 'islands'), ('ivorycoast', 'districts'), ('southafrica', 'provinces')]:
        COUNTRY_BOUNDARIES[country] = {
            name: stage / spec['out_name'] for name, spec in COUNTRY_CONFIG[country]['levels'].items()}
        original = inputs / 'local-archive' / country / 'stats' / f'chirps-v2.0.2026.04_{country}.json'
        tif = inputs / 'production-archive' / country / 'tifs' / f'chirps-v2.0.2026.04_{country}.tif'
        before = json.loads(original.read_text())['zonal_stats']
        with contextlib.redirect_stdout(io.StringIO()):
            after = compute_stats(tif, country)
        expected = {k.removeprefix('|'): v for k, v in before[level].items()}
        changes = [{'key': key, 'before': expected.get(key), 'after': after[level].get(key)}
                   for key in sorted(expected.keys() | after[level].keys()) if expected.get(key) != after[level].get(key)]
        row = {'country': country, 'month': '2026-04', 'protected_level': level,
               'before_count': len(expected), 'after_count': len(after[level]),
               'changes': changes, 'all_level_counts': {k: len(v) for k, v in after.items()}}
        results.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
        if changes:
            out.write_text(json.dumps({'passed': False, 'results': results}, indent=2, ensure_ascii=False))
            raise SystemExit('STOP: protected statistics changed; no archive output was written')
    out.write_text(json.dumps({'passed': True, 'results': results}, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
