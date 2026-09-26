import sys
from pathlib import Path

from affine import Affine
import numpy as np
from rasterstats import zonal_stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from cached_admin_zonal import prepared_features, cached_masks


def test_cached_geometry_preserves_both_sampling_modes_and_grid_changes():
    features = [{'type': 'Feature', 'properties': {}, 'geometry': {
        'type': 'Polygon', 'coordinates': [[[0.2, 0.2], [2.2, 0.2], [2.2, 2.2], [0.2, 2.2], [0.2, 0.2]]]}}]
    ready = prepared_features('synthetic-test', features)
    for touched in (False, True, False):
        for offset in (0, 0.3):
            affine = Affine.translation(offset, 4) * Affine.scale(1, -1)
            for values in (np.arange(16, dtype=float).reshape(4, 4), np.full((4, 4), -9999.)):
                args = {'affine': affine, 'nodata': -9999, 'all_touched': touched, 'stats': ['mean', 'max', 'min']}
                expected = zonal_stats(features, values, **args)
                with cached_masks():
                    actual = zonal_stats(ready, values, **args)
                assert actual == expected
