"""Migration-only geometry cache; rasterstats still computes every statistic.

Use only with validated immutable staged polygon layers, in single-threaded
workers. Reuses rasterized masks when geometry, grid and sampling match.
"""
from contextlib import contextmanager

import rasterstats.main
from shapely.geometry import shape

_features = {}
_masks = {}


def prepared_features(identity, features):
    if identity not in _features:
        _features[identity] = [{**f, 'geometry': shape(f['geometry'])} for f in features]
    return _features[identity]


@contextmanager
def cached_masks():
    original = rasterstats.main.rasterize_geom
    def rasterize(geom, like, all_touched=False):
        if geom.geom_type not in ('Polygon', 'MultiPolygon'):
            return original(geom, like, all_touched=all_touched)
        # Prepared geometries remain alive in _features, so object IDs cannot
        # be recycled while their masks are cached.
        key = (id(geom), like.affine, like.array.shape, all_touched)
        if key not in _masks:
            _masks[key] = original(geom, like, all_touched=all_touched)
        return _masks[key]
    rasterstats.main.rasterize_geom = rasterize
    try:
        yield
    finally:
        rasterstats.main.rasterize_geom = original
