import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import { performance } from "node:perf_hooks";
import { findNearestStation } from "../src/services/stationService";
import type { StationRecord } from "../src/types/assets";
import { haversineKm } from "../src/utils/distance";

const frontendRoot = process.cwd();
const stationDirectory = path.join(frontendRoot, "public", "stations");
const stationFiles = (await readdir(stationDirectory))
  .filter((name) => name.endsWith("_stations.json"))
  .sort();

let checkedQueries = 0;
let largestStations: StationRecord[] = [];
let randomState = 0x5eed1234;

for (const stationFile of stationFiles) {
  const stations = JSON.parse(
    await readFile(path.join(stationDirectory, stationFile), "utf8")
  ) as StationRecord[];
  if (stations.length === 0) {
    continue;
  }
  if (stations.length > largestStations.length) {
    largestStations = stations;
  }

  const latitudes = stations.map((station) => station.lat);
  const longitudes = stations.map((station) => station.lon);
  const minLat = Math.min(...latitudes);
  const maxLat = Math.max(...latitudes);
  const minLon = Math.min(...longitudes);
  const maxLon = Math.max(...longitudes);
  const queries = stations.slice(0, 10).map((station) => [station.lat, station.lon] as const);
  for (let index = 0; index < 110; index += 1) {
    queries.push([
      minLat + nextRandom() * (maxLat - minLat),
      minLon + nextRandom() * (maxLon - minLon)
    ]);
  }

  for (const [lat, lon] of queries) {
    const expected = findNearestStationLinear(stations, lat, lon);
    const actual = findNearestStation(stations, lat, lon);
    assert.equal(actual?.station.station_id, expected?.station.station_id, stationFile);
    assert.ok(Math.abs((actual?.distanceKm ?? 0) - (expected?.distanceKm ?? 0)) < 1e-9);
    checkedQueries += 1;
  }
}

assert.ok(largestStations.length > 0, "駅データが見つかりません");
const benchmarkLatitudes = largestStations.map((station) => station.lat);
const benchmarkLongitudes = largestStations.map((station) => station.lon);
const benchmarkMinLat = Math.min(...benchmarkLatitudes);
const benchmarkMaxLat = Math.max(...benchmarkLatitudes);
const benchmarkMinLon = Math.min(...benchmarkLongitudes);
const benchmarkMaxLon = Math.max(...benchmarkLongitudes);
const benchmarkQueries = Array.from({ length: 5_000 }, () => [
  benchmarkMinLat + nextRandom() * (benchmarkMaxLat - benchmarkMinLat),
  benchmarkMinLon + nextRandom() * (benchmarkMaxLon - benchmarkMinLon)
] as const);
findNearestStation(largestStations, benchmarkQueries[0][0], benchmarkQueries[0][1]);

const linearStartedAt = performance.now();
for (const [lat, lon] of benchmarkQueries) {
  findNearestStationLinear(largestStations, lat, lon);
}
const linearMs = performance.now() - linearStartedAt;

const indexedStartedAt = performance.now();
for (const [lat, lon] of benchmarkQueries) {
  findNearestStation(largestStations, lat, lon);
}
const indexedMs = performance.now() - indexedStartedAt;

console.info(
  JSON.stringify({
    stationFiles: stationFiles.length,
    checkedQueries,
    benchmarkStations: largestStations.length,
    benchmarkQueries: benchmarkQueries.length,
    linearMs: Math.round(linearMs * 10) / 10,
    indexedMs: Math.round(indexedMs * 10) / 10,
    speedup: Math.round((linearMs / indexedMs) * 10) / 10
  })
);

function findNearestStationLinear(stations: StationRecord[], lat: number, lon: number) {
  let nearest: { station: StationRecord; distanceKm: number } | null = null;
  for (const station of stations) {
    const distanceKm = haversineKm(lat, lon, station.lat, station.lon);
    if (!nearest || distanceKm < nearest.distanceKm) {
      nearest = { station, distanceKm };
    }
  }
  return nearest;
}

function nextRandom() {
  randomState = (Math.imul(randomState, 1_664_525) + 1_013_904_223) >>> 0;
  return randomState / 0x1_0000_0000;
}
