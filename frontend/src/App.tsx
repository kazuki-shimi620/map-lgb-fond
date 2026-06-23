import { useEffect, useMemo, useState } from "react";
import { PropertyMap } from "./features/map/PropertyMap";
import { getModelManager } from "./features/model/modelManagerFactory";
import { PriceHistoryChart } from "./features/prediction/PriceHistoryChart";
import { PredictionForm } from "./features/prediction/PredictionForm";
import { PredictionResultView } from "./features/prediction/PredictionResultView";
import { reverseGeocode } from "./services/geocodingService";
import { findNearestStation, loadStations } from "./services/stationService";
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
  buildingType: "RC",
  predictionYear: new Date().getFullYear(),
  lat: null,
  lon: null
};

export function App() {
  const [form, setForm] = useState<PredictionFormState>(initialForm);
  const [result, setResult] = useState<PredictionResult | null>(null);
  const [history, setHistory] = useState<PriceHistoryPoint[]>([]);
  const [stations, setStations] = useState<StationRecord[]>([]);
  const [metadata, setMetadata] = useState<ModelMetadata | null>(null);
  const [status, setStatus] = useState("モデルとメタデータを読み込んでいます");
  const [isPredicting, setIsPredicting] = useState(false);

  const region = useMemo(() => getRegionFromPrefecture(form.prefecture), [form.prefecture]);
  const longRangeWarning =
    metadata && form.predictionYear > metadata.latestTrainingYear + 10
      ? "長期予測のため精度は保証できません"
      : "";

  useEffect(() => {
    if (!region) {
      setStatus("未対応地域です");
      return;
    }

    const currentRegion = region;
    let disposed = false;
    const manager = getModelManager(currentRegion);

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
          setStatus("駅マスタまたは価格推移データを読み込めませんでした");
        }
      }

      try {
        await manager.loadAll();
        if (!disposed) {
          setMetadata(manager.getMetadata());
          setStatus(manager.isFallbackMode() ? "サンプル予測できます" : "予測できます");
        }
      } catch {
        if (!disposed) {
          setMetadata(manager.getMetadata());
          setStatus("モデルの読み込みに失敗しました");
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
    setForm((current) => ({ ...current, lat, lon }));

    try {
      const geocode = await reverseGeocode(lat, lon).catch(() => ({ prefecture: "", municipality: "" }));
      const geocodedRegion = getRegionFromPrefecture(geocode.prefecture);
      const targetStations = await loadStationCandidates(null);
      const nearest = findNearestStation(targetStations, lat, lon);
      const stationRegion = nearest ? getRegionFromPrefecture(nearest.station.prefecture) : null;
      const nextRegion = geocodedRegion ?? stationRegion ?? region;
      const nextPrefecture =
        (geocodedRegion ? geocode.prefecture : "") || nearest?.station.prefecture || currentPrefectureFromRegion(nextRegion);

      if (nextRegion && nextRegion !== region) {
        setStations(await loadStations(nextRegion));
      }

      setForm((current) => ({
        ...current,
        prefecture: nextPrefecture || current.prefecture,
        municipality: geocode.municipality || current.municipality,
        station: nearest?.station.station_name ?? current.station,
        stationDistance: nearest ? Math.round(nearest.distanceKm * 10) / 10 : current.stationDistance,
        lat,
        lon
      }));
    } catch {
      setStatus("地域または駅情報の取得に失敗しました。フォームを手入力してください");
    }
  }

  async function handlePredict() {
    if (!region) {
      setStatus("未対応地域です");
      return;
    }

    setIsPredicting(true);
    setStatus("予測中です");

    try {
      const manager = getModelManager(region);
      const predictionRequest = {
        ...form,
        stationDistance: Math.round(form.stationDistance)
      };
      const nextResult = await manager.predict(predictionRequest);
      setResult(nextResult);
      setStatus("予測しました");
    } catch {
      setResult(null);
      setStatus("価格予測に失敗しました");
    } finally {
      setIsPredicting(false);
    }
  }

  const stationOptions = stations.map((station) => station.station_name);
  const visibleHistory = history.filter((point) => point.station === form.station);
  const chartPoints = buildChartPoints(visibleHistory, result, form.station, form.predictionYear);

  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">Real Estate Price Prediction</p>
          <h1>不動産価格予測</h1>
        </div>
        <p className="status">{status}</p>
      </header>

      {longRangeWarning ? <p className="warning">{longRangeWarning}</p> : null}

      <div className="layout">
        <PropertyMap lat={form.lat} lon={form.lon} onSelect={handleMapSelect} />
        <PredictionForm
          value={form}
          onChange={setForm}
          onSubmit={handlePredict}
          stationOptions={stationOptions}
          disabled={isPredicting}
        />
        <PredictionResultView result={result} />
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
  result: PredictionResult | null,
  station: string,
  predictionYear: number
) {
  const sortedHistory = [...history].sort((a, b) => a.year - b.year);
  if (!result) {
    return sortedHistory;
  }

  const existingYears = new Set(sortedHistory.map((point) => point.year));
  const lastPoint = sortedHistory.at(-1);
  const startYear = lastPoint ? lastPoint.year + 1 : predictionYear;
  const startPrice = lastPoint?.avg_price ?? result.predictedPrice;
  const missingForecasts: PriceHistoryPoint[] = [];

  for (let year = startYear; year <= predictionYear; year += 1) {
    if (existingYears.has(year)) {
      continue;
    }

    const totalSteps = Math.max(predictionYear - startYear + 1, 1);
    const currentStep = year - startYear + 1;
    const progress = currentStep / totalSteps;
    missingForecasts.push({
      station,
      year,
      avg_price: startPrice + (result.predictedPrice - startPrice) * progress
    });
  }

  return [...sortedHistory, ...missingForecasts].sort((a, b) => a.year - b.year);
}
