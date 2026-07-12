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
import { usePriceHistory } from "./features/prediction/usePriceHistory";
import { usePricePrediction } from "./features/prediction/usePricePrediction";
import { usePropertySelection } from "./features/prediction/usePropertySelection";
import { useRegionAssets } from "./features/prediction/useRegionAssets";
import { StationScaleCard } from "./features/stations/StationScaleCard";
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

  const { chartPoints } = usePriceHistory({
    forecastPoints,
    form,
    history,
    historyModelAnchor,
    result,
    stations
  });
  const stationOptions = stations.map((station) => station.station_name);
  const selectedStation = stations.find((station) => station.station_name === form.station);
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
