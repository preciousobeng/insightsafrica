"""Administrative area identifiers shared by boundary and statistics writers."""


def build_key(name: str, parent: str | None = None) -> str:
    if not isinstance(name, str) or not name.strip() or name != name.strip():
        raise ValueError(f"Missing or untrimmed area name: {name!r}")
    if '|' in name:
        raise ValueError(f"Ambiguous area name: {name!r}")
    if parent is None or parent == '':
        return name
    if not isinstance(parent, str) or not parent.strip() or parent != parent.strip() or '|' in parent:
        raise ValueError(f"Invalid parent: {parent!r}")
    return f'{name}|{parent}'


def parse_key(key: str) -> tuple[str, str | None]:
    if not isinstance(key, str):
        raise ValueError(f"Invalid area key: {key!r}")
    parts = key.split('|')
    if len(parts) > 2 or (len(parts) == 2 and not parts[1]):
        raise ValueError(f"Invalid area key: {key!r}")
    name, parent = parts[0], parts[1] if len(parts) == 2 else None
    build_key(name, parent)
    return name, parent


def feature_keys(features: list) -> list[str]:
    keys = []
    seen = set()
    for feature in features:
        props = feature.get('properties', {})
        key = build_key(props.get('name'), props.get('region'))
        if key in seen:
            raise ValueError(f'Duplicate administrative key: {key}')
        seen.add(key)
        keys.append(key)
    return keys


def unique_name_match(key: str, candidates) -> str | None:
    """Only resolve a missing parent when exactly one candidate has that name."""
    name, parent = parse_key(key)
    if parent is not None:
        return None
    matches = [candidate for candidate in candidates if parse_key(candidate)[0] == name]
    if len(matches) > 1:
        raise ValueError(f'Ambiguous parent for {name!r}: {sorted(matches)}')
    return matches[0] if matches else None
