"""Rebuild existing derived products in an isolated, verified replay tree.

SPI/risk/outlook have no deployed artifacts/routes in this checkout. Produce
latest-month validation artifacts locally; do not introduce a new public API.
"""
import argparse
import contextlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys

from admin_keys import parse_key
from audit_admin_perfile import ROOT, STAGE, sha
from fetch_boundaries import COUNTRY_CONFIG
import compute_ltm_baseline as ltm
import compute_spi as spi
import compute_anomaly as anomaly
import compute_risk_index as risk
import compute_outlook as outlook


def write_new(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as f:
        json.dump(content, f, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    if json.loads(path.read_text()) != content:
        raise ValueError(f'Read-back failed: {path}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--environment', required=True, choices=['local', 'production'])
    args = parser.parse_args()
    gate = json.loads((ROOT / 'docs' / f'admin-regeneration-{args.environment}.json').read_text())
    if not gate['passed']:
        raise ValueError('Base exact-equality gate required')
    base = ROOT / 'data/admin-remediation-output' / args.environment
    for mod in [ltm, spi, anomaly, outlook]:
        mod.BASE_DIR = base
    risk.__file__ = str(base / 'scripts/compute_risk_index.py')
    results = []
    for country in COUNTRY_CONFIG:
        country_dir = base / 'data/archive' / country
        files = sorted((country_dir / 'stats').glob('*.json'))
        latest = json.loads(files[-1].read_text())
        year, month = latest['year'], latest['month']
        with contextlib.redirect_stdout(io.StringIO()):
            baseline = ltm.compute_baseline(ltm.load_archive(country, 1991, 2020), 1991, 2020)
        baseline['country'] = country
        write_new(country_dir / f'{country}_ltm_1991_2020.json', baseline)
        print(f'{country}: baseline rebuilt', flush=True)
        # Local validation artifact: the deployed app currently has no SPI route/files.
        spi_result = spi.compute_spi3(country, year, month)
        write_new(country_dir / 'spi' / f'chirps-v2.0.{year}.{month:02d}_{country}_spi3.json', spi_result)
        print(f'{country}: latest SPI validation artifact rebuilt', flush=True)
        count = 0
        for path in files:
            actual = json.loads(path.read_text())
            y, m = actual['year'], actual['month']
            with contextlib.redirect_stdout(io.StringIO()):
                calculated = anomaly.compute_anomaly(actual, baseline, y, m)
            for level, areas in calculated.items():
                for key, value in areas.items():
                    parse_key(key)
                    if key not in actual['zonal_stats'][level] or value['actual'] != actual['zonal_stats'][level][key]['mean']:
                        raise ValueError(f'Anomaly/base mismatch: {country}/{path.name}/{key}')
            write_new(country_dir / 'anomaly' / f'chirps-v2.0.{y}.{m:02d}_{country}_anomaly.json',
                      {'country': country, 'year': y, 'month': m,
                       'reference_period': {'start': 1991, 'end': 2020}, 'anomaly': calculated})
            count += 1
        results.append({'country': country, 'anomaly_files': count,
                        'latest_spi_counts': {level: len(areas) for level, areas in spi_result['zonal_stats'].items()}})
        print(f'{country}: {count} anomalies rebuilt', flush=True)
    # Ghana is the only implemented population/drainage domain. Rebuild using
    # the existing WorldPop algorithm and require equality with its old values.
    population_path = ROOT / 'data/exposure/ghana_population.json'
    population = json.loads(population_path.read_text())
    boundary = json.loads((STAGE / 'ghana_districts.geojson').read_text())
    from admin_keys import feature_keys
    if set(population) != set(feature_keys(boundary['features'])):
        raise ValueError('Population boundary keys need review')
    shutil.copytree(ROOT / 'scripts', base / 'scripts', ignore=shutil.ignore_patterns('__pycache__'))
    boundary_path = base / 'data/processed/ghana_districts.geojson'
    if boundary_path.exists():
        if json.loads(boundary_path.read_text()) != boundary:
            raise ValueError('Staged Ghana boundary differs')
    else:
        write_new(boundary_path, boundary)
    subprocess.run([sys.executable, str(base / 'scripts/compute_population_exposure.py'),
                    '--country', 'ghana'], check=True)
    rebuilt_population = json.loads((base / 'data/exposure/ghana_population.json').read_text())
    if rebuilt_population != population:
        raise ValueError('Population values changed; stop before risk generation')
    infrastructure = ROOT / 'frontend/static/data/ghana_infrastructure.json'
    write_new(base / 'frontend/static/data/ghana_infrastructure.json', json.loads(infrastructure.read_text()))
    latest = json.loads(sorted((base / 'data/archive/ghana/stats').glob('*.json'))[-1].read_text())
    year, month = latest['year'], latest['month']
    risk_result = risk.compute_risk('ghana', year, month)
    write_new(base / 'data/archive/ghana/risk' / f'chirps-v2.0.{year}.{month:02d}_ghana_risk.json', risk_result)
    print('Ghana: latest risk validation artifact rebuilt', flush=True)
    outlook_result = outlook.compute_outlook('ghana', year, month)
    write_new(base / 'data/archive/ghana/outlook' / f'chirps-v2.0.{year}.{month:02d}_ghana_outlook3.json', outlook_result)
    print('Ghana: latest outlook validation artifact rebuilt', flush=True)
    write_new(ROOT / 'docs' / f'admin-derived-{args.environment}.json',
              {'passed': True, 'countries': results,
               'population': 'Ghana population regenerated with existing method; exact equality required',
               'population_sha256': sha(population_path),
               'undeployed_products': 'Latest SPI for six countries; risk/outlook Ghana only, local validation artifacts',
               'risk_count': len(risk_result['districts']), 'outlook_count': len(outlook_result['districts'])})


if __name__ == '__main__':
    main()
