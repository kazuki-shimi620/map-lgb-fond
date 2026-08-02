import { useEffect, useMemo, useRef, useState, type Dispatch, type SetStateAction } from "react";
import {
  getModelManager,
  markModelManagerUsed,
  prefetchCapitalRegionModels
} from "../model/modelManagerFactory";
import { loadStations } from "../../services/stationService";
import { fetchJson } from "../../services/http";
import type {
  CommercialFacilitySummary,
  LandPriceSummary,
  ModelMetadata,
  PriceHistoryPoint,
  PriceTrendSummary,
  StationRecord,
  UrbanPlanningCollection
} from "../../types/assets";
import type { PredictionFormState, StationRegion } from "../../types/prediction";
import { getRegionFromPrefecture, getStationRegionFromPrefecture } from "../../utils/region";
import { loadLandPriceSummary } from "../../services/landPriceService";
import { loadUrbanPlanningCollection } from "../../services/urbanPlanningService";
import { scheduleIdleTask } from "../../utils/idleTask";

const RECENT_HISTORY_START_YEAR = 2020;
type AssetStatus = "idle" | "loading" | "ready" | "error";
const URBAN_PLANNING_FEATURE_NAMES = new Set([
  "is_commercial_zone",
  "is_residential_zone",
  "floor_area_ratio",
  "building_coverage_ratio",
  "has_zoning_data",
  "city_planning_area_type",
  "zoning_type",
  "location_optimization_area"
]);

type UseRegionAssetsParams = {
  prefecture: string;
  setForm: Dispatch<SetStateAction<PredictionFormState>>;
  setErrorMessage: Dispatch<SetStateAction<string>>;
};

export function useRegionAssets({
  prefecture,
  setForm,
  setErrorMessage
}: UseRegionAssetsParams) {
  const [history, setHistory] = useState<PriceHistoryPoint[]>([]);
  const [trendSummary, setTrendSummary] = useState<PriceTrendSummary | null>(null);
  const [isArchiveLoaded, setIsArchiveLoaded] = useState(false);
  const [isArchiveLoading, setIsArchiveLoading] = useState(false);
  const [stations, setStations] = useState<StationRecord[]>([]);
  const [commercialFacilities, setCommercialFacilities] = useState<CommercialFacilitySummary | null>(null);
  const [landPrices, setLandPrices] = useState<LandPriceSummary | null>(null);
  const [urbanPlanning, setUrbanPlanning] = useState<UrbanPlanningCollection | null>(null);
  const [metadata, setMetadata] = useState<ModelMetadata | null>(null);
  const [isModelReady, setIsModelReady] = useState(false);
  const [modelStatus, setModelStatus] = useState<AssetStatus>("idle");
  const [stationStatus, setStationStatus] = useState<AssetStatus>("idle");
  const [historyStatus, setHistoryStatus] = useState<AssetStatus>("idle");
  const [facilityStatus, setFacilityStatus] = useState<AssetStatus>("idle");
  const [landPriceStatus, setLandPriceStatus] = useState<AssetStatus>("idle");
  const [urbanPlanningStatus, setUrbanPlanningStatus] = useState<AssetStatus>("idle");
  const hazardStatus: AssetStatus = "ready";
  const activeStationRegionRef = useRef<StationRegion | null>(null);

  const region = useMemo(() => getRegionFromPrefecture(prefecture), [prefecture]);
  const stationRegion = useMemo(
    () => getStationRegionFromPrefecture(prefecture),
    [prefecture]
  );

  useEffect(() => {
    if (!region || !stationRegion) {
      setIsModelReady(false);
      setModelStatus("error");
      setStationStatus("error");
      setHistoryStatus("error");
      setErrorMessage("未対応地域です");
      return;
    }

    const currentRegion = region;
    const currentStationRegion = stationRegion;
    const currentPrefecture = prefecture;
    let disposed = false;
    const manager = getModelManager(currentRegion);
    activeStationRegionRef.current = currentStationRegion;
    setIsModelReady(false);
    setModelStatus("loading");
    setStationStatus("loading");
    setHistoryStatus("loading");
    setHistory([]);
    setTrendSummary(null);
    setIsArchiveLoaded(false);
    setIsArchiveLoading(false);
    setErrorMessage("");

    async function loadRegionAssets() {
      try {
        const nextStations = await loadStations(currentStationRegion);
        if (!disposed) {
          setStations(nextStations);
          setStationStatus("ready");
          setForm((current) =>
            current.prefecture === currentPrefecture && !current.station && nextStations.length > 0
              ? { ...current, station: nextStations[0].station_name }
              : current
          );
        }
      } catch {
        if (!disposed) {
          setStations([]);
          setStationStatus("error");
        }
      }

      try {
        const [nextHistory, nextTrendSummary] = await Promise.all([
          fetchJson<PriceHistoryPoint[]>(`./histories/${currentStationRegion}_latest_history.json`),
          fetchJson<PriceTrendSummary>(
            `./histories/${currentStationRegion}_trend_summary.json`
          ).catch(() => null)
        ]);
        if (!disposed) {
          setHistory(nextHistory);
          setTrendSummary(nextTrendSummary);
          setHistoryStatus("ready");
        }
      } catch {
        if (!disposed) {
          setHistory([]);
          setTrendSummary(null);
          setHistoryStatus("error");
        }
      }

      try {
        await manager.loadAll();
        if (!disposed) {
          markModelManagerUsed(currentRegion);
          setMetadata(manager.getMetadata());
          setIsModelReady(true);
          setModelStatus("ready");
          prefetchCapitalRegionModels(currentRegion);
        }
      } catch {
        if (!disposed) {
          setMetadata(manager.getMetadata());
          setIsModelReady(false);
          setModelStatus("error");
          setErrorMessage("モデルの読み込みに失敗しました");
        }
      }
    }

    loadRegionAssets();

    return () => {
      disposed = true;
    };
  }, [prefecture, region, setErrorMessage, setForm, stationRegion]);

  useEffect(() => {
    let disposed = false;
    setFacilityStatus("loading");
    setLandPriceStatus("loading");
    const cancelLoad = scheduleIdleTask(() => {
      fetchJson<CommercialFacilitySummary>("./facilities/commercial_facilities.json")
        .then((summary) => {
          if (!disposed) {
            setCommercialFacilities(summary);
            setFacilityStatus("ready");
          }
        })
        .catch(() => {
          if (!disposed) {
            setCommercialFacilities(null);
            setFacilityStatus("error");
          }
        });
      loadLandPriceSummary()
        .then((summary) => {
          if (!disposed) {
            setLandPrices(summary);
            setLandPriceStatus("ready");
          }
        })
        .catch(() => {
          if (!disposed) {
            setLandPrices(null);
            setLandPriceStatus("error");
          }
        });
    }, 2000);
    return () => {
      disposed = true;
      cancelLoad();
    };
  }, []);

  useEffect(() => {
    if (!metadata || !modelNeedsUrbanPlanning(metadata)) {
      setUrbanPlanning(null);
      setUrbanPlanningStatus("idle");
      return;
    }

    let disposed = false;
    setUrbanPlanningStatus("loading");
    loadUrbanPlanningCollection()
      .then((collection) => {
        if (!disposed) {
          setUrbanPlanning(collection);
          setUrbanPlanningStatus("ready");
        }
      })
      .catch(() => {
        if (!disposed) {
          setUrbanPlanning(null);
          setUrbanPlanningStatus("error");
        }
      });
    return () => {
      disposed = true;
    };
  }, [metadata]);

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

  return {
    assetStatus: {
      facilityStatus,
      hazardStatus,
      historyStatus,
      landPriceStatus,
      modelStatus,
      stationStatus,
      urbanPlanningStatus
    },
    assetWarnings: buildAssetWarnings({
      facilityStatus,
      historyStatus,
      stationStatus,
      urbanPlanningStatus
    }),
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
    stationRegion,
    stations,
    trendSummary,
    urbanPlanning
  };
}

function modelNeedsUrbanPlanning(metadata: ModelMetadata): boolean {
  return metadata.featureOrder.some((feature) => URBAN_PLANNING_FEATURE_NAMES.has(feature));
}

function buildAssetWarnings({
  facilityStatus,
  historyStatus,
  stationStatus,
  urbanPlanningStatus
}: {
  facilityStatus: AssetStatus;
  historyStatus: AssetStatus;
  stationStatus: AssetStatus;
  urbanPlanningStatus: AssetStatus;
}) {
  return [
    stationStatus === "error"
      ? "駅マスタを読み込めませんでした。地図選択時の最寄駅・駅徒歩の自動更新は利用できません。"
      : null,
    historyStatus === "error"
      ? "価格推移データを読み込めませんでした。価格予測は利用できます。"
      : null,
    facilityStatus === "error"
      ? "商業施設データを読み込めませんでした。価格予測は利用できます。"
      : null,
    urbanPlanningStatus === "error"
      ? "用途地域データを読み込めませんでした。用途地域特徴量は既定値で予測します。"
      : null
  ].filter((message): message is string => message !== null);
}
