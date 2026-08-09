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
import { useMobilePredictionSheet } from "./features/prediction/useMobilePredictionSheet";
import { usePriceHistory } from "./features/prediction/usePriceHistory";
import { usePricePrediction } from "./features/prediction/usePricePrediction";
import { usePropertySelection } from "./features/prediction/usePropertySelection";
import { useRegionAssets } from "./features/prediction/useRegionAssets";
import { StationScaleCard } from "./features/stations/StationScaleCard";
import { OnboardingGuide, useOnboardingGuide } from "./features/onboarding/OnboardingGuide";
import type { PredictionFormState } from "./types/prediction";
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
  const onboarding = useOnboardingGuide();
  const [isLayerPanelOpen, setIsLayerPanelOpen] = useState(false);
  const [form, setForm] = useState<PredictionFormState>(initialForm);
  const [futureScenario, setFutureScenario] = useState<FutureScenario>("base");
  const [errorMessage, setErrorMessage] = useState("");
  const {
    clearPendingMapSelectionScroll,
    formPanelRef,
    formSheetState,
    scrollToFormAfterMapSelection,
    setFormSheetState,
    sheetStackRef
  } = useMobilePredictionSheet();

  const {
    assetStatus,
    assetWarnings,
    closeArchiveHistory,
    commercialFacilities,
    history,
    isArchiveLoaded,
    isArchiveLoading,
    isModelReady,
    landPrices,
    loadArchiveHistory,
    metadata,
    region,
    setStations,
    stations,
    trendSummary,
    urbanPlanning
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
  const inputRangeWarnings = useMemo(
    () => buildInputRangeWarnings(form, metadata?.inputRanges),
    [form, metadata]
  );

  const {
    handleFormChange,
    handleMapSelect,
    isSelectionSupported
  } = usePropertySelection({
    form,
    setForm,
    region,
    setStations,
    clearPredictionState: () => clearPredictionStateRef.current(),
    clearPendingMapSelectionScroll,
    scrollToFormAfterMapSelection,
    setErrorMessage,
  });

  const {
    clearPredictionState,
    explanationDurationMs,
    forecastPoints,
    historyModelAnchor,
    isPredicting,
    predictionFactors,
    result
  } = usePricePrediction({
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
  });
  clearPredictionStateRef.current = clearPredictionState;

  const loadingMessage =
    assetStatus.modelStatus === "loading" && region
      ? "モデルを読み込んでいます"
      : isPredicting
        ? "予測を更新しています"
        : "";

  const { chartPoints, comparableSample } = usePriceHistory({
    forecastPoints,
    form,
    history,
    historyModelAnchor,
    result,
    stations
  });
  const predictionWarnings = useMemo(
    () => [
      ...inputRangeWarnings,
      ...buildComparableSampleWarnings(comparableSample)
    ],
    [comparableSample, inputRangeWarnings]
  );
  const selectedStation = stations.find((station) => station.station_name === form.station);
  const locationSummary = {
    prefecture: form.prefecture,
    municipality: form.municipality,
    station: form.station,
    stationDistance: form.stationDistance
  };
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
        featureImportance: metadata?.featureImportance ?? [],
        segmentEvaluations: buildMatchingSegmentEvaluations(
          metadata?.evaluation?.segments,
          form,
          result?.predictedPrice
        )
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

      {!onboarding.isOpen && !isLayerPanelOpen ? (
        <button className="guide-reopen-button" type="button" onClick={onboarding.reopen}>
          使い方
        </button>
      ) : null}

      {onboarding.isOpen ? <OnboardingGuide onClose={onboarding.close} /> : null}

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
        <PropertyMap
          lat={form.lat}
          lon={form.lon}
          onSelect={handleMapSelect}
          locationSummary={locationSummary}
          stations={stations}
          onLayerPanelOpenChange={(isOpen) => {
            setIsLayerPanelOpen(isOpen);
            if (isOpen) {
              clearPendingMapSelectionScroll();
              setFormSheetState("collapsed");
            }
          }}
        />
        <div
          ref={sheetStackRef}
          className={`sheet-stack sheet-${formSheetState}`}
          data-testid="prediction-sheet"
        >
          <PredictionSheetHandle
            sheetState={formSheetState}
            onSheetStateChange={(state) => {
              clearPendingMapSelectionScroll();
              setFormSheetState(state);
            }}
          />
          <div className="prediction-workflow">
            <div className="prediction-main-column">
              <PropertyConditionForm
                formRef={formPanelRef}
                value={form}
                onChange={handleFormChange}
                sheetState={formSheetState}
              />
              <PredictionResultView
                result={result}
                scopeWarnings={predictionWarnings}
                predictionFactors={predictionFactors}
                explanationDurationMs={explanationDurationMs}
              />
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

type InputRanges = NonNullable<import("./types/assets").ModelMetadata["inputRanges"]>;

export function buildInputRangeWarnings(
  form: PredictionFormState,
  ranges: InputRanges | undefined
): string[] {
  if (!ranges) return [];
  const fields = [
    { key: "area", label: "面積", value: form.area, unit: "㎡" },
    { key: "age", label: "築年数", value: form.age, unit: "年" },
    { key: "stationDistance", label: "駅徒歩", value: form.stationDistance, unit: "分" },
    { key: "transactionYear", label: "予測年", value: form.predictionYear, unit: "年" }
  ] as const;
  return fields.flatMap(({ key, label, value, unit }) => {
    const range = ranges[key];
    if (!range || (value >= range.min && value <= range.max)) return [];
    const suffix = key === "transactionYear"
      ? "過去傾向を使った参考シミュレーションです。"
      : "予測誤差が大きくなる可能性があります。";
    return [`${label}${value}${unit}（学習範囲: ${range.min}〜${range.max}${unit}）。${suffix}`];
  });
}

type ComparableSample = import("./features/prediction/usePriceHistory").ComparableSample;

export function buildComparableSampleWarnings(sample: ComparableSample): string[] {
  if (sample.level === "exact") return [];
  if (sample.level === "area") {
    return [`同じ駅・面積帯の直近データは${sample.count}件です。築年帯を広げた参考値です。`];
  }
  if (sample.level === "station") {
    return [`同じ駅の直近データは${sample.count}件です。類似する面積・築年帯が少ないため、参考値としてご覧ください。`];
  }
  return ["同じ駅の直近データを確認できません。モデル全体の傾向による参考値です。"];
}

type EvaluationSegments = NonNullable<
  NonNullable<import("./types/assets").ModelMetadata["evaluation"]>["segments"]
>;

export function buildMatchingSegmentEvaluations(
  segments: EvaluationSegments | undefined,
  form: PredictionFormState,
  predictedPrice: number | undefined
): PredictionSummary["segmentEvaluations"] {
  if (!segments || predictedPrice === undefined) return [];
  const targets = [
    { key: "price", label: "予測価格帯", matchLabel: selectBandLabel(predictedPrice, [30_000_000, 50_000_000, 80_000_000], ["3000万円未満", "3000〜5000万円", "5000〜8000万円", "8000万円以上"]) },
    { key: "age", label: "築年数帯", matchLabel: selectBandLabel(form.age, [10, 20, 30], ["築10年未満", "築10〜19年", "築20〜29年", "築30年以上"]) },
    { key: "area", label: "面積帯", matchLabel: selectBandLabel(form.area, [40, 60, 80], ["40㎡未満", "40〜59㎡", "60〜79㎡", "80㎡以上"]) },
    { key: "prefecture", label: "都道府県", matchLabel: form.prefecture }
  ] as const;

  return targets.flatMap((target) => {
    const rows = segments.dimensions[target.key] ?? [];
    const row = rows.find((item) => item.label === target.matchLabel);
    if (!row) return [];
    return [{
      dimension: target.label,
      label: row.label,
      count: row.count,
      mae: row.metrics?.mae ?? null,
      mape: row.metrics?.mape ?? null
    }];
  });
}

function selectBandLabel(
  value: number,
  boundaries: readonly number[],
  labels: readonly string[]
): string {
  const index = boundaries.findIndex((boundary) => value < boundary);
  return labels[index === -1 ? boundaries.length : index];
}
