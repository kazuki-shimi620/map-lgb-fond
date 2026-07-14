from __future__ import annotations

import pandas as pd
import pytest

from evaluate.population_coverage import build_population_coverage_report, render_markdown


def test_build_population_coverage_report_counts_matches(tmp_path) -> None:
    population_csv = tmp_path / "municipality_population.csv"
    population_csv.write_text("year,prefecture,municipality,population_total\n", encoding="utf-8")
    properties = pd.DataFrame(
        [
            {"prefecture": "東京都", "municipality": "千代田区", "transaction_year": 2025},
            {"prefecture": "東京都", "municipality": "未整備区", "transaction_year": 2025},
        ]
    )
    population = pd.DataFrame(
        [
            {
                "year": 2025,
                "prefecture": "東京都",
                "municipality": "千代田区",
                "population_total": 1100.0,
                "households_total": 550.0,
                "population_density_per_km2": 110.0,
                "aging_rate": 31.0,
                "working_age_rate": 59.0,
                "population_change_5y_rate": 10.0,
                "household_persons_avg": 2.0,
            }
        ]
    )

    report = build_population_coverage_report(
        property_df=properties,
        population_stats_df=population,
        source_paths=["tokyo.parquet"],
        population_stats_csv=population_csv,
    )

    assert report["recordCount"] == 2
    assert report["populationStatsCount"] == 1
    assert report["matchedRowCount"] == 1
    assert report["matchRate"] == pytest.approx(0.5)
    assert report["municipalityPopulation"]["max"] == pytest.approx(1100.0)
    assert report["municipalityAgingRate"]["max"] == pytest.approx(31.0)


def test_render_markdown_includes_population_summaries() -> None:
    markdown = render_markdown(
        {
            "generatedAt": "2026-07-15T00:00:00+00:00",
            "populationStatsCsv": "municipality_population.csv",
            "populationStatsCsvBytes": 100,
            "recordCount": 10,
            "populationStatsCount": 3,
            "matchedRowCount": 8,
            "matchRate": 0.8,
            "municipalityPopulation": {"min": 0, "median": 1, "p95": 2, "max": 3},
            "municipalityHouseholds": {"min": 0, "median": 1, "p95": 2, "max": 3},
            "municipalityPopulationDensity": {"min": 0, "median": 1, "p95": 2, "max": 3},
            "municipalityAgingRate": {"min": 0, "median": 1, "p95": 2, "max": 3},
            "municipalityWorkingAgeRate": {"min": 0, "median": 1, "p95": 2, "max": 3},
            "populationChange5yRate": {"min": 0, "median": 1, "p95": 2, "max": 3},
            "householdPersonsAvg": {"min": 0, "median": 1, "p95": 2, "max": 3},
        }
    )

    assert "matchRate: 80.00%" in markdown
    assert "| municipalityPopulationDensity | 0.000 | 1.000 | 2.000 | 3.000 |" in markdown
