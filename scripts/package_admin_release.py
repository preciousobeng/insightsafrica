"""Package only existing production products after all replay gates pass."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from deploy_admin_release import allowed, EXPECTED_FILES

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--destination', required=True, type=Path)
    parser.add_argument('--backup-manifest', required=True, type=Path)
    args = parser.parse_args()
    gates = {}
    for name in ('admin-regeneration-production.json', 'admin-current-replay-production.json',
                 'admin-derived-production.json', 'admin-derived-equality-production.json'):
        path = ROOT / 'docs' / name
        if not json.loads(path.read_text())['passed']:
            raise ValueError('Failed gate: ' + name)
        gates[name] = sha(path)
    backup = json.loads(args.backup_manifest.read_text())
    if not backup['verified']:
        raise ValueError('Verified backup required')
    base = ROOT / 'data/admin-remediation-output/production'
    paths = sorted(p for p in (base / 'data').rglob('*') if p.is_file() and allowed(str(p.relative_to(base))))
    names = {str(p.relative_to(base)) for p in paths}
    expected = {name for name in backup['files'] if allowed(name)}
    if names != expected or len(paths) != EXPECTED_FILES:
        raise ValueError(f'Inventory mismatch: {len(paths)}; missing={sorted(expected-names)}; extra={sorted(names-expected)}')
    args.destination.mkdir(parents=True, exist_ok=False)
    files = {}
    for source in paths:
        name = str(source.relative_to(base))
        if source.is_symlink():
            raise ValueError('Symlink in release')
        json.loads(source.read_text())
        target = args.destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if sha(source) != sha(target):
            raise ValueError('Copy mismatch: ' + name)
        files[name] = sha(target)
    manifest = {'gates_passed': True, 'gates': gates,
                'source_commit': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                'backup_sha256': backup['archive_sha256'], 'files': files}
    with (args.destination / 'overlay.json').open('x') as stream:
        json.dump(manifest, stream, indent=2)
    print(f'Packaged {len(files)} verified existing products: {args.destination}', flush=True)


if __name__ == '__main__':
    main()
