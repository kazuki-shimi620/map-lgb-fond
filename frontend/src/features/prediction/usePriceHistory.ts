import { useMemo } from "react";
import type { PriceHistoryPoint, StationRecord } from "../../types/assets";
import type { PredictionFormState, PredictionResult } from "../../types/prediction";
import { haversineKm } from "../../utils/distance";

type HistoryModelAnchor = {
  year: number;
  price: number;
};

type UsePriceHistoryParams = {
  forecastPoints: PriceHistoryPoint[];
  form: PredictionFormState;
  history: PriceHistoryPoint[];
  historyModelAnchor: HistoryModelAnchor | null;
  result: PredictionResult | null;
  stations: StationRecord[];
};

export function usePriceHistory({
  forecastPoints,
  form,
  history,
  historyModelAnchor,
  result,
  stations
}: UsePriceHistoryParams) {
  const targetHistory = useMemo(
    () =>
      history.filter(
        (point) =>
          point.station === form.station &&
          (point.prefecture === undefined || point.prefecture === form.prefecture)
      ),
    [form.prefecture, form.station, history]
  );

  const chartPoints = useMemo(() => {
    const comparableHistory = buildHistoryWithEstimates({
      history,
      targetHistory,
      stations,
      targetStation: form.station,
      prefecture: form.prefecture,
      area: form.area,
      age: form.age,
      modelAnchor: historyModelAnchor
    });
    return buildChartPoints(
      comparableHistory,
      forecastPoints,
      result,
      form.station,
      form.predictionYear
    );
  }, [
    forecastPoints,
    form.age,
    form.area,
    form.predictionYear,
    form.prefecture,
    form.station,
    history,
    historyModelAnchor,
    result,
    stations,
    targetHistory
  ]);

  return {
    chartPoints
  };
}

function buildChartPoints(
  history: PriceHistoryPoint[],
  forecastPoints: PriceHistoryPoint[],
  result: PredictionResult | null,
  station: string,
  predictionYear: number
) {
  const sortedHistory = [...history]
    .map((point) => ({
      ...point,
      kind: point.kind === "estimated" ? ("estimated" as const) : ("actual" as const)
    }))
    .sort((a, b) => a.year - b.year);
  if (!result) {
    return sortedHistory;
  }

  const predictionsByYear = new Map(
    forecastPoints
      .filter((point) => point.year > (sortedHistory.at(-1)?.year ?? 0))
      .map((point) => [point.year, { ...point, kind: "forecast" as const }])
  );
  if (predictionYear > (sortedHistory.at(-1)?.year ?? 0)) {
    predictionsByYear.set(predictionYear, {
      station,
      year: predictionYear,
      avg_price: result.predictedPrice,
      kind: "forecast"
    });
  }

  return [...sortedHistory, ...predictionsByYear.values()].sort((a, b) => a.year - b.year);
}

function buildHistoryWithEstimates({
  history,
  targetHistory,
  stations,
  targetStation,
  prefecture,
  area,
  age,
  modelAnchor
}: {
  history: PriceHistoryPoint[];
  targetHistory: PriceHistoryPoint[];
  stations: StationRecord[];
  targetStation: string;
  prefecture: string;
  area: number;
  age: number;
  modelAnchor: { year: number; price: number } | null;
}) {
  const actual = buildComparableHistory(targetHistory, area, age).map((point) => ({
    ...point,
    kind: "actual" as const
  }));
  if (!modelAnchor) {
    return actual;
  }

  const nearbyStationNames = findNearbyStationNames(stations, targetStation);
  const nearbySet = new Set(nearbyStationNames);
  const nearbyHistory = history.filter(
    (point) =>
      nearbySet.has(point.station) &&
      (point.prefecture === undefined || point.prefecture === prefecture)
  );
  const comparableNearby = nearbyStationNames.flatMap((station) =>
    buildComparableHistory(
      nearbyHistory.filter((point) => point.station === station),
      area,
      age
    )
  );
  const marketByYear = aggregateMarketByYear(comparableNearby);
  const anchorMarket = findClosestMarketPoint(marketByYear, modelAnchor.year);
  if (!anchorMarket || anchorMarket.avgPrice <= 0) {
    return actual;
  }

  const actualYears = new Set(actual.map((point) => point.year));
  const levelAdjustment = modelAnchor.price / anchorMarket.avgPrice;
  const estimates: PriceHistoryPoint[] = [...marketByYear.entries()]
    .filter(([year]) => !actualYears.has(year) && year <= modelAnchor.year)
    .map(([year, market]) => ({
      prefecture,
      station: targetStation,
      year,
      avg_price: market.avgPrice * levelAdjustment,
      transaction_count: market.transactionCount,
      kind: "estimated"
    }));

  return [...actual, ...estimates].sort((a, b) => a.year - b.year);
}

function findNearbyStationNames(stations: StationRecord[], targetStation: string) {
  const target = stations.find((station) => station.station_name === targetStation);
  if (!target) {
    return [];
  }

  const distanceByName = new Map<string, number>();
  for (const station of stations) {
    if (station.station_name === targetStation) {
      continue;
    }
    const distance = haversineKm(target.lat, target.lon, station.lat, station.lon);
    const current = distanceByName.get(station.station_name);
    if (distance <= 5 && (current === undefined || distance < current)) {
      distanceByName.set(station.station_name, distance);
    }
  }

  return [...distanceByName.entries()]
    .sort((left, right) => left[1] - right[1])
    .slice(0, 12)
    .map(([station]) => station);
}

function aggregateMarketByYear(points: PriceHistoryPoint[]) {
  const totals = new Map<number, { weightedPrice: number; transactionCount: number }>();
  for (const point of points) {
    const transactionCount = Math.max(1, point.transaction_count ?? 1);
    const total = totals.get(point.year) ?? { weightedPrice: 0, transactionCount: 0 };
    total.weightedPrice += point.avg_price * transactionCount;
    total.transactionCount += transactionCount;
    totals.set(point.year, total);
  }

  return new Map(
    [...totals.entries()].map(([year, total]) => [
      year,
      {
        avgPrice: total.weightedPrice / total.transactionCount,
        transactionCount: total.transactionCount
      }
    ])
  );
}

function findClosestMarketPoint(
  marketByYear: Map<number, { avgPrice: number; transactionCount: number }>,
  targetYear: number
) {
  return [...marketByYear.entries()]
    .sort((left, right) => Math.abs(left[0] - targetYear) - Math.abs(right[0] - targetYear))
    .at(0)?.[1];
}

function buildComparableHistory(history: PriceHistoryPoint[], area: number, age: number) {
  const areaBand = Math.min(100, Math.floor(area / 5) * 5);
  const ageBand = Math.min(60, Math.floor(age / 5) * 5);

  return history.map((point) => {
    const nearbyPoints = history.filter((candidate) => Math.abs(candidate.year - point.year) <= 2);
    const exactMatch = aggregateComparableBuckets(
      nearbyPoints,
      (bucket) => bucket[0] === areaBand && bucket[1] === ageBand
    );
    const areaMatch = aggregateComparableBuckets(
      nearbyPoints,
      (bucket) => bucket[0] === areaBand
    );
    const comparable =
      exactMatch.transactionCount >= 3
        ? exactMatch
        : areaMatch.transactionCount >= 3
          ? areaMatch
          : {
              avgUnitPrice: point.avg_unit_price ?? 0,
              transactionCount: point.transaction_count ?? 0
            };

    return {
      ...point,
      avg_price:
        comparable.avgUnitPrice > 0 && area > 0
          ? comparable.avgUnitPrice * area
          : point.avg_price,
      transaction_count: comparable.transactionCount
    };
  });
}

function aggregateComparableBuckets(
  points: PriceHistoryPoint[],
  predicate: (bucket: NonNullable<PriceHistoryPoint["comparable_buckets"]>[number]) => boolean
) {
  let weightedUnitPrice = 0;
  let transactionCount = 0;
  for (const point of points) {
    for (const bucket of point.comparable_buckets ?? []) {
      if (!predicate(bucket)) {
        continue;
      }
      weightedUnitPrice += bucket[2] * bucket[3];
      transactionCount += bucket[3];
    }
  }
  return {
    avgUnitPrice: transactionCount > 0 ? weightedUnitPrice / transactionCount : 0,
    transactionCount
  };
}
