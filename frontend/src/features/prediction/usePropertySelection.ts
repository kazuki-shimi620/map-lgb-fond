import { useState, type Dispatch, type SetStateAction } from "react";
import type { StationRecord } from "../../types/assets";
import type { PredictionFormState, SupportedRegion } from "../../types/prediction";
import { reverseGeocode } from "../../services/geocodingService";
import {
  distanceKmToWalkingMinutes,
  findNearestStation,
  loadStations
} from "../../services/stationService";
import { interruptModelPrefetch } from "../model/modelManagerFactory";
import { getRegionFromPrefecture, getStationRegionFromPrefecture } from "../../utils/region";

const MAX_SUPPORTED_STATION_DISTANCE_KM = 30;
const MAP_SELECTION_SCROLL_DELAY_MS = 2000;
const UNSUPPORTED_MAP_SELECTION_MESSAGE =
  "対応エリア外です。離島・海上などは現在対応していません。対応地域内の駅に近い地点を選択してください";

type MapSelectOptions = {
  mapMoveDurationMs?: number;
};

type UsePropertySelectionParams = {
  form: PredictionFormState;
  setForm: Dispatch<SetStateAction<PredictionFormState>>;
  region: SupportedRegion | null;
  setStations: Dispatch<SetStateAction<StationRecord[]>>;
  clearPredictionState: () => void;
  clearPendingMapSelectionScroll: () => void;
  scrollToFormAfterMapSelection: (delayMs: number) => void;
  setErrorMessage: Dispatch<SetStateAction<string>>;
};

export function usePropertySelection({
  form,
  setForm,
  region,
  setStations,
  clearPredictionState,
  clearPendingMapSelectionScroll,
  scrollToFormAfterMapSelection,
  setErrorMessage
}: UsePropertySelectionParams) {
  const [isSelectionSupported, setIsSelectionSupported] = useState(true);
  const [stationDistanceSource, setStationDistanceSource] = useState<"map" | "manual">("manual");

  function rejectMapSelection(message = UNSUPPORTED_MAP_SELECTION_MESSAGE) {
    setIsSelectionSupported(false);
    setStationDistanceSource("manual");
    clearPredictionState();
    setErrorMessage(message);
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
    nextRegion: SupportedRegion | null;
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
    clearPendingMapSelectionScroll();
    setIsSelectionSupported(false);
    clearPredictionState();
    setErrorMessage("");

    if (!isLikelyJapanCoordinate(lat, lon)) {
      rejectMapSelection();
      return;
    }

    setForm((current) => ({ ...current, lat, lon }));

    try {
      const geocode = await reverseGeocode(lat, lon).catch(() => ({
        prefecture: "",
        municipality: ""
      }));
      const geocodedRegion = getRegionFromPrefecture(geocode.prefecture);
      const geocodedStationRegion = getStationRegionFromPrefecture(geocode.prefecture);

      if (!geocode.prefecture || !geocodedRegion || !geocodedStationRegion) {
        rejectMapSelection();
        return;
      }

      const targetStations = await loadStations(geocodedStationRegion);
      const nearest = findNearestStation(targetStations, lat, lon);
      const allowOkinawaMainIsland =
        geocode.prefecture === "沖縄県" && isOkinawaMainIsland(lat, lon);
      if (
        !nearest ||
        (!allowOkinawaMainIsland && nearest.distanceKm > MAX_SUPPORTED_STATION_DISTANCE_KM)
      ) {
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

  function handleFormChange(nextForm: PredictionFormState) {
    if (nextForm.prefecture !== form.prefecture) {
      clearPredictionState();
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

  return {
    handleFormChange,
    handleMapSelect,
    isSelectionSupported,
    stationDistanceSource
  };
}

function isOkinawaMainIsland(lat: number, lon: number) {
  return lat >= 26.0 && lat <= 26.95 && lon >= 127.55 && lon <= 128.4;
}

function isLikelyJapanCoordinate(lat: number, lon: number) {
  return lat >= 20.0 && lat <= 46.5 && lon >= 122.0 && lon <= 154.0;
}
