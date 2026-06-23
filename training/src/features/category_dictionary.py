from __future__ import annotations

from dataclasses import dataclass


FIELD_TO_JSON_KEY = {
    "prefecture": "prefectures",
    "municipality": "municipalities",
    "station": "stations",
    "room_layout": "roomLayouts",
    "building_type": "buildingTypes",
}


@dataclass(frozen=True)
class CategoryEncodingResult:
    dataframe: object
    dictionary: dict


def build_and_apply_category_dictionary(df, categorical_features: list[str]) -> CategoryEncodingResult:
    encoded = df.copy()
    dictionary: dict = {"unknownId": 0}

    for feature in categorical_features:
        json_key = FIELD_TO_JSON_KEY.get(feature, feature)
        values = sorted(str(value) for value in encoded[feature].dropna().unique())
        mapping = {value: index + 1 for index, value in enumerate(values)}
        dictionary[json_key] = mapping
        encoded[feature] = encoded[feature].astype(str).map(mapping).fillna(0).astype("int64")

    return CategoryEncodingResult(dataframe=encoded, dictionary=dictionary)
