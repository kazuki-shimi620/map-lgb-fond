import { useEffect, useMemo, useState, type FormEvent } from "react";
import { MapContainer, Marker, TileLayer, useMap, useMapEvents } from "react-leaflet";
import { Icon, type LatLngExpression } from "leaflet";
import markerIcon2xUrl from "leaflet/dist/images/marker-icon-2x.png";
import markerIconUrl from "leaflet/dist/images/marker-icon.png";
import markerShadowUrl from "leaflet/dist/images/marker-shadow.png";
import { searchPlace } from "../../services/geocodingService";

type Props = {
  lat: number | null;
  lon: number | null;
  onSelect: (lat: number, lon: number) => void;
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

export function PropertyMap({ lat, lon, onSelect }: Props) {
  const center = useMemo<LatLngExpression>(() => [lat ?? 35.681236, lon ?? 139.767125], [lat, lon]);
  const [query, setQuery] = useState("");
  const [searchCenter, setSearchCenter] = useState<LatLngExpression | null>(null);
  const [searchStatus, setSearchStatus] = useState("");
  const [isSearching, setIsSearching] = useState(false);

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
      setSearchStatus("");
    } catch {
      setSearchStatus("検索に失敗しました");
    } finally {
      setIsSearching(false);
    }
  }

  return (
    <section className="panel map-panel">
      <h2>地図</h2>
      <div className="map-frame">
        <form className="map-search" onSubmit={handleSearch}>
          <input
            aria-label="地図検索"
            placeholder="地名を検索"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <button type="submit" disabled={isSearching}>
            検索
          </button>
          {searchStatus ? <p>{searchStatus}</p> : null}
        </form>
        <MapContainer center={center} zoom={12} className="map">
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <MapMover center={searchCenter} />
          <ClickHandler onSelect={onSelect} />
          {lat !== null && lon !== null ? <Marker icon={propertyMarkerIcon} position={[lat, lon]} /> : null}
        </MapContainer>
      </div>
    </section>
  );
}
