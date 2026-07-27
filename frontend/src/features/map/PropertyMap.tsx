import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { CircleMarker, MapContainer, Marker, TileLayer, Tooltip, useMap, useMapEvents } from "react-leaflet";
import { Icon, type LatLngExpression } from "leaflet";
import markerIcon2xUrl from "leaflet/dist/images/marker-icon-2x.png";
import markerIconUrl from "leaflet/dist/images/marker-icon.png";
import markerShadowUrl from "leaflet/dist/images/marker-shadow.png";
import { searchPlace } from "../../services/geocodingService";
import type {
  NearbyFacilityCategoryId,
  NearbyFacilityCollection,
  NearbyFacilityPoint
} from "../../types/assets";

type HazardLayerDefinition = {
  id: string;
  name: string;
  type: "raster";
  tileUrl: string | null;
  portalUrl: string;
  minZoom: number;
  maxZoom: number;
  defaultOpacity: number;
  enabled: boolean;
  legendLabel: string;
};

type HazardLayerConfig = {
  source: {
    name: string;
    url: string;
    dataCopyrightUrl: string;
    attribution: string;
  };
  disclaimer: string;
  layers: HazardLayerDefinition[];
};

type Props = {
  lat: number | null;
  lon: number | null;
  onSelect: (lat: number, lon: number, options?: { mapMoveDurationMs?: number }) => void;
  locationSummary?: {
    prefecture: string;
    municipality: string;
    station: string;
    stationDistance: number;
  };
};

const SEARCH_FLY_TO_DURATION_MS = 800;
const MAX_VISIBLE_FACILITY_MARKERS = 1200;

type MapViewport = {
  north: number;
  south: number;
  east: number;
  west: number;
  centerLat: number;
  centerLon: number;
};

const propertyMarkerIcon = new Icon({
  iconUrl: markerIconUrl,
  iconRetinaUrl: markerIcon2xUrl,
  shadowUrl: markerShadowUrl,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
});

function ClickHandler({ onSelect }: Pick<Props, "onSelect">) {
  useMapEvents({
    click(event) {
      onSelect(event.latlng.lat, event.latlng.lng);
    }
  });

  return null;
}

function MapMover({ center }: { center: LatLngExpression | null }) {
  const map = useMap();

  useEffect(() => {
    if (center) {
      map.flyTo(center, 12, { duration: 0.8 });
    }
  }, [center, map]);

  return null;
}

function ViewportTracker({ onChange }: { onChange: (viewport: MapViewport) => void }) {
  const map = useMap();

  const updateViewport = useCallback(() => {
    const bounds = map.getBounds();
    const center = map.getCenter();
    onChange({
      north: bounds.getNorth(),
      south: bounds.getSouth(),
      east: bounds.getEast(),
      west: bounds.getWest(),
      centerLat: center.lat,
      centerLon: center.lng
    });
  }, [map, onChange]);

  useEffect(() => {
    updateViewport();
  }, [updateViewport]);

  useMapEvents({
    moveend: updateViewport,
    zoomend: updateViewport
  });

  return null;
}

function isLongitudeInBounds(lon: number, west: number, east: number) {
  if (west <= east) {
    return lon >= west && lon <= east;
  }
  return lon >= west || lon <= east;
}

function isFacilityInViewport(facility: NearbyFacilityPoint, viewport: MapViewport) {
  return (
    facility.lat >= viewport.south &&
    facility.lat <= viewport.north &&
    isLongitudeInBounds(facility.lon, viewport.west, viewport.east)
  );
}

export function PropertyMap({ lat, lon, onSelect, locationSummary }: Props) {
  const center = useMemo<LatLngExpression>(() => [lat ?? 35.681236, lon ?? 139.767125], [lat, lon]);
  const [query, setQuery] = useState("");
  const [searchCenter, setSearchCenter] = useState<LatLngExpression | null>(null);
  const [searchStatus, setSearchStatus] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [hazardConfig, setHazardConfig] = useState<HazardLayerConfig | null>(null);
  const [activeHazardLayerIds, setActiveHazardLayerIds] = useState<Set<string>>(new Set());
  const [nearbyFacilities, setNearbyFacilities] = useState<NearbyFacilityCollection | null>(null);
  const [activeFacilityCategoryIds, setActiveFacilityCategoryIds] = useState<Set<NearbyFacilityCategoryId>>(new Set());
  const [mapViewport, setMapViewport] = useState<MapViewport | null>(null);

  const hazardLayers = useMemo(
    () => hazardConfig?.layers.filter((layer) => layer.type === "raster" && layer.tileUrl) ?? [],
    [hazardConfig]
  );
  const activeHazardLayers = hazardLayers.filter((layer) => activeHazardLayerIds.has(layer.id));
  const isAnyHazardLayerActive = activeHazardLayers.length > 0;
  const activeFacilityPoints = useMemo(() => {
    if (!nearbyFacilities) {
      return [];
    }
    return nearbyFacilities.facilities.filter((facility) =>
      activeFacilityCategoryIds.has(facility.categoryId)
    );
  }, [activeFacilityCategoryIds, nearbyFacilities]);
  const visibleFacilityPoints = useMemo(() => {
    if (!mapViewport) {
      return [];
    }

    const inBounds = activeFacilityPoints.filter((facility) =>
      isFacilityInViewport(facility, mapViewport)
    );

    if (inBounds.length <= MAX_VISIBLE_FACILITY_MARKERS) {
      return inBounds;
    }

    return [...inBounds]
      .sort((a, b) => {
        const aDistance =
          (a.lat - mapViewport.centerLat) ** 2 + (a.lon - mapViewport.centerLon) ** 2;
        const bDistance =
          (b.lat - mapViewport.centerLat) ** 2 + (b.lon - mapViewport.centerLon) ** 2;
        return aDistance - bDistance;
      })
      .slice(0, MAX_VISIBLE_FACILITY_MARKERS);
  }, [activeFacilityPoints, mapViewport]);
  const facilityCountsByCategoryId = useMemo(() => {
    const counts = new Map<NearbyFacilityCategoryId, number>();
    for (const facility of nearbyFacilities?.facilities ?? []) {
      counts.set(facility.categoryId, (counts.get(facility.categoryId) ?? 0) + 1);
    }
    return counts;
  }, [nearbyFacilities]);
  const hasOpenStreetMapFacilities = useMemo(
    () => nearbyFacilities?.facilities.some((facility) => facility.source === "openstreetmap_odbl") ?? false,
    [nearbyFacilities]
  );
  const facilityCategoryById = useMemo(() => {
    const entries = nearbyFacilities?.categories.map((category) => [category.id, category] as const) ?? [];
    return new Map(entries);
  }, [nearbyFacilities]);

  useEffect(() => {
    if (!searchStatus) {
      return;
    }
    const timer = window.setTimeout(() => setSearchStatus(""), 3000);
    return () => window.clearTimeout(timer);
  }, [searchStatus]);

  useEffect(() => {
    let disposed = false;

    async function loadMapLayers() {
      try {
        const response = await fetch("./hazards/layers.json");
        if (!response.ok) {
          throw new Error("hazard config not found");
        }
        const config = (await response.json()) as HazardLayerConfig;
        if (!disposed) {
          setHazardConfig(config);
          setActiveHazardLayerIds(
            new Set(
              config.layers
                .filter((layer) => layer.enabled && layer.tileUrl)
                .map((layer) => layer.id)
            )
          );
        }
      } catch {
        if (!disposed) {
          setHazardConfig(null);
        }
      }

      try {
        const response = await fetch("./facilities/nearby_facilities.json");
        if (!response.ok) {
          throw new Error("facility config not found");
        }
        const collection = (await response.json()) as NearbyFacilityCollection;
        if (!disposed) {
          setNearbyFacilities(collection);
          setActiveFacilityCategoryIds(
            new Set(
              collection.categories
                .filter((category) => category.enabled)
                .map((category) => category.id)
            )
          );
        }
      } catch {
        if (!disposed) {
          setNearbyFacilities(null);
        }
      }
    }

    loadMapLayers();

    return () => {
      disposed = true;
    };
  }, []);

  function toggleHazardLayer(layerId: string) {
    setActiveHazardLayerIds((current) => {
      const next = new Set(current);
      if (next.has(layerId)) {
        next.delete(layerId);
      } else {
        next.add(layerId);
      }
      return next;
    });
  }

  function toggleFacilityCategory(categoryId: NearbyFacilityCategoryId) {
    setActiveFacilityCategoryIds((current) => {
      const next = new Set(current);
      if (next.has(categoryId)) {
        next.delete(categoryId);
      } else {
        next.add(categoryId);
      }
      return next;
    });
  }

  function toggleAllHazardLayers() {
    setActiveHazardLayerIds(
      isAnyHazardLayerActive ? new Set() : new Set(hazardLayers.map((layer) => layer.id))
    );
  }

  function handleMapSelect(nextLat: number, nextLon: number) {
    setSearchStatus("");
    onSelect(nextLat, nextLon);
  }

  async function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedQuery = query.trim();
    if (!trimmedQuery) {
      return;
    }

    setIsSearching(true);
    setSearchStatus("");

    try {
      const result = await searchPlace(trimmedQuery);
      if (!result) {
        setSearchStatus("見つかりませんでした");
        return;
      }
      setSearchCenter([result.lat, result.lon]);
      onSelect(result.lat, result.lon, { mapMoveDurationMs: SEARCH_FLY_TO_DURATION_MS });
    } catch {
      setSearchStatus("検索に失敗しました");
    } finally {
      setIsSearching(false);
    }
  }

  return (
    <section className="panel map-panel" aria-label="地図" data-testid="property-map">
      <div className="map-frame">
        <img className="app-icon map-app-icon" src="./app-icon.svg" alt="" aria-hidden="true" />
        <form className="map-search" onSubmit={handleSearch}>
          <input
            aria-label="地図検索"
            placeholder="駅名・住所を入力 例: 大宮駅、那覇市"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <button type="submit" disabled={isSearching}>
            検索
          </button>
          {searchStatus ? <p>{searchStatus}</p> : null}
        </form>
        <div className="mobile-map-layer-controls" aria-label="地図レイヤー切替">
          {nearbyFacilities?.categories.map((category) => {
            const isActive = activeFacilityCategoryIds.has(category.id);
            const count = facilityCountsByCategoryId.get(category.id) ?? 0;
            return (
              <button
                type="button"
                key={category.id}
                className={isActive ? "is-active" : ""}
                aria-pressed={isActive}
                disabled={count === 0}
                onClick={() => toggleFacilityCategory(category.id)}
              >
                <span style={{ color: category.color }} aria-hidden="true">●</span>
                {category.label}
              </button>
            );
          })}
          {hazardLayers.length > 0 ? (
            <button
              type="button"
              className={isAnyHazardLayerActive ? "is-active" : ""}
              aria-pressed={isAnyHazardLayerActive}
              onClick={toggleAllHazardLayers}
            >
              <span aria-hidden="true">◆</span>
              ハザード
            </button>
          ) : null}
        </div>
        <MapContainer center={center} zoom={12} className="map">
          <ViewportTracker onChange={setMapViewport} />
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <MapMover center={searchCenter} />
          {activeHazardLayers.map((layer, index) => (
            <TileLayer
              key={layer.id}
              attribution={hazardConfig?.source.attribution}
              maxZoom={layer.maxZoom}
              minZoom={layer.minZoom}
              opacity={layer.defaultOpacity}
              url={layer.tileUrl ?? ""}
              zIndex={300 + index}
            />
          ))}
          {visibleFacilityPoints.map((facility) => {
            const category = facilityCategoryById.get(facility.categoryId);
            const color = category?.color ?? "#0f766e";
            return (
              <CircleMarker
                key={facility.id}
                center={[facility.lat, facility.lon]}
                pathOptions={{
                  color,
                  fillColor: color,
                  fillOpacity: 0.85,
                  weight: 2
                }}
                radius={7}
                eventHandlers={{
                  click(event) {
                    event.originalEvent.stopPropagation();
                  }
                }}
              >
                <Tooltip className="facility-marker-tooltip" direction="top" offset={[0, -8]}>
                  <strong>{facility.name}</strong>
                  <span>{category?.label ?? "周辺施設"}</span>
                  {facility.address ? <small>{facility.address}</small> : null}
                </Tooltip>
              </CircleMarker>
            );
          })}
          <ClickHandler onSelect={handleMapSelect} />
          {lat !== null && lon !== null ? (
            <Marker icon={propertyMarkerIcon} position={[lat, lon]}>
              {locationSummary ? (
                <Tooltip
                  className="map-location-tooltip"
                  direction="top"
                  offset={[0, -38]}
                  opacity={1}
                  permanent
                >
                  <dl className="map-location-popup">
                    <div>
                      <dt>都道府県</dt>
                      <dd>{locationSummary.prefecture || "-"}</dd>
                    </div>
                    <div>
                      <dt>市区町村</dt>
                      <dd>{locationSummary.municipality || "-"}</dd>
                    </div>
                    <div>
                      <dt>最寄駅</dt>
                      <dd>{locationSummary.station || "-"}</dd>
                    </div>
                    <div>
                      <dt>駅徒歩</dt>
                      <dd>{Math.round(locationSummary.stationDistance)}分</dd>
                    </div>
                  </dl>
                </Tooltip>
              ) : null}
            </Marker>
          ) : null}
        </MapContainer>
        {nearbyFacilities ? (
          <div className="facility-layer-control" aria-label="周辺施設レイヤー" data-testid="facility-layer-control">
            <strong>周辺施設</strong>
            {nearbyFacilities.categories.map((category) => {
              const count = facilityCountsByCategoryId.get(category.id) ?? 0;
              return (
                <label className="map-layer-toggle" key={category.id}>
                  <input
                    type="checkbox"
                    checked={activeFacilityCategoryIds.has(category.id)}
                    disabled={count === 0}
                    onChange={() => toggleFacilityCategory(category.id)}
                  />
                  <span className="facility-layer-swatch" style={{ backgroundColor: category.color }} aria-hidden="true" />
                  <span>{category.label}</span>
                </label>
              );
            })}
            {nearbyFacilities.facilities.length === 0 ? (
              <p>周辺施設データは未生成です。</p>
            ) : (
              <p>
                出典: {nearbyFacilities.sourceLabel}
                {hasOpenStreetMapFacilities ? (
                  <>
                    <br />
                    <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">
                      OpenStreetMap contributors (ODbL)
                    </a>
                  </>
                ) : null}
              </p>
            )}
          </div>
        ) : null}
        {hazardLayers.length > 0 && hazardConfig ? (
          <div className="hazard-layer-control" aria-label="ハザードレイヤー" data-testid="hazard-layer-control">
            <strong>ハザード</strong>
            {hazardLayers.map((layer) => (
              <label className="map-layer-toggle" key={layer.id}>
                <input
                  type="checkbox"
                  checked={activeHazardLayerIds.has(layer.id)}
                  onChange={() => toggleHazardLayer(layer.id)}
                />
                <span>{layer.name}</span>
              </label>
            ))}
            <a href={hazardConfig.source.dataCopyrightUrl} target="_blank" rel="noreferrer">
              出典: {hazardConfig.source.attribution}
            </a>
          </div>
        ) : null}
      </div>
    </section>
  );
}
