import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import replay_admin_archive as replay


@pytest.mark.parametrize('changed', [False, True])
def test_staged_replay_preserves_original_and_rejects_statistic_change(tmp_path, monkeypatch, changed):
    monkeypatch.setattr(replay, 'ROOT', tmp_path)
    inputs = tmp_path / 'inputs'
    monkeypatch.setattr(replay, 'INPUTS', inputs)
    source = inputs / 'local-archive/capeverde/stats/chirps-v2.0.2026.04_capeverde.json'
    source.parent.mkdir(parents=True)
    old = {'country': 'capeverde', 'year': 2026, 'month': 4,
           'zonal_stats': {'islands': {'|BoaVista': {'mean': None, 'min': None, 'max': None}}}}
    source.write_text(json.dumps(old))
    original = source.read_bytes()
    tif = inputs / 'production-archive/capeverde/tifs' / source.with_suffix('.tif').name
    tif.parent.mkdir(parents=True)
    tif.write_bytes(b'test raster stand-in')
    row = {'environment': 'local', 'country': 'capeverde', 'file': source.name,
           'selected_all_touched': False, 'source_sha256': replay.sha(source), 'raster_sha256': replay.sha(tif)}
    result = {'islands': {'BoaVista': {'mean': 0 if changed else None, 'min': None, 'max': None}}}
    monkeypatch.setattr(replay.archive, 'compute_stats', lambda *_: result)
    output = tmp_path / 'data/admin-remediation-output/local/data/archive/capeverde/stats' / source.name
    if changed:
        with pytest.raises(ValueError, match='Exact equality'):
            replay.replay(row)
        assert not output.exists()
    else:
        replay.replay(row)
        assert json.loads(output.read_text())['zonal_stats'] == result
        with pytest.raises(FileExistsError):
            replay.replay(row)
    assert source.read_bytes() == original
