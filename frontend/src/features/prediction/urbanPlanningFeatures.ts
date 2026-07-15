import type { UrbanPlanningArea, UrbanPlanningCollection } from "../../types/assets";

export type UrbanPlanningRequestFields = {
  isCommercialZone: number;
  isResidentialZone: number;
  floorAreaRatio: number;
  buildingCoverageRatio: number;
  hasZoningData: number;
  cityPlanningAreaType: string;
  zoningType: string;
  locationOptimizationArea: string;
};

type AreaGrid = {
  cellSize: number;
  cells: Map<string, number[]>;
};

const EMPTY_URBAN_PLANNING_FIELDS: UrbanPlanningRequestFields = {
  isCommercialZone: 0,
  isResidentialZone: 0,
  floorAreaRatio: 0,
  buildingCoverageRatio: 0,
  hasZoningData: 0,
  cityPlanningAreaType: "unknown",
  zoningType: "unknown",
  locationOptimizationArea: "unknown"
};

const urbanPlanningGridCache = new WeakMap<UrbanPlanningCollection, AreaGrid>();

export function buildUrbanPlanningRequestFields(
  collection: UrbanPlanningCollection | null,
  lat: number | null,
  lon: number | null
): UrbanPlanningRequestFields {
  if (!collection || lat === null || lon === null) {
    return EMPTY_URBAN_PLANNING_FIELDS;
  }

  const matched = findMatchedAreas(collection, lat, lon);
  return buildFieldsFromMatchedAreas(matched);
}

function findMatchedAreas(
  collection: UrbanPlanningCollection,
  lat: number,
  lon: number
): UrbanPlanningArea[] {
  const grid = getAreaGrid(collection);
  const candidateIndexes = getCandidateAreaIndexes(grid, lat, lon);
  return candidateIndexes
    .map((index) => collection.areas[index])
    .filter(
      (area): area is UrbanPlanningArea =>
        Boolean(area) && pointInBbox(lon, lat, area.bbox) && pointInGeometry(lon, lat, area.geometry)
    );
}

function buildFieldsFromMatchedAreas(
  matched: UrbanPlanningArea[]
): UrbanPlanningRequestFields {
  const zoning = firstArea(matched, "zoning");
  const cityPlanning = firstArea(matched, "city_planning_area");
  const locationOptimization = firstArea(matched, "location_optimization");

  if (!zoning && !cityPlanning && !locationOptimization) {
    return EMPTY_URBAN_PLANNING_FIELDS;
  }

  const zoningType = text(zoning?.zoningType || zoning?.areaName) || "unknown";

  return {
    isCommercialZone: zoningType.includes("商業") ? 1 : 0,
    isResidentialZone:
      zoningType.includes("住居") || zoningType.includes("住宅") ? 1 : 0,
    floorAreaRatio: zoning?.floorAreaRatio ?? 0,
    buildingCoverageRatio: zoning?.buildingCoverageRatio ?? 0,
    hasZoningData: zoning ? 1 : 0,
    cityPlanningAreaType: text(cityPlanning?.areaName) || "unknown",
    zoningType,
    locationOptimizationArea: text(locationOptimization?.areaName) || "unknown"
  };
}

function getAreaGrid(collection: UrbanPlanningCollection): AreaGrid {
  const cached = urbanPlanningGridCache.get(collection);
  if (cached) {
    return cached;
  }

  const cellSize = 0.02;
  const cells = new Map<string, number[]>();
  collection.areas.forEach((area, index) => {
    const [minLon, minLat, maxLon, maxLat] = area.bbox;
    const minX = Math.floor(minLon / cellSize);
    const maxX = Math.floor(maxLon / cellSize);
    const minY = Math.floor(minLat / cellSize);
    const maxY = Math.floor(maxLat / cellSize);
    for (let x = minX; x <= maxX; x += 1) {
      for (let y = minY; y <= maxY; y += 1) {
        const key = cellKey(x, y);
        const indexes = cells.get(key);
        if (indexes) {
          indexes.push(index);
        } else {
          cells.set(key, [index]);
        }
      }
    }
  });
  const grid = { cellSize, cells };
  urbanPlanningGridCache.set(collection, grid);
  return grid;
}

function getCandidateAreaIndexes(grid: AreaGrid, lat: number, lon: number): number[] {
  const x = Math.floor(lon / grid.cellSize);
  const y = Math.floor(lat / grid.cellSize);
  return grid.cells.get(cellKey(x, y)) ?? [];
}

function cellKey(x: number, y: number): string {
  return `${x},${y}`;
}

function firstArea(rows: UrbanPlanningArea[], areaType: string): UrbanPlanningArea | null {
  return rows.find((row) => row.areaType === areaType) ?? null;
}

function pointInBbox(
  lon: number,
  lat: number,
  [minLon, minLat, maxLon, maxLat]: [number, number, number, number]
): boolean {
  return minLon <= lon && lon <= maxLon && minLat <= lat && lat <= maxLat;
}

function pointInGeometry(
  lon: number,
  lat: number,
  geometry: UrbanPlanningArea["geometry"]
): boolean {
  const { type, coordinates } = geometry;
  if (type === "Polygon") {
    return pointInPolygon(lon, lat, coordinates);
  }
  if (type === "MultiPolygon" && Array.isArray(coordinates)) {
    return coordinates.some((polygon) => pointInPolygon(lon, lat, polygon));
  }
  return false;
}

function pointInPolygon(lon: number, lat: number, polygon: unknown): boolean {
  if (!Array.isArray(polygon) || polygon.length === 0) {
    return false;
  }
  const [outer, ...holes] = polygon;
  if (!pointInRing(lon, lat, outer)) {
    return false;
  }
  return !holes.some((hole) => pointInRing(lon, lat, hole));
}

function pointInRing(lon: number, lat: number, ring: unknown): boolean {
  if (!Array.isArray(ring) || ring.length < 3) {
    return false;
  }

  let inside = false;
  let previous = ring.at(-1);
  for (const current of ring) {
    if (!isCoordinate(current) || !isCoordinate(previous)) {
      previous = current;
      continue;
    }
    const [x1, y1] = previous;
    const [x2, y2] = current;
    const intersects =
      (y1 > lat) !== (y2 > lat) && lon < ((x2 - x1) * (lat - y1)) / (y2 - y1) + x1;
    if (intersects) {
      inside = !inside;
    }
    previous = current;
  }
  return inside;
}

function isCoordinate(value: unknown): value is [number, number] {
  return (
    Array.isArray(value) &&
    value.length >= 2 &&
    typeof value[0] === "number" &&
    typeof value[1] === "number"
  );
}

function text(value: unknown): string {
  return value === null || value === undefined ? "" : String(value).trim();
}
