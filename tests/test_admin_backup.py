import json
from pathlib import Path
import subprocess
import sys
import tarfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import backup_admin_data as backup


def test_backup_reads_back_every_member_and_refuses_overwrite(tmp_path, monkeypatch):
    root, dest = tmp_path / 'repo', tmp_path / 'backup'
    (root / 'data/archive/test/stats').mkdir(parents=True)
    (root / 'data/processed').mkdir()
    (root / 'data/archive/test/stats/month.json').write_text('{"mean":null}')
    (root / 'data/processed/test.geojson').write_text('{"features":[]}')
    subprocess.run(['git', 'init', '-q', str(root)], check=True)
    subprocess.run(['git', '-C', str(root), '-c', 'user.name=Test', '-c', 'user.email=test@example.com',
                    'commit', '--allow-empty', '-qm', 'fixture'], check=True)
    monkeypatch.setattr(sys, 'argv', ['backup_admin_data.py', '--root', str(root), '--destination', str(dest)])
    backup.main()
    manifest = json.loads((dest / 'manifest.json').read_text())
    assert manifest['verified'] is True
    assert len(manifest['files']) == 2
    with tarfile.open(dest / 'data.tar.gz') as archive:
        for member in archive:
            content = archive.extractfile(member).read()
            assert backup.digest(content) == manifest['files'][member.name]
            json.loads(content)
    with pytest.raises(FileExistsError):
        backup.main()
    assert (root / 'data/archive/test/stats/month.json').read_text() == '{"mean":null}'
