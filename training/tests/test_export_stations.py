from __future__ import annotations

from pathlib import Path

from src.export.stations import (
    build_station_passenger_candidates,
    build_station_passenger_lookup,
    select_station_passenger,
)


def test_build_station_passenger_lookup_uses_largest_same_name_station(tmp_path: Path) -> None:
    csv_path = tmp_path / "station_groups.csv"
    csv_path.write_text(
        "\n".join(
            [
                "station_name,normalized_station_name,latest_passenger_count,latest_passenger_year,rank,log_passenger_count,line_count,operator_count",
                "新宿,新宿,100,2023,D,4.6,1,1",
                "新宿,新宿,1000,2023,C,6.9,2,2",
            ]
        ),
        encoding="utf-8",
    )

    lookup = build_station_passenger_lookup(csv_path)

    assert lookup["新宿"] == {
        "station_passenger_log": 6.9,
        "station_line_count": 2.0,
        "station_operator_count": 2.0,
        "station_rank": "C",
    }


def test_select_station_passenger_uses_nearest_candidate(tmp_path: Path) -> None:
    csv_path = tmp_path / "station_groups.csv"
    csv_path.write_text(
        "\n".join(
            [
                "station_name,normalized_station_name,lat,lon,latest_passenger_count,latest_passenger_year,rank,log_passenger_count,line_count,operator_count",
                "中央,中央,36.0,140.0,10000,2023,A,9.2,4,3",
                "中央,中央,35.001,139.001,100,2024,D,4.6,1,1",
            ]
        ),
        encoding="utf-8",
    )

    candidates = build_station_passenger_candidates(csv_path)
    selected = select_station_passenger(candidates, "中央", 35.0, 139.0)

    assert selected == {
        "station_passenger_log": 4.6,
        "station_line_count": 1.0,
        "station_operator_count": 1.0,
        "station_rank": "D",
    }


def test_select_station_passenger_rejects_distant_same_name(tmp_path: Path) -> None:
    csv_path = tmp_path / "station_groups.csv"
    csv_path.write_text(
        "station_name,normalized_station_name,lat,lon,latest_passenger_count,"
        "latest_passenger_year,rank,log_passenger_count,line_count,operator_count\n"
        "大森,大森,35.58,139.73,10000,2023,C,9.2,2,1\n",
        encoding="utf-8",
    )

    candidates = build_station_passenger_candidates(csv_path)

    assert select_station_passenger(candidates, "大森", 34.78, 138.18) == {}
