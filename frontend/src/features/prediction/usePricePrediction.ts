import { useEffect, useState } from "react";
import { getModelManager } from "../model/modelManagerFactory";
import { buildStationScaleRequestFields } from "../stations/stationScale";
import type {
  PriceHistoryPoint,
  PriceTrend,
  PriceTrendSummary,
  StationRecord
} from "../../types/assets";
import type {
  PredictionFormState,
  PredictionResult,
  SupportedRegion
} from "../../types/prediction";
import type { FutureScenario } from "./PredictionForm";

type HistoryModelAnchor = {
  year: number;
  price: number;
};

type UsePricePredictionParams = {
  form: PredictionFormState;
  futureScenario: FutureScenario;
  history: PriceHistoryPoint[];
  isModelReady: boolean;
  isSelectionSupported: boolean;
  region: SupportedRegion | null;
  setErrorMessage: (message: string) => void;
  stations: StationRecord[];
  trendSummary: PriceTrendSummary | null;
};

export function usePricePrediction({
  form,
  futureScenario,
  history,
  isModelReady,
  isSelectionSupported,
  region,
  setErrorMessage,
  stations,
  trendSummary
}: UsePricePredictionParams) {
  const [result, setResult] = useState<PredictionResult | null>(null);
  const [forecastPoints, setForecastPoints] = useState<PriceHistoryPoint[]>([]);
  const [historyModelAnchor, setHistoryModelAnchor] = useState<HistoryModelAnchor | null>(null);
  const [isPredicting, setIsPredicting] = useState(false);

  function clearPredictionState() {
    setResult(null);
    setForecastPoints([]);
    setHistoryModelAnchor(null);
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
          clearPredictionState();
          setErrorMessage("価格予測に失敗しました");
          setIsPredicting(false);
        }
      }
    }, 250);

    return () => {
      disposed = true;
      window.clearTimeout(timer);
    };
  }, [
    form,
    futureScenario,
    history,
    isModelReady,
    isSelectionSupported,
    region,
    stations,
    trendSummary
  ]);

  return {
    clearPredictionState,
    forecastPoints,
    historyModelAnchor,
    isPredicting,
    result
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
