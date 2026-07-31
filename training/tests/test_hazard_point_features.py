from collect.hazard_point_features import _apply_tile_features, group_points_by_tile


def test_group_points_by_tile_deduplicates_tile() -> None:
    grouped = group_points_by_tile([(35.68, 139.76), (35.681, 139.761)], ["XKT029"])

    assert len(grouped) == 1
    assert len(next(iter(grouped.values()))) == 2


def test_apply_tile_features_uses_maximum_matching_risk() -> None:
    rows = {}
    polygon = {
        "type": "Polygon",
        "coordinates": [[[139, 35], [140, 35], [140, 36], [139, 36], [139, 35]]],
    }
    features = [
        {"geometry": polygon, "properties": {"A31a_205": 2}},
        {"geometry": polygon, "properties": {"A31a_205": 4}},
    ]

    _apply_tile_features(rows, [(35.5, 139.5)], "XKT026", features)

    assert rows[(35.5, 139.5)]["flood_risk_level"] == 4
    assert rows[(35.5, 139.5)]["flood_source_available"] == 1
