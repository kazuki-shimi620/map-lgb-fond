from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from features.commercial_facilities import (
    COMMERCIAL_FEATURES,
    add_commercial_facility_features,
    load_commercial_facilities_csv,
)
from features.hazards import HAZARD_FEATURES, add_hazard_features, load_hazard_features_csv
from features.station_passengers import (
    STATION_PASSENGER_FEATURES,
    add_station_passenger_features,
    load_station_passengers_csv,
)


class IFeatureProvider(Protocol):
    output_features: list[str]

    def fit(self, df) -> None: ...

    def transform(self, df, context: dict): ...


@dataclass
class FeaturePipeline:
    providers: list[IFeatureProvider]

    def fit_transform(self, df):
        context: dict = {}
        current = df.copy()
        for provider in self.providers:
            provider.fit(current)
            current = provider.transform(current, context)
        return current, context


@dataclass
class BaseProvider:
    output_features: list[str] = field(default_factory=list)

    def fit(self, df) -> None:
        return None

    def transform(self, df, context: dict):
        for feature in self.output_features:
            context[feature] = df[feature]
        return df


class AreaProvider(BaseProvider):
    def __init__(self) -> None:
        super().__init__(["area"])


class AgeProvider(BaseProvider):
    def __init__(self) -> None:
        super().__init__(["age"])


class LocationProvider(BaseProvider):
    def __init__(self) -> None:
        super().__init__(["prefecture", "municipality", "station", "station_distance"])


class BuildingProvider(BaseProvider):
    def __init__(self) -> None:
        super().__init__(["room_layout", "building_type"])


class TransactionProvider(BaseProvider):
    def __init__(self) -> None:
        super().__init__(["transaction_year"])


@dataclass
class StationPassengerProvider:
    csv_path: Path = Path("data/processed/station_passengers/station_groups.csv")
    output_features: list[str] = field(default_factory=lambda: list(STATION_PASSENGER_FEATURES))

    def fit(self, df) -> None:
        if not self.csv_path.exists():
            raise FileNotFoundError(f"Station passenger CSV not found: {self.csv_path}")
        self._station_passengers = load_station_passengers_csv(self.csv_path)

    def transform(self, df, context: dict):
        result = add_station_passenger_features(df, self._station_passengers)
        _store_output_features(context, result, self.output_features)
        return result


@dataclass
class CommercialFacilityProvider:
    csv_path: Path = Path("data/processed/jcsc/jcsc_sc_open.csv")
    data_start_year: int = 2015
    output_features: list[str] = field(default_factory=lambda: list(COMMERCIAL_FEATURES))

    def fit(self, df) -> None:
        if not self.csv_path.exists():
            raise FileNotFoundError(f"Commercial facility CSV not found: {self.csv_path}")
        self._facilities = load_commercial_facilities_csv(self.csv_path)

    def transform(self, df, context: dict):
        result = add_commercial_facility_features(
            df,
            self._facilities,
            data_start_year=self.data_start_year,
        )
        _store_output_features(context, result, self.output_features)
        return result


@dataclass
class HazardProvider:
    csv_path: Path = Path("data/processed/hazards/hazard_features.csv")
    output_features: list[str] = field(default_factory=lambda: list(HAZARD_FEATURES))

    def fit(self, df) -> None:
        if not self.csv_path.exists():
            raise FileNotFoundError(f"Hazard feature CSV not found: {self.csv_path}")
        self._hazards = load_hazard_features_csv(self.csv_path)

    def transform(self, df, context: dict):
        result = add_hazard_features(df, self._hazards)
        _store_output_features(context, result, self.output_features)
        return result


def create_mvp_feature_pipeline() -> FeaturePipeline:
    return FeaturePipeline(
        providers=[
            AreaProvider(),
            AgeProvider(),
            LocationProvider(),
            BuildingProvider(),
            TransactionProvider(),
        ]
    )


def create_external_feature_pipeline(
    *,
    requested_features: set[str],
    station_passengers_csv: str | None = None,
    commercial_facilities_csv: str | None = None,
    hazard_features_csv: str | None = None,
    commercial_data_start_year: int = 2015,
) -> FeaturePipeline | None:
    providers: list[IFeatureProvider] = []

    if not requested_features.isdisjoint(STATION_PASSENGER_FEATURES):
        providers.append(
            StationPassengerProvider(
                csv_path=Path(
                    station_passengers_csv or "data/processed/station_passengers/station_groups.csv"
                )
            )
        )

    if not requested_features.isdisjoint(COMMERCIAL_FEATURES):
        providers.append(
            CommercialFacilityProvider(
                csv_path=Path(commercial_facilities_csv or "data/processed/jcsc/jcsc_sc_open.csv"),
                data_start_year=commercial_data_start_year,
            )
        )

    if not requested_features.isdisjoint(HAZARD_FEATURES):
        providers.append(
            HazardProvider(
                csv_path=Path(hazard_features_csv or "data/processed/hazards/hazard_features.csv")
            )
        )

    if not providers:
        return None
    return FeaturePipeline(providers=providers)


def _store_output_features(context: dict, df, output_features: list[str]) -> None:
    for feature in output_features:
        if feature in df.columns:
            context[feature] = df[feature]
