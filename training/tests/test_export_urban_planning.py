from __future__ import annotations

from export.urban_planning import build_urban_planning_collection


def test_build_urban_planning_collection_exports_compact_area_records() -> None:
    collection = build_urban_planning_collection(
        [
            {
                "area_type": "zoning",
                "prefecture": "東京都",
                "city_name": "千代田区",
                "area_name": "商業地域",
                "zoning_type": "商業地域",
                "floor_area_ratio": "500",
                "building_coverage_ratio": "80",
                "geometry_json": (
                    '{"type":"Polygon","coordinates":[[[139.0,35.0],'
                    "[139.1,35.0],[139.1,35.1],[139.0,35.0]]]}"
                ),
            },
            {
                "area_type": "zoning",
                "prefecture": "東京都",
                "city_name": "千代田区",
                "geometry_json": "",
            },
        ]
    )

    area = collection["areas"][0]

    assert collection["schemaVersion"] == 1
    assert collection["areaCount"] == 1
    assert area["areaType"] == "zoning"
    assert area["municipality"] == "千代田区"
    assert area["floorAreaRatio"] == 500
    assert area["buildingCoverageRatio"] == 80
    assert area["bbox"] == [139.0, 35.0, 139.1, 35.1]
