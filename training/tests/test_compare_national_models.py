import pandas as pd
import pytest

from common.regions import (
    PREFECTURE_TO_SLUG,
    REGIONAL_CLUSTERS,
    build_model_by_prefecture,
    validate_cluster_coverage,
)


def test_regional_clusters_cover_all_prefectures_once():
    prefectures = [
        prefecture for cluster in REGIONAL_CLUSTERS.values() for prefecture in cluster
    ]

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
