from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from common.regions import (
    PREFECTURE_TO_SLUG,
    REGIONAL_CLUSTERS,
    build_model_by_prefecture,
    validate_cluster_coverage,
)
from evaluate.compare_national_models import (
    build_residual_corrections,
    map_residual_corrections,
)


def test_regional_clusters_cover_all_prefectures_once():
    prefectures = [prefecture for cluster in REGIONAL_CLUSTERS.values() for prefecture in cluster]

    assert len(prefectures) == 47
    assert len(set(prefectures)) == 47
    validate_cluster_coverage(pd.Series(prefectures))


def test_regional_cluster_validation_rejects_unknown_prefecture():
    with pytest.raises(ValueError, match="Regional cluster mismatch"):
        validate_cluster_coverage(pd.Series(["架空県"]))


def test_prefectures_resolve_to_station_slug_and_production_model():
    model_by_prefecture = build_model_by_prefecture()

    assert len(PREFECTURE_TO_SLUG) == 47
    assert model_by_prefecture["東京都"] == "tokyo"
    assert model_by_prefecture["大阪府"] == "regional_kinki"
    assert model_by_prefecture["沖縄県"] == "regional_kyushu"


def test_build_residual_corrections_shrinks_small_groups() -> None:
    corrections = build_residual_corrections(
        groups=pd.Series(["a", "a", "b"]),
        residuals=np.array([100.0, 300.0, 1000.0]),
        shrinkage_count=2,
    )

    assert corrections["fallback"] == 1400.0 / 3.0
    assert 200.0 < corrections["groups"]["a"] < corrections["fallback"]
    assert corrections["fallback"] < corrections["groups"]["b"] < 1000.0


def test_map_residual_corrections_uses_fallback_for_unknown_group() -> None:
    corrections = {
        "fallback": 10.0,
        "groups": {
            "tokyo": 100.0,
        },
    }

    actual = map_residual_corrections(pd.Series(["tokyo", "unknown"]), corrections)

    assert actual.tolist() == [100.0, 10.0]
