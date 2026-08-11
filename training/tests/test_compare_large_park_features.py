from __future__ import annotations

import pandas as pd

from evaluate.compare_large_park_features import filter_inner_bbox


def test_filter_inner_bbox_excludes_three_kilometer_edges() -> None:
    data = pd.DataFrame({"lat": [35.651, 35.70, 35.749], "lon": [139.681, 139.73, 139.779]})
    result = filter_inner_bbox(data, (35.65, 139.68, 35.75, 139.78), 3.0)
    assert result.index.tolist() == [1]
