import { useMemo } from "react";
import { MapContainer, Marker, TileLayer, useMapEvents } from "react-leaflet";
import type { LatLngExpression } from "leaflet";

type Props = {
  lat: number | null;
  lon: number | null;
  onSelect: (lat: number, lon: number) => void;
};

function ClickHandler({ onSelect }: Pick<Props, "onSelect">) {
  useMapEvents({
    click(event) {
      onSelect(event.latlng.lat, event.latlng.lng);
    }
  });

  return null;
}

export function PropertyMap({ lat, lon, onSelect }: Props) {
  const center = useMemo<LatLngExpression>(() => [lat ?? 35.681236, lon ?? 139.767125], [lat, lon]);

  return (
    <section className="panel map-panel">
      <h2>地図</h2>
      <MapContainer center={center} zoom={12} className="map">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <ClickHandler onSelect={onSelect} />
        {lat !== null && lon !== null ? <Marker position={[lat, lon]} /> : null}
      </MapContainer>
    </section>
  );
}
