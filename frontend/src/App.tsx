import { useEffect, useMemo, useState } from "react";
import { PropertyMap } from "./features/map/PropertyMap";
import { getModelManager } from "./features/model/modelManagerFactory";
import { PriceHistoryChart } from "./features/prediction/PriceHistoryChart";
import { PredictionForm, PredictionYearControl } from "./features/prediction/PredictionForm";
import { PredictionResultView } from "./features/prediction/PredictionResultView";
import { reverseGeocode } from "./services/geocodingService";
import { distanceKmToWalkingMinutes, findNearestStation, loadStations } from "./services/stationService";
import type { ModelMetadata, PriceHistoryPoint, StationRecord } from "./types/assets";
import type { PredictionFormState, PredictionResult, SupportedRegion } from "./types/prediction";
import { fetchJson } from "./services/http";
import { getPrefectureLabel, getRegionFromPrefecture, supportedRegions } from "./utils/region";

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
  lat: null,
  lon: null
};

export function App() {
  const [form, setForm] = useState<PredictionFormState>(initialForm);
  const [result, setResult] = useState<PredictionResult | null>(null);
  const [forecastPoints, setForecastPoints] = useState<PriceHistoryPoint[]>([]);
  const [history, setHistory] = useState<PriceHistoryPoint[]>([]);
  const [stations, setStations] = useState<StationRecord[]>([]);
  const [metadata, setMetadata] = useState<ModelMetadata | null>(null);
  const [isModelReady, setIsModelReady] = useState(false);
  const [isPredicting, setIsPredicting] = useState(false);
  const [isSelectionSupported, setIsSelectionSupported] = useState(true);
  const [stationDistanceSource, setStationDistanceSource] = useState<"map" | "manual">("manual");
  const [formSheetState, setFormSheetState] = useState<"collapsed" | "open">("collapsed");
  const [errorMessage, setErrorMessage] = useState("");

  const region = useMemo(() => getRegionFromPrefecture(form.prefecture), [form.prefecture]);
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
    if (!region) {
      setIsModelReady(false);
      setErrorMessage("未対応地域です");
      return;
    }

    const currentRegion = region;
    let disposed = false;
    const manager = getModelManager(currentRegion);
    setIsModelReady(false);
    setErrorMessage("");

    async function loadRegionAssets() {
      try {
        const [nextStations, nextHistory] = await Promise.all([
          loadStations(currentRegion),
          fetchJson<PriceHistoryPoint[]>(`./histories/${currentRegion}_latest_history.json`)
        ]);
        if (!disposed) {
          setStations(nextStations);
          setHistory(nextHistory);
        }
      } catch {
        if (!disposed) {
          setErrorMessage("駅マスタまたは価格推移データを読み込めませんでした");
        }
      }

      try {
        await manager.loadAll();
        if (!disposed) {
          setMetadata(manager.getMetadata());
          setIsModelReady(true);
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
  }, [region]);

  async function loadStationCandidates(targetRegion: SupportedRegion | null) {
    if (targetRegion) {
      const targetStations = await loadStations(targetRegion);
      return targetStations;
    }

    const allStationGroups = await Promise.all(supportedRegions.map((nextRegion) => loadStations(nextRegion)));
    return allStationGroups.flat();
  }

  async function handleMapSelect(lat: number, lon: number) {
    setFormSheetState("open");
    setForm((current) => ({ ...current, lat, lon }));

    try {
      const geocode = await reverseGeocode(lat, lon).catch(() => ({ prefecture: "", municipality: "" }));
      const geocodedRegion = getRegionFromPrefecture(geocode.prefecture);

      if (geocode.prefecture && !geocodedRegion) {
        setIsSelectionSupported(false);
        setResult(null);
        setForecastPoints([]);
        setErrorMessage(`${geocode.prefecture}は未対応地域です。現在は東京都、埼玉県、千葉県、神奈川県に対応しています。`);
        return;
      }

      const targetStations = await loadStationCandidates(null);
      const nearest = findNearestStation(targetStations, lat, lon);
      const stationRegion = nearest ? getRegionFromPrefecture(nearest.station.prefecture) : null;
      const nextRegion = geocodedRegion ?? stationRegion ?? region;
      const nextPrefecture =
        (geocodedRegion ? geocode.prefecture : "") || nearest?.station.prefecture || currentPrefectureFromRegion(nextRegion);

      if (nextRegion && nextRegion !== region) {
        setStations(await loadStations(nextRegion));
      }

      setIsSelectionSupported(true);
      setStationDistanceSource(nearest ? "map" : "manual");
      setForm((current) => ({
        ...current,
        prefecture: nextPrefecture || current.prefecture,
        municipality: geocode.municipality || current.municipality,
        station: nearest?.station.station_name ?? current.station,
        stationDistance: nearest ? distanceKmToWalkingMinutes(nearest.distanceKm) : current.stationDistance,
        lat,
        lon
      }));
    } catch {
      setErrorMessage("地域または駅情報の取得に失敗しました。フォームを手入力してください");
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
          stationDistance: Math.round(form.stationDistance)
        };
        const { result: nextResult, forecastPoints: nextForecastPoints } = await predictWithFutureTrend(
          manager,
          predictionRequest,
          history
        );
        if (!disposed) {
          setResult(nextResult);
          setForecastPoints(nextForecastPoints);
          setErrorMessage("");
          setIsPredicting(false);
        }
      } catch {
        if (!disposed) {
          setResult(null);
          setForecastPoints([]);
          setErrorMessage("価格予測に失敗しました");
          setIsPredicting(false);
        }
      }
    }, 250);

    return () => {
      disposed = true;
      window.clearTimeout(timer);
    };
  }, [form, history, isModelReady, isSelectionSupported, region]);

  function handleFormChange(nextForm: PredictionFormState) {
    if (nextForm.stationDistance !== form.stationDistance) {
      setStationDistanceSource("manual");
    }
    setIsSelectionSupported(true);
    setForm(nextForm);
  }

  const stationOptions = stations.map((station) => station.station_name);
  const visibleHistory = history.filter((point) => point.station === form.station);
  const chartPoints = buildChartPoints(visibleHistory, forecastPoints, result, form.station, form.predictionYear);

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
        <PredictionForm
          value={form}
          onChange={handleFormChange}
          stationOptions={stationOptions}
          stationDistanceSource={stationDistanceSource}
          sheetState={formSheetState}
          onSheetStateChange={setFormSheetState}
          predictionYearRange={predictionYearRange}
        />
        <PredictionResultView
          result={result}
          summary={
            region
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
              : undefined
          }
        />
        <section className="panel prediction-year-panel" aria-label="予測年シミュレーション">
          <PredictionYearControl
            className="desktop-prediction-year"
            value={form.predictionYear}
            onChange={(predictionYear) => handleFormChange({ ...form, predictionYear })}
            predictionYearRange={predictionYearRange}
          />
        </section>
        <PriceHistoryChart points={chartPoints} />
      </div>
    </main>
  );
}

function currentPrefectureFromRegion(region: SupportedRegion | null) {
  return region ? getPrefectureLabel(region) : "";
}

function buildChartPoints(
  history: PriceHistoryPoint[],
  forecastPoints: PriceHistoryPoint[],
  result: PredictionResult | null,
  station: string,
  predictionYear: number
) {
  const sortedHistory = [...history]
    .map((point) => ({ ...point, kind: "actual" as const }))
    .sort((a, b) => a.year - b.year);
  if (!result) {
    return sortedHistory;
  }

  const existingYears = new Set(sortedHistory.map((point) => point.year));
  const missingForecasts = forecastPoints
    .filter((point) => !existingYears.has(point.year))
    .map((point) => ({ ...point, kind: "forecast" as const }));

  if (!existingYears.has(predictionYear) && !missingForecasts.some((point) => point.year === predictionYear)) {
    missingForecasts.push({
      station,
      year: predictionYear,
      avg_price: result.predictedPrice,
      kind: "forecast"
    });
  }

  return [...sortedHistory, ...missingForecasts].sort((a, b) => a.year - b.year);
}

async function predictWithFutureTrend(
  manager: ReturnType<typeof getModelManager>,
  request: PredictionFormState,
  history: PriceHistoryPoint[]
) {
  const metadata = manager.getMetadata();
  if (!metadata || request.predictionYear <= metadata.latestTrainingYear) {
    return {
      result: await manager.predict(request),
      forecastPoints: []
    };
  }

  const baseYear = metadata.latestTrainingYear;
  const baseResult = await manager.predict({ ...request, predictionYear: baseYear });
  const annualChange = estimateAnnualPriceChange(history, request.station, baseYear);
  const forecastPoints: PriceHistoryPoint[] = [];

  for (let year = baseYear + 1; year <= request.predictionYear; year += 1) {
    forecastPoints.push({
      station: request.station,
      year,
      avg_price: Math.max(1000000, baseResult.predictedPrice + annualChange * (year - baseYear))
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
    forecastPoints
  };
}

function estimateAnnualPriceChange(history: PriceHistoryPoint[], station: string, latestTrainingYear: number) {
  const stationPoints = history.filter((point) => point.station === station && point.year <= latestTrainingYear);
  const stationTrend = estimateTrendFromPoints(stationPoints);
  if (stationTrend !== null) {
    return stationTrend;
  }

  const yearlyPrices = new Map<number, number[]>();
  for (const point of history) {
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
