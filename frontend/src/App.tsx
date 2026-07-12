import { useMemo, useRef, useState } from "react";
import { CommercialFacilityCard } from "./features/facilities/CommercialFacilityCard";
import { HazardRiskCard } from "./features/hazard/HazardRiskCard";
import { PropertyMap } from "./features/map/PropertyMap";
import { PriceHistoryChart } from "./features/prediction/PriceHistoryChart";
import {
  ForecastControls,
  PropertyConditionForm,
  PredictionSheetHandle,
  type FutureScenario
} from "./features/prediction/PredictionForm";
import {
  PredictionDetailsPanel,
  PredictionResultView,
  type PredictionSummary
} from "./features/prediction/PredictionResultView";
import { SupportingInfoTabs } from "./features/prediction/SupportingInfoTabs";
import { usePricePrediction } from "./features/prediction/usePricePrediction";
import { usePropertySelection } from "./features/prediction/usePropertySelection";
import { useRegionAssets } from "./features/prediction/useRegionAssets";
import { StationScaleCard } from "./features/stations/StationScaleCard";
import type { PriceHistoryPoint, StationRecord } from "./types/assets";
import type { PredictionFormState, PredictionResult } from "./types/prediction";
import { haversineKm } from "./utils/distance";
import { getPrefectureLabel } from "./utils/region";

const initialForm: PredictionFormState = {
  prefecture: "東京都",
  municipality: "千代田区",
  station: "東京",
  area: 55,
  age: 15,
  stationDistance: 8,
  roomLayout: "2LDK",
  buildingType: "ＲＣ",
  predictionYear: new Date().getFullYear(),
  lat: 35.681236,
  lon: 139.767125
};

export function App() {
  const [form, setForm] = useState<PredictionFormState>(initialForm);
  const [futureScenario, setFutureScenario] = useState<FutureScenario>("base");
  const [formSheetState, setFormSheetState] = useState<"collapsed" | "half" | "open">("collapsed");
  const [errorMessage, setErrorMessage] = useState("");

  const {
    assetStatus,
    assetWarnings,
    closeArchiveHistory,
    commercialFacilities,
    history,
    isArchiveLoaded,
    isArchiveLoading,
    isModelReady,
    loadArchiveHistory,
    metadata,
    region,
    setStations,
    stations,
    trendSummary
  } = useRegionAssets({
    prefecture: form.prefecture,
    setForm,
    setErrorMessage
  });
  const clearPredictionStateRef = useRef<() => void>(() => {});

  const longRangeWarning =
    metadata && form.predictionYear > metadata.latestTrainingYear + 10
      ? "長期予測のため精度は保証できません"
      : "";
  const predictionYearRange = useMemo(
    () => ({
      min: metadata?.latestTrainingYear ?? new Date().getFullYear(),
      max: (metadata?.latestTrainingYear ?? new Date().getFullYear()) + 10
    }),
    [metadata]
  );

  const {
    formPanelRef,
    handleFormChange,
    handleMapSelect,
    isSelectionSupported,
    sheetStackRef,
    stationDistanceSource
  } = usePropertySelection({
    form,
    setForm,
    region,
    setStations,
    clearPredictionState: () => clearPredictionStateRef.current(),
    setErrorMessage,
    setFormSheetState
  });

  const {
    clearPredictionState,
    forecastPoints,
    historyModelAnchor,
    isPredicting,
    result
  } = usePricePrediction({
    form,
    futureScenario,
    history,
    isModelReady,
    isSelectionSupported,
    region,
    setErrorMessage,
    stations,
    trendSummary
  });
  clearPredictionStateRef.current = clearPredictionState;

  const loadingMessage =
    assetStatus.modelStatus === "loading" && region
      ? "モデルを読み込んでいます"
      : isPredicting
        ? "予測を更新しています"
        : "";

  const stationOptions = stations.map((station) => station.station_name);
  const selectedStation = stations.find((station) => station.station_name === form.station);
  const targetHistory = history.filter(
    (point) =>
      point.station === form.station &&
      (point.prefecture === undefined || point.prefecture === form.prefecture)
  );
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
  const chartPoints = buildChartPoints(
    comparableHistory,
    forecastPoints,
    result,
    form.station,
    form.predictionYear
  );
  const predictionSummary: PredictionSummary | undefined = region
    ? {
        station: form.station,
        stationDistance: Math.round(form.stationDistance),
        modelRegion: getPrefectureLabel(region),
        latestTrainingYear: metadata?.latestTrainingYear ?? null,
        trainStartYear: metadata?.deployment?.trainStartYear ?? metadata?.evaluation?.trainStartYear ?? null,
        evaluationMae: metadata?.evaluation?.metrics.mae ?? metadata?.mae ?? null,
        evaluationRmse: metadata?.evaluation?.metrics.rmse ?? null,
        trainCount: metadata?.deployment?.trainCount ?? metadata?.evaluation?.trainCount ?? null,
        generatedAt: metadata?.generatedAt ?? null,
        featureImportance: metadata?.featureImportance ?? []
      }
    : undefined;

  return (
    <main className="app-shell">
      <header className="app-header">
        <img className="app-icon app-icon-header" src="./app-icon.svg" alt="" aria-hidden="true" />
        <div className="app-title">
          <p className="eyebrow">Real Estate Price Prediction</p>
          <h1>不動産価格予測</h1>
        </div>
      </header>

      {longRangeWarning ? <p className="warning">{longRangeWarning}</p> : null}
      {errorMessage ? <p className="warning">{errorMessage}</p> : null}
      {assetWarnings.map((message) => (
        <p className="warning" key={message}>
          {message}
        </p>
      ))}
      {loadingMessage ? (
        <div className="loading-toast" role="status" aria-live="polite">
          <span className="loading-spinner" aria-hidden="true" />
          <span>{loadingMessage}</span>
        </div>
      ) : null}

      <div className={`layout form-sheet-${formSheetState}`}>
        <PropertyMap lat={form.lat} lon={form.lon} onSelect={handleMapSelect} />
        <div
          ref={sheetStackRef}
          className={`sheet-stack sheet-${formSheetState}`}
          data-testid="prediction-sheet"
        >
          <PredictionSheetHandle
            sheetState={formSheetState}
            onSheetStateChange={setFormSheetState}
          />
          <div className="prediction-workflow">
            <div className="prediction-main-column">
              <PropertyConditionForm
                formRef={formPanelRef}
                value={form}
                onChange={handleFormChange}
                stationOptions={stationOptions}
                stationDistanceSource={stationDistanceSource}
                sheetState={formSheetState}
              />
              <PredictionResultView result={result} />
            </div>
            <div className="prediction-side-column">
              <ForecastControls
                value={form}
                onChange={handleFormChange}
                futureScenario={futureScenario}
                onFutureScenarioChange={setFutureScenario}
                predictionYearRange={predictionYearRange}
              />
              <PriceHistoryChart
                points={chartPoints}
                hasHistory={history.length > 0}
                isArchiveLoaded={isArchiveLoaded}
                isArchiveLoading={isArchiveLoading}
                onLoadArchive={loadArchiveHistory}
                onCloseArchive={closeArchiveHistory}
              />
            </div>
          </div>
          <SupportingInfoTabs
            tabs={[
              {
                id: "facilities",
                label: "商業施設",
                description: "対象エリア周辺のショッピングセンター開業状況を確認できます。",
                content: (
                  <CommercialFacilityCard
                    summary={commercialFacilities}
                    prefecture={form.prefecture}
                    municipality={form.municipality}
                  />
                )
              },
              {
                id: "station",
                label: "駅規模",
                description: "最寄駅の乗降客数や路線数を確認できます。",
                content: <StationScaleCard station={selectedStation} stationName={form.station} />
              },
              {
                id: "hazard",
                label: "災害リスク",
                description: "選択地点の災害リスクに関する参考情報を確認できます。",
                content: <HazardRiskCard latitude={form.lat} longitude={form.lon} />
              },
              {
                id: "model",
                label: "モデル",
                description: "予測に使った条件、モデル評価、モデル全体の特徴量重要度を確認できます。",
                content: <PredictionDetailsPanel summary={predictionSummary} />
              }
            ]}
          />
        </div>
      </div>
    </main>
  );
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
