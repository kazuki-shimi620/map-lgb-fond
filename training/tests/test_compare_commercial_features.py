from __future__ import annotations

import pandas as pd

from evaluate.compare_commercial_features import (
    CANDIDATES,
    _feature_lists,
    _sample_by_region_year,
)


def test_sample_by_region_year_preserves_each_group_and_limit() -> None:
    data = pd.DataFrame(
        [
            {"source_region": region, "transaction_year": year, "value": index}
            for region in ["tokyo", "chiba"]
            for year in [2023, 2024]
            for index in range(5)
        ]
    )

    actual = _sample_by_region_year(data, 2)

    counts = actual.groupby(["source_region", "transaction_year"]).size()
    assert len(actual) == 8
    assert counts.eq(2).all()


def test_scale_candidate_contains_all_scale_distance_and_count_features() -> None:
    candidate = next(item for item in CANDIDATES if item.name == "spatial_distance_counts_by_scale")

    features, _ = _feature_lists(candidate)

    for scale in ["small", "medium", "large", "very_large"]:
        assert f"nearest_sc_{scale}_distance_km" in features
        assert f"sc_{scale}_count_within_3km" in features
