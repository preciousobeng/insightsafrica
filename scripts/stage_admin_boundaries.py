"""Fetch and validate new boundary files without replacing existing data."""
import hashlib
import io
import json
from pathlib import Path
import zipfile

import requests
from fetch_boundaries import COUNTRY_CONFIG, map_boundaries, validate_boundaries


def main():
    root = Path(__file__).resolve().parents[1]
    stage = root / 'data' / 'admin-remediation-stage'
    stage.mkdir(parents=True, exist_ok=False)
    evidence = []
    for country, cfg in COUNTRY_CONFIG.items():
        for level, spec in cfg['levels'].items():
            response = requests.get(spec['url'], timeout=120)
            response.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                member, = [n for n in archive.namelist() if n.endswith('.json')]
                raw = json.loads(archive.read(member))
            mapped = map_boundaries(raw, spec['level_label'], spec['admin_level'])
            keys = validate_boundaries(mapped, spec['admin_level'])
            assert len(keys) == len(raw['features'])
            assert all(a['geometry'] == b['geometry'] for a, b in zip(raw['features'], mapped['features']))
            target = stage / spec['out_name']
            target.write_text(json.dumps(mapped), encoding='utf-8')
            validate_boundaries(json.loads(target.read_text()), spec['admin_level'])
            row = {'country': country, 'level': level, 'admin_level': spec['admin_level'],
                   'count': len(keys), 'samples': keys[:3], 'url': spec['url'],
                   'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                   'types': {t: sum(f['properties']['admin_type'] == t for f in mapped['features'])
                             for t in sorted({f['properties']['admin_type'] for f in mapped['features']})}}
            evidence.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
    out = root / 'docs' / 'admin-hierarchy-gate2.json'
    with out.open('x', encoding='utf-8') as f:
        json.dump(evidence, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
