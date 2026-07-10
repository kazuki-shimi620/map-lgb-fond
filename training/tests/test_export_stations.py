from __future__ import annotations

from pathlib import Path

from src.export.stations import build_station_passenger_lookup


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
