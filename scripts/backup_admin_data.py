"""Create a new data backup and read every member back before permitting deploy."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    dest = args.destination.resolve()
    if dest.is_relative_to(root):
        raise ValueError('Backup must be outside the repository')
    if not (root / 'data/archive').is_dir():
        raise ValueError('Archive missing')
    dest.mkdir(parents=True, exist_ok=False)
    paths = set(p for p in (root / 'data/archive').rglob('*') if p.is_file())
    for directory in (root / 'data').glob('processed*'):
        paths.update(directory.glob('*.geojson'))
        paths.update(directory.glob('chirps-*.json'))
    paths.update((root / 'data/exposure').glob('*.json'))
    manifest = {}
    for path in sorted(paths):
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError(f'Unsafe backup input: {path}')
        content = path.read_bytes()
        if path.suffix in ('.json', '.geojson'):
            json.loads(content)
        manifest[str(path.relative_to(root))] = digest(content)
    backup = dest / 'data.tar.gz'
    with tarfile.open(backup, 'x:gz') as archive:
        for path in sorted(paths):
            archive.add(path, arcname=str(path.relative_to(root)), recursive=False)
    seen = set()
    with tarfile.open(backup, 'r:gz') as archive:
        for member in archive:
            if not member.isfile() or member.name not in manifest or member.name in seen:
                raise ValueError(f'Unexpected backup member: {member.name}')
            content = archive.extractfile(member).read()
            if digest(content) != manifest[member.name]:
                raise ValueError(f'Backup read-back hash mismatch: {member.name}')
            if Path(member.name).suffix in ('.json', '.geojson'):
                json.loads(content)
            seen.add(member.name)
    if seen != set(manifest):
        raise ValueError('Backup member inventory mismatch')
    # Detect any source change during backup. Stop instead of trusting a stale copy.
    for name, expected in manifest.items():
        if digest((root / name).read_bytes()) != expected:
            raise ValueError(f'Source changed during backup: {name}')
    head = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    (dest / 'manifest.json').write_text(json.dumps({'verified': True, 'source_head': head,
        'archive_sha256': digest(backup.read_bytes()), 'files': manifest}, indent=2))
    print(f'BACKUP VERIFIED: {len(manifest)} files, every JSON parsed and every member hash checked; {dest}', flush=True)


if __name__ == '__main__':
    main()
