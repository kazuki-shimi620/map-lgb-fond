import type { NearbyFacilityPoint } from "../../types/assets";

const CELL_SIZE_DEGREES = 0.25;

export type FacilityBounds = {
  north: number;
  south: number;
  east: number;
  west: number;
};

export type FacilitySpatialIndex = {
  cells: Map<string, NearbyFacilityPoint[]>;
  facilities: NearbyFacilityPoint[];
};

function cellCoordinate(value: number) {
  return Math.floor(value / CELL_SIZE_DEGREES);
}

function cellKey(latCell: number, lonCell: number) {
  return `${latCell}:${lonCell}`;
}

export function buildFacilitySpatialIndex(
  facilities: NearbyFacilityPoint[]
): FacilitySpatialIndex {
  const cells = new Map<string, NearbyFacilityPoint[]>();
  for (const facility of facilities) {
    const key = cellKey(cellCoordinate(facility.lat), cellCoordinate(facility.lon));
    const cell = cells.get(key);
    if (cell) {
      cell.push(facility);
    } else {
      cells.set(key, [facility]);
    }
  }
  return { cells, facilities };
}

export function queryFacilitySpatialIndex(
  index: FacilitySpatialIndex,
  bounds: FacilityBounds
): NearbyFacilityPoint[] {
  const latStart = cellCoordinate(bounds.south);
  const latEnd = cellCoordinate(bounds.north);
  const longitudeRanges =
    bounds.west <= bounds.east
      ? [[bounds.west, bounds.east]]
      : [[bounds.west, 180], [-180, bounds.east]];
  const estimatedCellCount = longitudeRanges.reduce((total, [west, east]) => {
    return total + (latEnd - latStart + 1) * (cellCoordinate(east) - cellCoordinate(west) + 1);
  }, 0);

  if (estimatedCellCount > index.facilities.length / 2) {
    return index.facilities.filter((facility) => isInBounds(facility, bounds));
  }

  const candidates: NearbyFacilityPoint[] = [];
  for (let latCell = latStart; latCell <= latEnd; latCell += 1) {
    for (const [west, east] of longitudeRanges) {
      const lonStart = cellCoordinate(west);
      const lonEnd = cellCoordinate(east);
      for (let lonCell = lonStart; lonCell <= lonEnd; lonCell += 1) {
        candidates.push(...(index.cells.get(cellKey(latCell, lonCell)) ?? []));
      }
    }
  }
  return candidates.filter((facility) => isInBounds(facility, bounds));
}

function isInBounds(facility: NearbyFacilityPoint, bounds: FacilityBounds) {
  const longitudeMatches =
    bounds.west <= bounds.east
      ? facility.lon >= bounds.west && facility.lon <= bounds.east
      : facility.lon >= bounds.west || facility.lon <= bounds.east;
  return facility.lat >= bounds.south && facility.lat <= bounds.north && longitudeMatches;
}
