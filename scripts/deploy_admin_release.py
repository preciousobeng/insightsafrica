"""Deploy a fully verified hierarchy overlay, with automatic rollback on failure.

Run on the production host only after the separate replay gates pass. The release
directory contains overlay.json and files under data/. All overlay paths must
already exist in the independently verified backup. New product types are refused.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import time
import urllib.request

EXPECTED_FILES = 6882

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(*args, **kwargs):
    return subprocess.check_output(args, text=True, **kwargs).strip()


def atomic_write(path, content):
    mode = path.stat().st_mode & 0o777
    fd, temporary = tempfile.mkstemp(prefix='.admin-release-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def allowed(name):
    p = Path(name)
    if p.is_absolute() or '..' in p.parts or len(p.parts) < 3:
        return False
    if p.parts[0] != 'data':
        return False
    if p.parts[1] == 'archive':
        return (len(p.parts) == 5 and p.parts[3] in ('stats', 'anomaly') and p.suffix == '.json') or (
            len(p.parts) == 4 and p.name.endswith('_ltm_1991_2020.json'))
    if p.parts[1].startswith('processed') and len(p.parts) == 3:
        return p.suffix == '.geojson' or (p.name.startswith('chirps-') and p.suffix == '.json')
    return name == 'data/exposure/ghana_population.json'


def main():
    parser = argparse.ArgumentParser()
    for name in ('root', 'release', 'backup'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--commit', required=True)
    args = parser.parse_args()
    root, release, backup = args.root.resolve(), args.release.resolve(), args.backup.resolve()
    report_path = release / 'deployment.json'
    if report_path.exists():
        raise ValueError('Deployment already attempted; inspect its report')
    evidence = json.loads((backup / 'manifest.json').read_text())
    overlay = json.loads((release / 'overlay.json').read_text())
    if not evidence['verified'] or not overlay['gates_passed']:
        raise ValueError('Passing backup and replay gates required')
    if sha(backup / 'data.tar.gz') != evidence['archive_sha256']:
        raise ValueError('Backup archive changed')
    old = run('git', '-C', str(root), 'rev-parse', 'HEAD')
    target = run('git', '-C', str(root), 'rev-parse', args.commit + '^{commit}')
    if overlay['source_commit'] != target or overlay['backup_sha256'] != evidence['archive_sha256']:
        raise ValueError('Release code/backup pairing mismatch')
    if old != evidence['source_head']:
        raise ValueError('Production code changed since backup')
    if run('git', '-C', str(root), 'status', '--porcelain', '--untracked-files=no'):
        raise ValueError('Tracked production edits require review')
    run('git', '-C', str(root), 'merge-base', '--is-ancestor', old, target)
    files = overlay['files']
    if len(files) != EXPECTED_FILES:
        raise ValueError(f'Unexpected overlay inventory: {len(files)}')
    # Check every backed-up source, including preserved TIFFs, before downtime.
    for name, expected in evidence['files'].items():
        if sha(root / name) != expected:
            raise ValueError('Production data changed since backup: ' + name)
    for name, expected in files.items():
        if not allowed(name) or name not in evidence['files']:
            raise ValueError('Unauthorised new product/path: ' + name)
        for base in (root, release):
            if not (base / name).resolve().is_relative_to(base) or (base / name).is_symlink():
                raise ValueError('Unsafe path: ' + name)
        if sha(release / name) != expected:
            raise ValueError('Release hash mismatch: ' + name)
        json.loads((release / name).read_text())
    # Read-back verify the backup again before stopping the service.
    with tarfile.open(backup / 'data.tar.gz', 'r:gz') as archive:
        seen = set()
        for member in archive:
            if not member.isfile() or member.name not in evidence['files'] or member.name in seen:
                raise ValueError('Invalid backup inventory')
            content = archive.extractfile(member).read()
            if hashlib.sha256(content).hexdigest() != evidence['files'][member.name]:
                raise ValueError('Backup member mismatch')
            if Path(member.name).suffix in ('.json', '.geojson'):
                json.loads(content)
            seen.add(member.name)
        if seen != set(evidence['files']):
            raise ValueError('Incomplete backup')
    report = {'previous_commit': old, 'commit': target, 'backup': str(backup),
              'files': len(files), 'passed': False, 'started': time.time()}
    stopped = False
    changed = []
    try:
        run('sudo', '-n', 'systemctl', 'stop', 'insightsafrica')
        stopped = True
        run('git', '-C', str(root), 'checkout', '--detach', target)
        for name, expected in files.items():
            changed.append(name)
            atomic_write(root / name, (release / name).read_bytes())
            if sha(root / name) != expected:
                raise ValueError('Deployed file mismatch: ' + name)
        run('sudo', '-n', 'systemctl', 'start', 'insightsafrica')
        for attempt in range(30):
            try:
                with urllib.request.urlopen('http://127.0.0.1:8001/api/flood/layers', timeout=5) as response:
                    if response.headers.get('X-Administrative-Key-Version') != '2':
                        raise ValueError('Missing version header')
                    json.load(response)
                break
            except Exception:
                if attempt == 29:
                    raise
                time.sleep(1)
        report['passed'] = True
    except BaseException as error:
        report['error'] = repr(error)
        if stopped:
            run('sudo', '-n', 'systemctl', 'stop', 'insightsafrica')
            with tarfile.open(backup / 'data.tar.gz', 'r:gz') as archive:
                for name in changed:
                    atomic_write(root / name, archive.extractfile(name).read())
                    if sha(root / name) != evidence['files'][name]:
                        raise RuntimeError('Rollback hash mismatch: ' + name)
            run('git', '-C', str(root), 'checkout', '--detach', old)
            run('sudo', '-n', 'systemctl', 'start', 'insightsafrica')
            report['rolled_back'] = True
        raise
    finally:
        report['finished'] = time.time()
        with report_path.open('x') as stream:
            json.dump(report, stream, indent=2)
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
