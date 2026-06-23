import type { StationRecord } from "../types/assets";
import { haversineKm } from "../utils/distance";
import { fetchJson } from "./http";

const stationCache = new Map<string, Promise<StationRecord[]>>();
const WALKING_DISTANCE_METERS_PER_MINUTE = 80;
const ROUTE_DISTANCE_FACTOR = 1.25;

export async function loadStations(region: string): Promise<StationRecord[]> {
  const cached = stationCache.get(region);
  if (cached) {
    return cached;
  }

  const stations = fetchJson<StationRecord[]>(`./stations/${region}_stations.json`);
  stationCache.set(region, stations);
  return stations;
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

export function distanceKmToWalkingMinutes(distanceKm: number): number {
  const routeDistanceMeters = distanceKm * 1000 * ROUTE_DISTANCE_FACTOR;
  return Math.max(1, Math.ceil(routeDistanceMeters / WALKING_DISTANCE_METERS_PER_MINUTE));
}
