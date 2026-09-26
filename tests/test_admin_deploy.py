"""Exercise fail-closed deployment and rollback without touching a real service."""
import hashlib
import json
from pathlib import Path
import sys
import tarfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import deploy_admin_release as deploy


@pytest.mark.parametrize('fail_start', [False, True])
def test_deploy_or_restore_verified_original(tmp_path, monkeypatch, fail_start):
    root, release, backup = [tmp_path / name for name in ('root', 'release', 'backup')]
    backup.mkdir()
    name = 'data/archive/ghana/stats/month.json'
    for base, value in ((root, 'original'), (release, 'corrected')):
        path = base / name
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({'value': value}))
    original = (root / name).read_bytes()
    with tarfile.open(backup / 'data.tar.gz', 'w:gz') as archive:
        archive.add(root / name, arcname=name)
    (backup / 'manifest.json').write_text(json.dumps({
        'verified': True, 'source_head': 'old',
        'archive_sha256': deploy.sha(backup / 'data.tar.gz'),
        'files': {name: deploy.sha(root / name)}}))
    (release / 'overlay.json').write_text(json.dumps({
        'gates_passed': True, 'source_commit': 'new',
        'backup_sha256': deploy.sha(backup / 'data.tar.gz'),
        'files': {name: deploy.sha(release / name)}}))
    commands = []
    def run(*args, **kwargs):
        commands.append(args)
        if 'rev-parse' in args:
            return 'old' if args[-1] == 'HEAD' else 'new'
        if args == ('sudo', '-n', 'systemctl', 'start', 'insightsafrica') and fail_start:
            if sum(c == args for c in commands) == 1:
                raise RuntimeError('Simulated startup failure')
        return ''
    class Response:
        headers = {'X-Administrative-Key-Version': '2'}
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self): return '{}'
    monkeypatch.setattr(deploy, 'run', run)
    monkeypatch.setattr(deploy, 'EXPECTED_FILES', 1)
    monkeypatch.setattr(deploy.urllib.request, 'urlopen', lambda *a, **k: Response())
    monkeypatch.setattr(sys, 'argv', ['deploy', '--root', str(root), '--release', str(release),
                                    '--backup', str(backup), '--commit', 'new'])
    if fail_start:
        with pytest.raises(RuntimeError, match='Simulated'):
            deploy.main()
        assert (root / name).read_bytes() == original
        assert commands[-2][-3:] == ('checkout', '--detach', 'old')
    else:
        deploy.main()
        assert (root / name).read_bytes() == (release / name).read_bytes()
    report = json.loads((release / 'deployment.json').read_text())
    assert report['passed'] is not fail_start
    assert report.get('rolled_back', False) is fail_start


def test_refuse_new_products_and_unsafe_paths():
    for name in ('../data/file.json', '/data/file.json', 'data/archive/ghana/spi/a.json',
                 'data/archive/ghana/risk/a.json', 'data/archive/ghana/outlook/a.json'):
        assert not deploy.allowed(name)
