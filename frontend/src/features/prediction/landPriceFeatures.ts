import type { LandPriceSummary, LandPriceYearSummary } from "../../types/assets";

export type LandPriceRequestFields = {
  landPriceCityAvgYenPerSqm: number;
  landPriceCityYoyRate: number;
  landPricePointsCityCount: number;
  nearestLandPriceYenPerSqm: number;
  nearestLandPriceDistanceKm: number;
  landPricePointsWithin2km: number;
  hasLandPriceData: number;
};

const EMPTY_LAND_PRICE_FIELDS: LandPriceRequestFields = {
  landPriceCityAvgYenPerSqm: 0,
  landPriceCityYoyRate: 0,
  landPricePointsCityCount: 0,
  nearestLandPriceYenPerSqm: 0,
  nearestLandPriceDistanceKm: 0,
  landPricePointsWithin2km: 0,
  hasLandPriceData: 0
};

export function buildLandPriceRequestFields(
  summary: LandPriceSummary | null,
  prefecture: string,
  municipality: string,
  predictionYear: number
): LandPriceRequestFields {
  const city = summary?.cities[`${prefecture}|${municipality}`];
  if (!city) {
    return EMPTY_LAND_PRICE_FIELDS;
  }

  const yearSummary = selectLatestYearSummary(city.years, predictionYear);
  if (!yearSummary) {
    return EMPTY_LAND_PRICE_FIELDS;
  }

  return {
    landPriceCityAvgYenPerSqm: yearSummary.avgPriceYenPerSqm,
    landPriceCityYoyRate: yearSummary.yoyRate,
    landPricePointsCityCount: yearSummary.pointCount,
    nearestLandPriceYenPerSqm: 0,
    nearestLandPriceDistanceKm: 0,
    landPricePointsWithin2km: 0,
    hasLandPriceData:
      yearSummary.avgPriceYenPerSqm + yearSummary.yoyRate + yearSummary.pointCount > 0 ? 1 : 0
  };
}

function selectLatestYearSummary(
  years: Record<string, LandPriceYearSummary>,
  predictionYear: number
) {
  const targetYear = Math.floor(predictionYear);
  const availableYears = Object.keys(years)
    .map((year) => Number(year))
    .filter((year) => Number.isFinite(year) && year <= targetYear)
    .sort((a, b) => b - a);
  const selectedYear = availableYears[0];
  return selectedYear === undefined ? null : years[String(selectedYear)];
}
