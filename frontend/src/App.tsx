import { useEffect, useMemo, useRef, useState } from "react";
import { CommercialFacilityCard } from "./features/facilities/CommercialFacilityCard";
import { HazardRiskCard } from "./features/hazard/HazardRiskCard";
import { PropertyMap } from "./features/map/PropertyMap";
import {
  getModelManager,
  interruptModelPrefetch,
  markModelManagerUsed,
  prefetchCapitalRegionModels
} from "./features/model/modelManagerFactory";
import { PriceHistoryChart } from "./features/prediction/PriceHistoryChart";
import {
  PredictionForm,
  PredictionSheetHandle,
  type FutureScenario
} from "./features/prediction/PredictionForm";
import {
  PredictionDetailsPanel,
  PredictionResultView,
  type PredictionSummary
} from "./features/prediction/PredictionResultView";
import { StationScaleCard } from "./features/stations/StationScaleCard";
import { buildStationScaleRequestFields } from "./features/stations/stationScale";
import { reverseGeocode } from "./services/geocodingService";
import { distanceKmToWalkingMinutes, findNearestStation, loadStations } from "./services/stationService";
import type {
  CommercialFacilitySummary,
  ModelMetadata,
  PriceHistoryPoint,
  PriceTrend,
  PriceTrendSummary,
  StationRecord
} from "./types/assets";
import type { PredictionFormState, PredictionResult, StationRegion } from "./types/prediction";
import { fetchJson } from "./services/http";
import { haversineKm } from "./utils/distance";
import { getPrefectureLabel, getRegionFromPrefecture, getStationRegionFromPrefecture } from "./utils/region";

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

const RECENT_HISTORY_START_YEAR = 2020;
const MAX_SUPPORTED_STATION_DISTANCE_KM = 30;
const MAP_SELECTION_SCROLL_DELAY_MS = 2000;
const UNSUPPORTED_MAP_SELECTION_MESSAGE =
  "対応エリア外です。離島・海上などは現在対応していません。対応地域内の駅に近い地点を選択してください";
type MapSelectOptions = {
  mapMoveDurationMs?: number;
};

export function App() {
  const [form, setForm] = useState<PredictionFormState>(initialForm);
  const [result, setResult] = useState<PredictionResult | null>(null);
  const [forecastPoints, setForecastPoints] = useState<PriceHistoryPoint[]>([]);
  const [historyModelAnchor, setHistoryModelAnchor] = useState<{
    year: number;
    price: number;
  } | null>(null);
  const [history, setHistory] = useState<PriceHistoryPoint[]>([]);
  const [trendSummary, setTrendSummary] = useState<PriceTrendSummary | null>(null);
  const [futureScenario, setFutureScenario] = useState<FutureScenario>("base");
  const [isArchiveLoaded, setIsArchiveLoaded] = useState(false);
  const [isArchiveLoading, setIsArchiveLoading] = useState(false);
  const [stations, setStations] = useState<StationRecord[]>([]);
  const [commercialFacilities, setCommercialFacilities] = useState<CommercialFacilitySummary | null>(null);
  const [metadata, setMetadata] = useState<ModelMetadata | null>(null);
  const [isModelReady, setIsModelReady] = useState(false);
  const [isPredicting, setIsPredicting] = useState(false);
  const [isSelectionSupported, setIsSelectionSupported] = useState(true);
  const [stationDistanceSource, setStationDistanceSource] = useState<"map" | "manual">("manual");
  const [formSheetState, setFormSheetState] = useState<"collapsed" | "half" | "open">("collapsed");
  const [errorMessage, setErrorMessage] = useState("");
  const activeStationRegionRef = useRef<StationRegion | null>(null);
  const formPanelRef = useRef<HTMLElement | null>(null);
  const sheetStackRef = useRef<HTMLDivElement | null>(null);
  const scrollAnimationRef = useRef<number | null>(null);
  const mapSelectionScrollTimerRef = useRef<number | null>(null);

  const region = useMemo(() => getRegionFromPrefecture(form.prefecture), [form.prefecture]);
  const stationRegion = useMemo(
    () => getStationRegionFromPrefecture(form.prefecture),
    [form.prefecture]
  );
  const longRangeWarning =
    metadata && form.predictionYear > metadata.latestTrainingYear + 10
      ? "長期予測のため精度は保証できません"
      : "";
  const loadingMessage = !isModelReady && region ? "モデルを読み込んでいます" : isPredicting ? "予測を更新しています" : "";
  const predictionYearRange = useMemo(
    () => ({
      min: metadata?.latestTrainingYear ?? new Date().getFullYear(),
      max: (metadata?.latestTrainingYear ?? new Date().getFullYear()) + 10
    }),
    [metadata]
  );

  useEffect(() => {
    if (!region || !stationRegion) {
      setIsModelReady(false);
      setErrorMessage("未対応地域です");
      return;
    }

    const currentRegion = region;
    const currentStationRegion = stationRegion;
    const currentPrefecture = form.prefecture;
    let disposed = false;
    const manager = getModelManager(currentRegion);
    activeStationRegionRef.current = currentStationRegion;
    setIsModelReady(false);
    setHistory([]);
    setTrendSummary(null);
    setHistoryModelAnchor(null);
    setIsArchiveLoaded(false);
    setIsArchiveLoading(false);
    setErrorMessage("");

    async function loadRegionAssets() {
      try {
        const [nextStations, nextHistory, nextTrendSummary] = await Promise.all([
          loadStations(currentStationRegion),
          fetchJson<PriceHistoryPoint[]>(`./histories/${currentStationRegion}_latest_history.json`),
          fetchJson<PriceTrendSummary>(`./histories/${currentStationRegion}_trend_summary.json`).catch(() => null)
        ]);
        if (!disposed) {
          setStations(nextStations);
          setHistory(nextHistory);
          setTrendSummary(nextTrendSummary);
          setForm((current) =>
            current.prefecture === currentPrefecture && !current.station && nextStations.length > 0
              ? { ...current, station: nextStations[0].station_name }
              : current
          );
        }
      } catch {
        if (!disposed) {
          setErrorMessage("駅マスタまたは価格推移データを読み込めませんでした");
        }
      }

      try {
        await manager.loadAll();
        if (!disposed) {
          markModelManagerUsed(currentRegion);
          setMetadata(manager.getMetadata());
          setIsModelReady(true);
          prefetchCapitalRegionModels(currentRegion);
        }
      } catch {
        if (!disposed) {
          setMetadata(manager.getMetadata());
          setIsModelReady(false);
          setErrorMessage("モデルの読み込みに失敗しました");
        }
      }
    }

    loadRegionAssets();

    return () => {
      disposed = true;
    };
  }, [form.prefecture, region, stationRegion]);

  useEffect(() => {
    return () => {
      if (mapSelectionScrollTimerRef.current !== null) {
        window.clearTimeout(mapSelectionScrollTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    let disposed = false;
    fetchJson<CommercialFacilitySummary>("./facilities/commercial_facilities.json")
      .then((summary) => {
        if (!disposed) {
          setCommercialFacilities(summary);
        }
      })
      .catch(() => {
        if (!disposed) {
          setCommercialFacilities(null);
        }
      });
    return () => {
      disposed = true;
    };
  }, []);

  async function loadArchiveHistory() {
    if (!stationRegion || isArchiveLoaded || isArchiveLoading) {
      return;
    }

    setIsArchiveLoading(true);
    try {
      const archive = await fetchJson<PriceHistoryPoint[]>(
        `./histories/${stationRegion}_archive_history.json`
      );
      if (activeStationRegionRef.current !== stationRegion) {
        return;
      }
      setHistory((current) => [...archive, ...current]);
      setIsArchiveLoaded(true);
    } catch {
      setErrorMessage("過去の価格推移データを読み込めませんでした");
    } finally {
      setIsArchiveLoading(false);
    }
  }

  function closeArchiveHistory() {
    setHistory((current) =>
      current.filter((point) => point.year >= RECENT_HISTORY_START_YEAR)
    );
    setIsArchiveLoaded(false);
  }

  async function loadStationCandidates(targetRegion: StationRegion) {
    return loadStations(targetRegion);
  }

  function clearPredictionState() {
    setResult(null);
    setForecastPoints([]);
    setHistoryModelAnchor(null);
  }

  function rejectMapSelection(message = UNSUPPORTED_MAP_SELECTION_MESSAGE) {
    setIsSelectionSupported(false);
    setStationDistanceSource("manual");
    clearPredictionState();
    setErrorMessage(message);
  }

  function scrollToFormAfterMapSelection(delayMs = MAP_SELECTION_SCROLL_DELAY_MS) {
    if (mapSelectionScrollTimerRef.current !== null) {
      window.clearTimeout(mapSelectionScrollTimerRef.current);
    }

    mapSelectionScrollTimerRef.current = window.setTimeout(() => {
      mapSelectionScrollTimerRef.current = null;
      setFormSheetState("half");
      window.requestAnimationFrame(() => {
        if (window.matchMedia("(max-width: 760px)").matches) {
          sheetStackRef.current?.scrollTo({ top: 0, behavior: "smooth" });
          return;
        }
        if (formPanelRef.current) {
          animateScrollToElement(formPanelRef.current, scrollAnimationRef);
        }
      });
    }, delayMs);
  }

  function clearPendingMapSelectionTimers() {
    if (mapSelectionScrollTimerRef.current !== null) {
      window.clearTimeout(mapSelectionScrollTimerRef.current);
      mapSelectionScrollTimerRef.current = null;
    }
  }

  function applyMapSelection({
    geocode,
    lat,
    lon,
    nearest,
    nextPrefecture,
    targetStations,
    nextRegion,
    scrollDelayMs
  }: {
    geocode: { municipality: string };
    lat: number;
    lon: number;
    nearest: { station: StationRecord; distanceKm: number };
    nextPrefecture: string;
    targetStations: StationRecord[];
    nextRegion: string | null;
    scrollDelayMs: number;
  }) {
    if (nextRegion && nextRegion !== region) {
      setStations(targetStations);
    }

    setIsSelectionSupported(true);
    setStationDistanceSource("map");
    setForm((current) => ({
      ...current,
      prefecture: nextPrefecture || current.prefecture,
      municipality: geocode.municipality || current.municipality,
      station: nearest.station.station_name,
      stationDistance: distanceKmToWalkingMinutes(nearest.distanceKm),
      lat,
      lon
    }));
    scrollToFormAfterMapSelection(scrollDelayMs);
  }

  async function handleMapSelect(lat: number, lon: number, options: MapSelectOptions = {}) {
    const selectionStartedAt = window.performance.now();
    interruptModelPrefetch();
    clearPendingMapSelectionTimers();
    setIsSelectionSupported(false);
    clearPredictionState();
    setErrorMessage("");

    if (!isLikelyJapanCoordinate(lat, lon)) {
      rejectMapSelection();
      return;
    }

    setForm((current) => ({ ...current, lat, lon }));

    try {
      const geocode = await reverseGeocode(lat, lon).catch(() => ({ prefecture: "", municipality: "" }));
      const geocodedRegion = getRegionFromPrefecture(geocode.prefecture);
      const geocodedStationRegion = getStationRegionFromPrefecture(geocode.prefecture);

      if (
        !geocode.prefecture ||
        !geocodedRegion ||
        !geocodedStationRegion
      ) {
        rejectMapSelection();
        return;
      }

      const targetStations = await loadStationCandidates(geocodedStationRegion);
      const nearest = findNearestStation(targetStations, lat, lon);
      const allowOkinawaMainIsland = geocode.prefecture === "沖縄県" && isOkinawaMainIsland(lat, lon);
      if (!nearest || (!allowOkinawaMainIsland && nearest.distanceKm > MAX_SUPPORTED_STATION_DISTANCE_KM)) {
        rejectMapSelection();
        return;
      }

      const nextPrefecture = geocode.prefecture;
      const nextRegion = getRegionFromPrefecture(nextPrefecture) ?? region;
      const elapsedMs = window.performance.now() - selectionStartedAt;
      const remainingMapMoveMs = Math.max(0, (options.mapMoveDurationMs ?? 0) - elapsedMs);
      const scrollDelayMs = remainingMapMoveMs + MAP_SELECTION_SCROLL_DELAY_MS;
      applyMapSelection({
        geocode,
        lat,
        lon,
        nearest,
        nextPrefecture,
        targetStations,
        nextRegion,
        scrollDelayMs
      });
    } catch {
      rejectMapSelection("地域または駅情報の取得に失敗しました。別の地点を選択してください");
    }
  }

  useEffect(() => {
    if (!region) {
      setErrorMessage("未対応地域です");
      return;
    }

    if (!isSelectionSupported) {
      return;
    }

    if (!isModelReady) {
      return;
    }

    let disposed = false;
    setIsPredicting(true);
    const timer = window.setTimeout(async () => {
      try {
        const manager = getModelManager(region);
        const predictionRequest = {
          ...form,
          stationDistance: Math.round(form.stationDistance),
          ...buildStationScaleRequestFields(stations, form.station)
        };
        const {
          result: nextResult,
          forecastPoints: nextForecastPoints,
          basePrice
        } = await predictWithFutureTrend(
          manager,
          predictionRequest,
          history,
          trendSummary,
          futureScenario
        );
        if (!disposed) {
          setResult(nextResult);
          setForecastPoints(nextForecastPoints);
          setHistoryModelAnchor({
            year: manager.getMetadata()?.latestTrainingYear ?? form.predictionYear,
            price: basePrice
          });
          setErrorMessage("");
          setIsPredicting(false);
        }
      } catch {
        if (!disposed) {
          setResult(null);
          setForecastPoints([]);
          setHistoryModelAnchor(null);
          setErrorMessage("価格予測に失敗しました");
          setIsPredicting(false);
        }
      }
    }, 250);

    return () => {
      disposed = true;
      window.clearTimeout(timer);
    };
  }, [form, futureScenario, history, isModelReady, isSelectionSupported, region, trendSummary]);

  function handleFormChange(nextForm: PredictionFormState) {
    if (nextForm.prefecture !== form.prefecture) {
      setResult(null);
      setForecastPoints([]);
      setHistoryModelAnchor(null);
      setStationDistanceSource("manual");
      setForm({
        ...nextForm,
        municipality: "",
        station: "",
        lat: null,
        lon: null
      });
      return;
    }
    if (nextForm.stationDistance !== form.stationDistance) {
      setStationDistanceSource("manual");
    }
    setIsSelectionSupported(true);
    setForm(nextForm);
  }

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
          <PredictionForm
            formRef={formPanelRef}
            value={form}
            onChange={handleFormChange}
            stationOptions={stationOptions}
            futureScenario={futureScenario}
            onFutureScenarioChange={setFutureScenario}
            stationDistanceSource={stationDistanceSource}
            sheetState={formSheetState}
            predictionYearRange={predictionYearRange}
          />
          <PredictionResultView result={result} />
          <PriceHistoryChart
            points={chartPoints}
            hasHistory={history.length > 0}
            isArchiveLoaded={isArchiveLoaded}
            isArchiveLoading={isArchiveLoading}
            onLoadArchive={loadArchiveHistory}
            onCloseArchive={closeArchiveHistory}
          />
          <CommercialFacilityCard
            summary={commercialFacilities}
            prefecture={form.prefecture}
            municipality={form.municipality}
          />
          <StationScaleCard station={selectedStation} stationName={form.station} />
          <HazardRiskCard latitude={form.lat} longitude={form.lon} />
          <PredictionDetailsPanel summary={predictionSummary} />
        </div>
      </div>
    </main>
  );
}

function animateScrollToElement(
  element: HTMLElement,
  animationRef: { current: number | null }
) {
  if (animationRef.current !== null) {
    window.cancelAnimationFrame(animationRef.current);
  }

  const startY = window.scrollY;
  const targetY = startY + element.getBoundingClientRect().top;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    window.scrollTo(0, targetY);
    animationRef.current = null;
    return;
  }

  const distance = targetY - startY;
  const duration = 1000;
  const startTime = performance.now();

  function step(now: number) {
    const progress = Math.min(1, (now - startTime) / duration);
    const eased =
      progress < 0.5
        ? 4 * progress * progress * progress
        : 1 - Math.pow(-2 * progress + 2, 3) / 2;
    window.scrollTo(0, startY + distance * eased);
    if (progress < 1) {
      animationRef.current = window.requestAnimationFrame(step);
    } else {
      animationRef.current = null;
    }
  }

  animationRef.current = window.requestAnimationFrame(step);
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

function isOkinawaMainIsland(lat: number, lon: number) {
  return lat >= 26.0 && lat <= 26.95 && lon >= 127.55 && lon <= 128.4;
}

function isLikelyJapanCoordinate(lat: number, lon: number) {
  return lat >= 20.0 && lat <= 46.5 && lon >= 122.0 && lon <= 154.0;
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

async function predictWithFutureTrend(
  manager: ReturnType<typeof getModelManager>,
  request: PredictionFormState,
  history: PriceHistoryPoint[],
  trendSummary: PriceTrendSummary | null,
  scenario: FutureScenario
) {
  const metadata = manager.getMetadata();
  if (!metadata || request.predictionYear <= metadata.latestTrainingYear) {
    const result = await manager.predict(request);
    return {
      result,
      forecastPoints: [] as PriceHistoryPoint[],
      basePrice: result.predictedPrice
    };
  }

  const baseYear = metadata.latestTrainingYear;
  const baseResult = await manager.predict({ ...request, predictionYear: baseYear });
  const scenarioAnnualRate = buildScenarioAnnualRate(
    selectFutureTrend(trendSummary, request.station),
    scenario
  );
  const annualChange = estimateAnnualPriceChange(
    history,
    request.prefecture,
    request.station,
    baseYear
  );
  const forecastPoints: PriceHistoryPoint[] = [];

  for (let year = baseYear + 1; year <= request.predictionYear; year += 1) {
    const yearsFromBase = year - baseYear;
    forecastPoints.push({
      station: request.station,
      year,
      avg_price: Math.max(
        1000000,
        scenarioAnnualRate === null
          ? baseResult.predictedPrice + annualChange * yearsFromBase
          : baseResult.predictedPrice * Math.pow(1 + scenarioAnnualRate, yearsFromBase)
      )
    });
  }

  const predictedPrice = forecastPoints.at(-1)?.avg_price ?? baseResult.predictedPrice;
  return {
    result: {
      predictedPrice,
      pricePerSquareMeter: request.area > 0 ? predictedPrice / request.area : 0,
      lowerPrice: Math.max(0, predictedPrice - metadata.mae),
      upperPrice: predictedPrice + metadata.mae
    },
    forecastPoints,
    basePrice: baseResult.predictedPrice
  };
}

function selectFutureTrend(
  trendSummary: PriceTrendSummary | null,
  station: string
): PriceTrend | null {
  if (!trendSummary) {
    return null;
  }

  const stationTrend = trendSummary.stationTrends[station];
  if (stationTrend?.annualizedRate !== null && stationTrend?.annualizedRate !== undefined) {
    return stationTrend;
  }

  return trendSummary.regionalTrend.annualizedRate !== null
    ? trendSummary.regionalTrend
    : null;
}

function buildScenarioAnnualRate(trend: PriceTrend | null, scenario: FutureScenario) {
  if (!trend || trend.annualizedRate === null) {
    return null;
  }

  if (scenario === "flat") {
    return 0;
  }

  const width = Math.min(0.015, Math.max(0.01, (trend.volatility ?? 0.02) * 0.5));
  if (scenario === "bear") {
    return trend.annualizedRate - width;
  }
  if (scenario === "bull") {
    return trend.annualizedRate + width;
  }
  return trend.annualizedRate;
}

function estimateAnnualPriceChange(
  history: PriceHistoryPoint[],
  prefecture: string,
  station: string,
  latestTrainingYear: number
) {
  const prefectureHistory = history.filter(
    (point) => point.prefecture === undefined || point.prefecture === prefecture
  );
  const stationPoints = prefectureHistory.filter(
    (point) => point.station === station && point.year <= latestTrainingYear
  );
  const stationTrend = estimateTrendFromPoints(stationPoints);
  if (stationTrend !== null) {
    return stationTrend;
  }

  const yearlyPrices = new Map<number, number[]>();
  for (const point of prefectureHistory) {
    if (point.year > latestTrainingYear) {
      continue;
    }
    yearlyPrices.set(point.year, [...(yearlyPrices.get(point.year) ?? []), point.avg_price]);
  }

  const regionPoints = [...yearlyPrices.entries()].map(([year, prices]) => ({
    station: "__region__",
    year,
    avg_price: prices.reduce((sum, price) => sum + price, 0) / prices.length
  }));

  return estimateTrendFromPoints(regionPoints) ?? 0;
}

function estimateTrendFromPoints(points: PriceHistoryPoint[]) {
  const sortedPoints = [...points].sort((a, b) => a.year - b.year).slice(-4);
  if (sortedPoints.length < 2) {
    return null;
  }

  const deltas: number[] = [];
  for (let index = 1; index < sortedPoints.length; index += 1) {
    deltas.push(sortedPoints[index].avg_price - sortedPoints[index - 1].avg_price);
  }

  return deltas.reduce((sum, delta) => sum + delta, 0) / deltas.length;
}
