import type { StationRecord } from "../types/assets";
import { haversineKm } from "../utils/distance";
import { fetchJson } from "./http";

const stationCache = new Map<string, Promise<StationRecord[]>>();
const stationSpatialIndexCache = new WeakMap<StationRecord[], StationSpatialNode | null>();
const WALKING_DISTANCE_METERS_PER_MINUTE = 60;

type Axis = 0 | 1 | 2;

type StationSpatialPoint = {
  coordinates: [number, number, number];
  order: number;
  station: StationRecord;
};

type StationSpatialNode = StationSpatialPoint & {
  axis: Axis;
  left: StationSpatialNode | null;
  right: StationSpatialNode | null;
};

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
  if (stations.length === 0) {
    return null;
  }

  let index = stationSpatialIndexCache.get(stations);
  if (index === undefined) {
    index = buildStationSpatialIndex(
      stations.map((station, order) => ({
        coordinates: toUnitSphere(station.lat, station.lon),
        order,
        station
      }))
    );
    stationSpatialIndexCache.set(stations, index);
  }

  const nearest = findNearestSpatialPoint(index, toUnitSphere(lat, lon));
  if (!nearest) {
    return null;
  }
  return {
    station: nearest.station,
    distanceKm: haversineKm(lat, lon, nearest.station.lat, nearest.station.lon)
  };
}

export function distanceKmToWalkingMinutes(distanceKm: number): number {
  const straightDistanceMeters = distanceKm * 1000;
  return Math.max(1, Math.ceil(straightDistanceMeters / WALKING_DISTANCE_METERS_PER_MINUTE));
}

function toUnitSphere(lat: number, lon: number): [number, number, number] {
  const latRadians = (lat * Math.PI) / 180;
  const lonRadians = (lon * Math.PI) / 180;
  const cosLat = Math.cos(latRadians);
  return [
    cosLat * Math.cos(lonRadians),
    cosLat * Math.sin(lonRadians),
    Math.sin(latRadians)
  ];
}

function buildStationSpatialIndex(
  points: StationSpatialPoint[],
  depth = 0
): StationSpatialNode | null {
  if (points.length === 0) {
    return null;
  }
  const axis = (depth % 3) as Axis;
  points.sort((a, b) => a.coordinates[axis] - b.coordinates[axis]);
  const middle = Math.floor(points.length / 2);
  const point = points[middle];
  return {
    ...point,
    axis,
    left: buildStationSpatialIndex(points.slice(0, middle), depth + 1),
    right: buildStationSpatialIndex(points.slice(middle + 1), depth + 1)
  };
}

function findNearestSpatialPoint(
  root: StationSpatialNode | null,
  target: [number, number, number]
): StationSpatialPoint | null {
  let best: StationSpatialPoint | null = null;
  let bestDistanceSquared = Number.POSITIVE_INFINITY;

  function visit(node: StationSpatialNode | null) {
    if (!node) {
      return;
    }
    const distanceSquared = squaredDistance(node.coordinates, target);
    if (
      distanceSquared < bestDistanceSquared ||
      (distanceSquared === bestDistanceSquared && (!best || node.order < best.order))
    ) {
      best = node;
      bestDistanceSquared = distanceSquared;
    }

    const delta = target[node.axis] - node.coordinates[node.axis];
    const nearBranch = delta < 0 ? node.left : node.right;
    const farBranch = delta < 0 ? node.right : node.left;
    visit(nearBranch);
    if (delta * delta <= bestDistanceSquared) {
      visit(farBranch);
    }
  }

  visit(root);
  return best;
}

function squaredDistance(
  a: [number, number, number],
  b: [number, number, number]
) {
  return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2;
}
