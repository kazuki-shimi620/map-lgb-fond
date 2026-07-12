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
  ModelMetadata,
  PriceHistoryPoint,
  PriceTrendSummary,
  StationRecord
} from "../../types/assets";
import type { PredictionFormState, StationRegion } from "../../types/prediction";
import { getRegionFromPrefecture, getStationRegionFromPrefecture } from "../../utils/region";

const RECENT_HISTORY_START_YEAR = 2020;

type HistoryModelAnchor = {
  year: number;
  price: number;
};

type UseRegionAssetsParams = {
  prefecture: string;
  setForm: Dispatch<SetStateAction<PredictionFormState>>;
  setHistoryModelAnchor: Dispatch<SetStateAction<HistoryModelAnchor | null>>;
  setErrorMessage: Dispatch<SetStateAction<string>>;
};

export function useRegionAssets({
  prefecture,
  setForm,
  setHistoryModelAnchor,
  setErrorMessage
}: UseRegionAssetsParams) {
  const [history, setHistory] = useState<PriceHistoryPoint[]>([]);
  const [trendSummary, setTrendSummary] = useState<PriceTrendSummary | null>(null);
  const [isArchiveLoaded, setIsArchiveLoaded] = useState(false);
  const [isArchiveLoading, setIsArchiveLoading] = useState(false);
  const [stations, setStations] = useState<StationRecord[]>([]);
  const [commercialFacilities, setCommercialFacilities] = useState<CommercialFacilitySummary | null>(null);
  const [metadata, setMetadata] = useState<ModelMetadata | null>(null);
  const [isModelReady, setIsModelReady] = useState(false);
  const activeStationRegionRef = useRef<StationRegion | null>(null);

  const region = useMemo(() => getRegionFromPrefecture(prefecture), [prefecture]);
  const stationRegion = useMemo(
    () => getStationRegionFromPrefecture(prefecture),
    [prefecture]
  );

  useEffect(() => {
    if (!region || !stationRegion) {
      setIsModelReady(false);
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
          fetchJson<PriceTrendSummary>(
            `./histories/${currentStationRegion}_trend_summary.json`
          ).catch(() => null)
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
  }, [prefecture, region, setErrorMessage, setForm, setHistoryModelAnchor, stationRegion]);

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

  return {
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
    stationRegion,
    stations,
    trendSummary
  };
}
