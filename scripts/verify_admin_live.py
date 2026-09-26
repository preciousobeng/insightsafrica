"""Verify public hierarchy responses after the coordinated code/data release."""
import argparse
import csv
import io
import json
from pathlib import Path
import urllib.request

from admin_keys import feature_keys, parse_key

COUNTRIES = {
    'ghana': {'regions': 16, 'districts': 260},
    'nigeria': {'states': 37, 'lgas': 775},
    'ivorycoast': {'districts': 14, 'regions': 33},
    'senegal': {'regions': 14, 'departments': 45},
    'capeverde': {'islands': 22},
    'southafrica': {'provinces': 9, 'districts': 52},
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('base')
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    results = []

    def get(path, as_json=True):
        request = urllib.request.Request(args.base.rstrip('/') + path,
                                         headers={'Cache-Control': 'no-cache', 'User-Agent': 'InsightsAfrica-release-verification'})
        with urllib.request.urlopen(request, timeout=40) as response:
            if response.status != 200:
                raise ValueError(f'HTTP {response.status}: {path}')
            if path.startswith('/api/') and response.headers.get('X-Administrative-Key-Version') != '2':
                raise ValueError('Missing identifier version: ' + path)
            raw = response.read().decode()
            results.append({'path': path, 'status': response.status})
            return json.loads(raw) if as_json else raw

    for country, levels in COUNTRIES.items():
        prefix = '/api' if country == 'ghana' else '/api/' + country
        layers = get(prefix + '/flood/layers')
        expected_layers = 80 if country in ('capeverde', 'southafrica') else 32
        if len(layers) != expected_layers:
            raise ValueError(f'Unexpected current month count: {country}')
        for layer in layers:
            for level, count in levels.items():
                areas = layer['zonal_stats'][level]
                if len(areas) != count:
                    raise ValueError(f'Current counts: {country}/{level}')
                for key in areas:
                    parse_key(key)
        latest = max(layers, key=lambda row: (row['year'], row['month']))
        if (latest['year'], latest['month']) != (2026, 8):
            raise ValueError('Unexpected latest month: ' + country)
        for level, count in levels.items():
            boundary = get(prefix + '/boundaries/' + level)
            keys = feature_keys(boundary['features'])
            if len(keys) != count or set(keys) != set(latest['zonal_stats'][level]):
                raise ValueError(f'Boundary/stat mismatch: {country}/{level}')
        baseline = get(f'/api/{country}/flood/baseline')
        if len(baseline['months']) != 12:
            raise ValueError('Incomplete baseline')
        for levels_data in baseline['months'].values():
            for areas in levels_data.values():
                for key in areas:
                    parse_key(key)
        index = get(f'/api/{country}/flood/anomaly')['available_months']
        if len(index) != 548:
            raise ValueError('Incomplete anomaly history')
        for year, month in ((1981, 1), (2026, 8)):
            anomaly = get(f'/api/{country}/flood/anomaly/{year}/{month}')['anomaly']
            for areas in anomaly.values():
                for key in areas:
                    parse_key(key)
            if country == 'ivorycoast' and len(anomaly['regions']) != 33:
                raise ValueError('Collapsed CIV anomaly')
        fine = list(levels)[-1]
        content = get(f'/api/{country}/flood/archive/download/csv?level={fine}&from=2026-08&to=2026-08', False)
        reader = csv.DictReader(io.StringIO('\n'.join(line for line in content.splitlines() if not line.startswith('#'))))
        rows = list(reader)
        if len(rows) != len(anomaly[fine]):
            raise ValueError('CSV/anomaly row mismatch: ' + country)
        if {row['area'] for row in rows} != set(anomaly[fine]):
            raise ValueError('CSV key mismatch: ' + country)
        print(f'{country}: current layers, boundaries, baseline, archive and CSV passed', flush=True)
    current_csv = get('/api/ivorycoast/flood/download/csv?level=regions&from=2026-08&to=2026-08', False)
    reader = csv.DictReader(io.StringIO('\n'.join(line for line in current_csv.splitlines() if not line.startswith('#'))))
    if reader.fieldnames != ['year', 'month', 'period', 'area', 'level', 'mean_rainfall_mm', 'max_rainfall_mm', 'min_rainfall_mm']:
        raise ValueError('Current CSV columns changed')
    if len(list(reader)) != 33:
        raise ValueError('Current CIV CSV missing areas')
    missing = get('/api/southafrica/flood/anomaly/1982/10')['anomaly']
    if 'districts' in missing:
        raise ValueError('Out-of-scope South Africa gap changed')
    notice = get('/admin-hierarchy-v2.html', False)
    if 'May 2026' not in notice or '33' not in notice:
        raise ValueError('Version/methodology notice missing')
    for path, expected in (('/ghana', '/ghana/hub.html'), ('/flood/', '/ghana/flood/')):
        with urllib.request.urlopen(args.base.rstrip('/') + path, timeout=30) as response:
            if not response.url.endswith(expected) or response.status != 200:
                raise ValueError('Legacy redirect failed: ' + path)
            results.append({'path': path, 'final_path': expected, 'status': response.status})
    with args.output.open('x') as stream:
        json.dump({'passed': True, 'base': args.base, 'checks': results,
                   'risk': 'No deployed route; 260-district staged validation recorded separately'}, stream, indent=2)


if __name__ == '__main__':
    main()
