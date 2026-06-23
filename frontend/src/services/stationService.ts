import type { StationRecord } from "../types/assets";
import { haversineKm } from "../utils/distance";
import { fetchJson } from "./http";

export async function loadStations(region: string): Promise<StationRecord[]> {
  return fetchJson<StationRecord[]>(`./stations/${region}_stations.json`);
}

export function findNearestStation(
  stations: StationRecord[],
  lat: number,
  lon: number
): { station: StationRecord; distanceKm: number } | null {
  let nearest: { station: StationRecord; distanceKm: number } | null = null;

  for (const station of stations) {
    const distanceKm = haversineKm(lat, lon, station.lat, station.lon);
    if (!nearest || distanceKm < nearest.distanceKm) {
      nearest = { station, distanceKm };
    }
  }

  return nearest;
}
