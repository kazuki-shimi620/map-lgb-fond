import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { CircleMarker, MapContainer, Marker, TileLayer, Tooltip, useMap, useMapEvents } from "react-leaflet";
import { DivIcon, Icon, type LatLngExpression } from "leaflet";
import markerIcon2xUrl from "leaflet/dist/images/marker-icon-2x.png";
import markerIconUrl from "leaflet/dist/images/marker-icon.png";
import markerShadowUrl from "leaflet/dist/images/marker-shadow.png";
import { searchPlace } from "../../services/geocodingService";
import {
  distanceKmToWalkingMinutes,
  findNearestStation
} from "../../services/stationService";
import type {
  NearbyFacilityCategoryId,
  NearbyFacilityCollection,
  NearbyFacilityPoint,
  StationRecord
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
  stations: StationRecord[];
  onLayerPanelOpenChange?: (isOpen: boolean) => void;
};

const SEARCH_FLY_TO_DURATION_MS = 800;
const MAX_VISIBLE_FACILITY_MARKERS = 1200;
const FACILITY_CLUSTER_MAX_ZOOM = 10;
const FACILITY_CLUSTER_GRID_SIZE_PX = 72;

type LayerPanel = "facilities" | "hazards";

const FACILITY_FILTERS = [
  { id: "commercial:small", categoryId: "commercial_facility", label: "小規模" },
  { id: "commercial:medium", categoryId: "commercial_facility", label: "中規模" },
  { id: "commercial:large", categoryId: "commercial_facility", label: "大規模" },
  { id: "commercial:very_large", categoryId: "commercial_facility", label: "超大型" },
  { id: "commercial:unknown", categoryId: "commercial_facility", label: "規模不明" },
  { id: "museum:art", categoryId: "museum", label: "美術館・ギャラリー" },
  { id: "museum:general", categoryId: "museum", label: "博物館・資料館" },
  { id: "hot_spring:sento", categoryId: "hot_spring", label: "銭湯" },
  { id: "hot_spring:spa", categoryId: "hot_spring", label: "スーパー銭湯・スパ" },
  { id: "hot_spring:other", categoryId: "hot_spring", label: "温泉・その他" },
  { id: "cinema:multiplex", categoryId: "cinema", label: "シネコン" },
  { id: "cinema:other", categoryId: "cinema", label: "ミニシアター・その他" }
] as const;

type FacilityFilterId = (typeof FACILITY_FILTERS)[number]["id"];

function facilityFilterId(facility: NearbyFacilityPoint): FacilityFilterId | null {
  const name = facility.name.normalize("NFKC").toLowerCase();
  if (facility.categoryId === "commercial_facility") {
    return `commercial:${facility.scaleCode ?? "unknown"}` as FacilityFilterId;
  }
  if (facility.categoryId === "museum") {
    return /(美術館|画廊|ギャラリー|gallery|\bart\b)/i.test(name)
      ? "museum:art"
      : "museum:general";
  }
  if (facility.categoryId === "hot_spring") {
    if (/(スーパー銭湯|健康ランド|spa|スパ|温浴|極楽湯|竜泉寺|万葉)/i.test(name)) {
      return "hot_spring:spa";
    }
    if (/(銭湯|公衆浴場|共同浴場|浴場|の湯|湯$)/i.test(name)) {
      return "hot_spring:sento";
    }
    return "hot_spring:other";
  }
  if (facility.categoryId === "cinema") {
    return /(toho|109シネマ|イオンシネマ|ユナイテッド.?シネマ|movix|t.?joy|ティ・ジョイ|シネマサンシャイン|シネマワールド)/i.test(name)
      ? "cinema:multiplex"
      : "cinema:other";
  }
  return null;
}

type MapViewport = {
  north: number;
  south: number;
  east: number;
  west: number;
  centerLat: number;
  centerLon: number;
  zoom: number;
};

type FacilityCluster = {
  id: string;
  lat: number;
  lon: number;
  count: number;
  categoryId: NearbyFacilityCategoryId;
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
      centerLon: center.lng,
      zoom: map.getZoom()
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

function projectToWorldPixel(lat: number, lon: number, zoom: number) {
  const scale = 256 * 2 ** zoom;
  const sinLat = Math.sin((Math.max(-85.05112878, Math.min(85.05112878, lat)) * Math.PI) / 180);
  return {
    x: ((lon + 180) / 360) * scale,
    y: (0.5 - Math.log((1 + sinLat) / (1 - sinLat)) / (4 * Math.PI)) * scale
  };
}

function clusterFacilities(facilities: NearbyFacilityPoint[], zoom: number): FacilityCluster[] {
  const clusters = new Map<
    string,
    {
      latSum: number;
      lonSum: number;
      count: number;
      categoryId: NearbyFacilityCategoryId;
    }
  >();

  for (const facility of facilities) {
    const pixel = projectToWorldPixel(facility.lat, facility.lon, zoom);
    const gridX = Math.floor(pixel.x / FACILITY_CLUSTER_GRID_SIZE_PX);
    const gridY = Math.floor(pixel.y / FACILITY_CLUSTER_GRID_SIZE_PX);
    const id = `${facility.categoryId}:${zoom}:${gridX}:${gridY}`;
    const current = clusters.get(id);
    if (current) {
      current.latSum += facility.lat;
      current.lonSum += facility.lon;
      current.count += 1;
    } else {
      clusters.set(id, {
        latSum: facility.lat,
        lonSum: facility.lon,
        count: 1,
        categoryId: facility.categoryId
      });
    }
  }

  return [...clusters.entries()].map(([id, cluster]) => ({
    id,
    lat: cluster.latSum / cluster.count,
    lon: cluster.lonSum / cluster.count,
    count: cluster.count,
    categoryId: cluster.categoryId
  }));
}

function createFacilityClusterIcon(count: number, categoryColor: string) {
  const intensity = Math.min(1, Math.log10(count + 1) / 2.5);
  const size = Math.round(34 + intensity * 34);
  const fillOpacity = (0.62 + intensity * 0.3).toFixed(2);
  const color = /^#[0-9a-f]{6}$/i.test(categoryColor) ? categoryColor : "#0f766e";

  return new DivIcon({
    className: "facility-cluster-icon-wrapper",
    html: `<span class="facility-cluster-icon" style="--cluster-size:${size}px;--cluster-color:${color};--cluster-opacity:${fillOpacity}">${count}</span>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2]
  });
}

function FacilityClusterMarker({
  cluster,
  color,
  label
}: {
  cluster: FacilityCluster;
  color: string;
  label: string;
}) {
  const map = useMap();
  return (
    <Marker
      position={[cluster.lat, cluster.lon]}
      icon={createFacilityClusterIcon(cluster.count, color)}
      eventHandlers={{
        click(event) {
          event.originalEvent.stopPropagation();
          map.flyTo([cluster.lat, cluster.lon], Math.min(map.getZoom() + 2, FACILITY_CLUSTER_MAX_ZOOM + 1), {
            duration: 0.45
          });
        }
      }}
    >
      <Tooltip direction="top" offset={[0, -18]}>
        {label}: この範囲に{cluster.count.toLocaleString("ja-JP")}件
      </Tooltip>
    </Marker>
  );
}

export function PropertyMap({
  lat,
  lon,
  onSelect,
  locationSummary,
  stations,
  onLayerPanelOpenChange
}: Props) {
  const center = useMemo<LatLngExpression>(() => [lat ?? 35.681236, lon ?? 139.767125], [lat, lon]);
  const [query, setQuery] = useState("");
  const [searchCenter, setSearchCenter] = useState<LatLngExpression | null>(null);
  const [searchStatus, setSearchStatus] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [hazardConfig, setHazardConfig] = useState<HazardLayerConfig | null>(null);
  const [activeHazardLayerIds, setActiveHazardLayerIds] = useState<Set<string>>(new Set());
  const [nearbyFacilities, setNearbyFacilities] = useState<NearbyFacilityCollection | null>(null);
  const [activeFacilityCategoryIds, setActiveFacilityCategoryIds] = useState<Set<NearbyFacilityCategoryId>>(new Set());
  const [activeFacilityFilterIds, setActiveFacilityFilterIds] = useState<Set<FacilityFilterId>>(
    new Set(FACILITY_FILTERS.map((filter) => filter.id))
  );
  const [openLayerPanel, setOpenLayerPanel] = useState<LayerPanel | null>(null);
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
    return nearbyFacilities.facilities.filter((facility) => {
      if (!activeFacilityCategoryIds.has(facility.categoryId)) {
        return false;
      }
      const filterId = facilityFilterId(facility);
      return filterId === null || activeFacilityFilterIds.has(filterId);
    });
  }, [activeFacilityCategoryIds, activeFacilityFilterIds, nearbyFacilities]);
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
  const facilityClusters = useMemo(() => {
    if (!mapViewport || mapViewport.zoom > FACILITY_CLUSTER_MAX_ZOOM) {
      return [];
    }
    const inBounds = activeFacilityPoints.filter((facility) =>
      isFacilityInViewport(facility, mapViewport)
    );
    return clusterFacilities(inBounds, mapViewport.zoom);
  }, [activeFacilityPoints, mapViewport]);
  const showFacilityClusters =
    mapViewport !== null && mapViewport.zoom <= FACILITY_CLUSTER_MAX_ZOOM;
  const facilityStationInfoById = useMemo(() => {
    const result = new Map<string, { stationName: string; walkingMinutes: number }>();
    if (!locationSummary || stations.length === 0) {
      return result;
    }

    for (const facility of visibleFacilityPoints) {
      if (facility.prefecture && facility.prefecture !== locationSummary.prefecture) {
        continue;
      }
      const nearest = findNearestStation(stations, facility.lat, facility.lon);
      if (nearest) {
        result.set(facility.id, {
          stationName: nearest.station.station_name,
          walkingMinutes: distanceKmToWalkingMinutes(nearest.distanceKm)
        });
      }
    }
    return result;
  }, [locationSummary, stations, visibleFacilityPoints]);
  const facilityCountsByCategoryId = useMemo(() => {
    const counts = new Map<NearbyFacilityCategoryId, number>();
    for (const facility of nearbyFacilities?.facilities ?? []) {
      counts.set(facility.categoryId, (counts.get(facility.categoryId) ?? 0) + 1);
    }
    return counts;
  }, [nearbyFacilities]);
  const facilityCountsByFilterId = useMemo(() => {
    const counts = new Map<FacilityFilterId, number>();
    for (const facility of nearbyFacilities?.facilities ?? []) {
      const filterId = facilityFilterId(facility);
      if (filterId) {
        counts.set(filterId, (counts.get(filterId) ?? 0) + 1);
      }
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

  function toggleFacilityFilter(filterId: FacilityFilterId) {
    setActiveFacilityFilterIds((current) => {
      const next = new Set(current);
      if (next.has(filterId)) {
        next.delete(filterId);
      } else {
        next.add(filterId);
      }
      return next;
    });
  }

  function toggleLayerPanel(panel: LayerPanel) {
    const next = openLayerPanel === panel ? null : panel;
    setOpenLayerPanel(next);
    onLayerPanelOpenChange?.(next !== null);
  }

  function closeLayerPanel() {
    setOpenLayerPanel(null);
    onLayerPanelOpenChange?.(false);
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
          {nearbyFacilities ? (
            <button
              type="button"
              className={openLayerPanel === "facilities" ? "is-active" : ""}
              aria-expanded={openLayerPanel === "facilities"}
              onClick={() => toggleLayerPanel("facilities")}
            >
              <span aria-hidden="true">●</span>
              周辺施設
            </button>
          ) : null}
          {hazardLayers.length > 0 ? (
            <button
              type="button"
              className={openLayerPanel === "hazards" ? "is-active" : ""}
              aria-expanded={openLayerPanel === "hazards"}
              onClick={() => toggleLayerPanel("hazards")}
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
          {showFacilityClusters
            ? facilityClusters.map((cluster) => {
                const category = facilityCategoryById.get(cluster.categoryId);
                return (
                  <FacilityClusterMarker
                    key={cluster.id}
                    cluster={cluster}
                    color={category?.color ?? "#0f766e"}
                    label={category?.label ?? "周辺施設"}
                  />
                );
              })
            : visibleFacilityPoints.map((facility) => {
            const category = facilityCategoryById.get(facility.categoryId);
            const color = category?.color ?? "#0f766e";
            const stationInfo = facilityStationInfoById.get(facility.id);
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
                  {facility.categoryId === "commercial_facility" && facility.scaleLabel ? (
                    <small>規模: {facility.scaleLabel}</small>
                  ) : null}
                  {stationInfo ? (
                    <small>
                      最寄駅: {stationInfo.stationName}駅・徒歩{stationInfo.walkingMinutes}分
                    </small>
                  ) : null}
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
        {nearbyFacilities && openLayerPanel === "facilities" ? (
          <div className="map-layer-control facility-layer-control" aria-label="周辺施設レイヤー" data-testid="facility-layer-control">
            <div className="map-layer-control-header">
              <strong>周辺施設</strong>
              <button type="button" aria-label="周辺施設を閉じる" onClick={closeLayerPanel}>×</button>
            </div>
            {nearbyFacilities.categories.map((category) => {
              const filters = FACILITY_FILTERS.filter((filter) => filter.categoryId === category.id);
              const count = facilityCountsByCategoryId.get(category.id) ?? 0;
              return (
                <fieldset className="map-layer-filter-group" key={category.id}>
                  <legend>
                    <span className="facility-layer-swatch" style={{ backgroundColor: category.color }} aria-hidden="true" />
                    {category.label}
                  </legend>
                  {filters.length > 0 ? filters.map((filter) => (
                    <label className="map-layer-toggle" key={filter.id}>
                      <input
                        type="checkbox"
                        checked={activeFacilityFilterIds.has(filter.id)}
                        disabled={(facilityCountsByFilterId.get(filter.id) ?? 0) === 0}
                        onChange={() => toggleFacilityFilter(filter.id)}
                      />
                      <span>{filter.label}</span>
                      <small>{(facilityCountsByFilterId.get(filter.id) ?? 0).toLocaleString("ja-JP")}</small>
                    </label>
                  )) : (
                    <label className="map-layer-toggle">
                      <input
                        type="checkbox"
                        checked={activeFacilityCategoryIds.has(category.id)}
                        disabled={count === 0}
                        onChange={() => toggleFacilityCategory(category.id)}
                      />
                      <span>{category.label}を表示</span>
                      <small>{count.toLocaleString("ja-JP")}</small>
                    </label>
                  )}
                </fieldset>
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
        {hazardLayers.length > 0 && hazardConfig && openLayerPanel === "hazards" ? (
          <div className="map-layer-control hazard-layer-control" aria-label="ハザードレイヤー" data-testid="hazard-layer-control">
            <div className="map-layer-control-header">
              <strong>ハザード</strong>
              <button type="button" aria-label="ハザードを閉じる" onClick={closeLayerPanel}>×</button>
            </div>
            <button type="button" className="map-layer-all-toggle" onClick={toggleAllHazardLayers}>
              {isAnyHazardLayerActive ? "すべて非表示" : "すべて表示"}
            </button>
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
