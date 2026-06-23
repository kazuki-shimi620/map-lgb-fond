from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class IFeatureProvider(Protocol):
    output_features: list[str]

    def fit(self, df) -> None:
        ...

    def transform(self, df, context: dict):
        ...


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
