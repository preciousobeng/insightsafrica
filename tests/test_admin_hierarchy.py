"""Prevent label/depth confusion and silent loss of zonal statistics."""
import copy
import importlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.admin_keys import build_key, parse_key, feature_keys, unique_name_match
from scripts.fetch_boundaries import COUNTRY_CONFIG, map_boundaries, validate_boundaries


def feature(name1='Parent', name2='Child', kind='Région'):
    return {'type': 'Feature', 'properties': {'NAME_1': name1, 'NAME_2': name2, 'TYPE_2': kind},
            'geometry': {'type': 'Polygon', 'coordinates': [[[0, 0], [1, 0], [1, 1], [0, 0]]]}}


LAYERS = [(country, level, config) for country, cfg in COUNTRY_CONFIG.items()
          for level, config in cfg['levels'].items()]


@pytest.mark.parametrize('country,level,config', LAYERS)
def test_every_country_uses_explicit_depth(country, level, config):
    raw = {'type': 'FeatureCollection', 'features': [feature()]}
    original = copy.deepcopy(raw)
    depth = config['admin_level']
    result = map_boundaries(raw, config['level_label'], depth)
    assert raw == original
    assert result['features'][0]['geometry'] == raw['features'][0]['geometry']
    assert feature_keys(result['features']) == (['Parent'] if depth == 1 else ['Child|Parent'])
    assert f'_{depth}.json.zip' in config['url']


def test_ivorycoast_preserves_31_regions_and_two_autonomous_districts():
    features = [feature(f'District{i % 12}', f'Region{i}') for i in range(31)]
    features += [feature(name, name, 'Districtautonome') for name in ['Abidjan', 'Yamoussoukro']]
    result = map_boundaries({'features': features}, 'region', 2)
    assert len(feature_keys(result['features'])) == 33
    assert sum(f['properties']['admin_type'] == 'Région' for f in result['features']) == 31
    assert sum(f['properties']['admin_type'] == 'Districtautonome' for f in result['features']) == 2


@pytest.mark.parametrize('key', ['', '|Abidjan', 'Name|', 'A|B|C', '  ', ' Name', 'Name| '])
def test_reject_malformed_keys(key):
    with pytest.raises(ValueError):
        parse_key(key)


def test_canonical_format_and_ambiguous_parent():
    assert build_key('Abidjan') == 'Abidjan'
    assert build_key('Gbôkle', 'Bas-Sassandra') == 'Gbôkle|Bas-Sassandra'
    assert parse_key('Gbôkle|Bas-Sassandra') == ('Gbôkle', 'Bas-Sassandra')
    assert unique_name_match('Accra', ['Accra|GreaterAccra']) == 'Accra|GreaterAccra'
    assert unique_name_match('Acc', ['Accra|GreaterAccra']) is None
    with pytest.raises(ValueError):
        unique_name_match('Town', ['Town|A', 'Town|B'])
    with pytest.raises(ValueError):
        build_key('A|B')


def test_duplicate_source_and_old_boundary_rejected():
    with pytest.raises(ValueError, match='Duplicate'):
        map_boundaries({'features': [feature(), feature()]}, 'region', 2)
    with pytest.raises(ValueError, match='refresh'):
        validate_boundaries({'features': [{'properties': {'name': 'District'}}]}, 2)


@pytest.mark.parametrize('module,function', [('fetch_chirps_archive', 'compute_stats'),
                                           ('process_rainfall', 'compute_zonal_stats')])
@pytest.mark.parametrize('bad', ['empty', 'duplicate', 'none'])
def test_actual_writers_validate_before_calculation_and_keep_nulls(tmp_path, monkeypatch, module, function, bad):
    mod = importlib.import_module('scripts.' + module)
    raw = map_boundaries({'features': [feature()]}, 'region', 2)
    if bad == 'empty':
        raw['features'][0]['properties']['name'] = ''
    elif bad == 'duplicate':
        raw['features'] *= 2
    p = tmp_path / 'boundaries.json'
    p.write_text(json.dumps(raw))
    monkeypatch.setattr(mod, 'COUNTRY_BOUNDARIES', {'test': {'regions': p}})
    calls = []
    def stats(*args, **kwargs):
        calls.append(True)
        return [{'mean': None, 'max': None, 'min': None}]
    import rasterstats
    monkeypatch.setattr(rasterstats, 'zonal_stats', stats)
    if hasattr(mod, 'zonal_stats'):
        monkeypatch.setattr(mod, 'zonal_stats', stats)
    if bad != 'none':
        with pytest.raises(ValueError):
            getattr(mod, function)(tmp_path / 'unused.tif', 'test')
        assert calls == []
    else:
        result = getattr(mod, function)(tmp_path / 'unused.tif', 'test')
        assert result['regions']['Child|Parent'] == {'mean': None, 'max': None, 'min': None}


def test_risk_normalization_uses_validated_key():
    from scripts.compute_risk_index import _normalise_key
    assert _normalise_key('Accra|Greater Accra') == 'Accra|GreaterAccra'
    with pytest.raises(ValueError):
        _normalise_key('|Abidjan')


def test_risk_rejects_normalized_collision():
    from scripts.compute_risk_index import _insert_unique, _normalise_key
    result = {}
    _insert_unique(result, _normalise_key('Town|Greater Accra'), 1)
    with pytest.raises(ValueError, match='Duplicate'):
        _insert_unique(result, _normalise_key('Town|GreaterAccra'), 2)
