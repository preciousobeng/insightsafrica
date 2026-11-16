"""Restrictive static serving for public pages and metadata-referenced map PNGs."""

import json
from pathlib import Path, PurePosixPath

from fastapi import HTTPException
from fastapi.staticfiles import StaticFiles


class PublicFrontendFiles(StaticFiles):
    async def get_response(self, path, scope):
        parts = PurePosixPath(path.replace("\\", "/")).parts
        security_contact = parts == (".well-known", "security.txt")
        if not security_contact and any(part.startswith((".", "_")) for part in parts):
            raise HTTPException(status_code=404)
        if "admin-hierarchy-v2.html" in parts:
            raise HTTPException(status_code=404)
        if Path(path).suffix.lower() in {
            ".yml",
            ".yaml",
            ".py",
            ".sql",
            ".md",
            ".toml",
            ".env",
        }:
            raise HTTPException(status_code=404)
        return await super().get_response(path, scope)


class PublicMapFiles(StaticFiles):
    """Only PNG filenames actually referenced by known product metadata are public."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._signature = None
        self._public_pngs = set()

    def public_pngs(self):
        root = Path(self.directory)
        metadata = sorted(
            set(
                path
                for pattern in (
                    "chirps-*.json",
                    "ndvi_*.json",
                    "heat_*.json",
                    "galamsey_sites.json",
                    "*_mining_sites.json",
                )
                for path in root.glob(pattern)
                if path.is_file()
            )
        )
        signature = tuple(
            (path.name, path.stat().st_mtime_ns, path.stat().st_size)
            for path in metadata
        )
        if signature == self._signature:
            return self._public_pngs
        names = set()

        def inspect(value):
            if isinstance(value, dict):
                for item in value.values():
                    inspect(item)
            elif isinstance(value, list):
                for item in value:
                    inspect(item)
            elif (
                isinstance(value, str)
                and value.endswith(".png")
                and Path(value).name == value
            ):
                names.add(value)

        for path in metadata:
            try:
                inspect(json.loads(path.read_text()))
            except (OSError, ValueError):
                continue  # Fail closed during an incomplete metadata write.
        self._signature = signature
        self._public_pngs = names
        return names

    async def get_response(self, path, scope):
        if "/" in path or "\\" in path or path not in self.public_pngs():
            raise HTTPException(status_code=404)
        return await super().get_response(path, scope)
