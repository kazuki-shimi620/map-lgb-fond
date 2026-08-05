import { useEffect, useState } from "react";
import { getModelManager } from "../model/modelManagerFactory";
import { buildStationScaleRequestFields } from "../stations/stationScale";
import { buildLandPriceRequestFields } from "./landPriceFeatures";
import { buildUrbanPlanningRequestFields } from "./urbanPlanningFeatures";
import type {
  LandPriceSummary,
  PriceHistoryPoint,
  PriceTrend,
  PriceTrendSummary,
  StationRecord,
  UrbanPlanningCollection
} from "../../types/assets";
import type {
  PredictionFormState,
  PredictionFactor,
  PredictionRequest,
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
  landPrices: LandPriceSummary | null;
  region: SupportedRegion | null;
  setErrorMessage: (message: string) => void;
  stations: StationRecord[];
  trendSummary: PriceTrendSummary | null;
  urbanPlanning: UrbanPlanningCollection | null;
};

export function usePricePrediction({
  form,
  futureScenario,
  history,
  isModelReady,
  isSelectionSupported,
  landPrices,
  region,
  setErrorMessage,
  stations,
  trendSummary,
  urbanPlanning
}: UsePricePredictionParams) {
  const [result, setResult] = useState<PredictionResult | null>(null);
  const [forecastPoints, setForecastPoints] = useState<PriceHistoryPoint[]>([]);
  const [historyModelAnchor, setHistoryModelAnchor] = useState<HistoryModelAnchor | null>(null);
  const [isPredicting, setIsPredicting] = useState(false);
  const [predictionFactors, setPredictionFactors] = useState<PredictionFactor[]>([]);
  const [explanationDurationMs, setExplanationDurationMs] = useState<number | null>(null);

  function clearPredictionState() {
    setResult(null);
    setForecastPoints([]);
    setHistoryModelAnchor(null);
    setPredictionFactors([]);
    setExplanationDurationMs(null);
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
          ...buildStationScaleRequestFields(stations, form.station),
          ...buildLandPriceRequestFields(
            landPrices,
            form.prefecture,
            form.municipality,
            form.predictionYear
          ),
          ...buildUrbanPlanningRequestFields(urbanPlanning, form.lat, form.lon)
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
          const explanationStarted = performance.now();
          const nextFactors = await buildPredictionFactors(
            manager,
            predictionRequest,
            basePrice
          );
          if (disposed) return;
          setResult(nextResult);
          setPredictionFactors(nextFactors);
          setExplanationDurationMs(performance.now() - explanationStarted);
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
    landPrices,
    region,
    stations,
    trendSummary,
    urbanPlanning
  ]);

  return {
    clearPredictionState,
    forecastPoints,
    historyModelAnchor,
    explanationDurationMs,
    isPredicting,
    predictionFactors,
    result
  };
}

async function buildPredictionFactors(
  manager: ReturnType<typeof getModelManager>,
  request: PredictionRequest,
  basePrice: number
): Promise<PredictionFactor[]> {
  const metadata = manager.getMetadata();
  const baselines = metadata?.inputBaselines;
  if (!metadata || !baselines) return [];
  const explanationYear = Math.min(request.predictionYear, metadata.latestTrainingYear);
  const definitions = [
    { key: "area", label: "面積", unit: "㎡" },
    { key: "age", label: "築年数", unit: "年" },
    { key: "stationDistance", label: "駅徒歩", unit: "分" },
    { key: "roomLayout", label: "間取り", unit: "" },
    { key: "buildingType", label: "建物構造", unit: "" }
  ] as const;
  const candidates = definitions.filter(({ key }) => {
    const baseline = baselines[key];
    return baseline !== undefined && baseline !== request[key];
  });
  const factors = await Promise.all(candidates.map(async ({ key, label, unit }) => {
    const baseline = baselines[key] as number | string;
    const alternative = await manager.predict({
      ...request,
      [key]: baseline,
      predictionYear: explanationYear
    });
    return {
      key,
      label,
      currentValue: `${request[key]}${unit}`,
      baselineValue: `${baseline}${unit}`,
      difference: basePrice - alternative.predictedPrice
    };
  }));
  return factors
    .filter((factor) => Math.abs(factor.difference) >= 100_000)
    .sort((left, right) => Math.abs(right.difference) - Math.abs(left.difference));
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
