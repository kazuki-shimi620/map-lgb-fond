export type ReverseGeocodeResult = {
  prefecture: string;
  municipality: string;
};

const PREFECTURE_ALIASES: Record<string, string> = {
  Tokyo: "東京都",
  Saitama: "埼玉県",
  Chiba: "千葉県",
  Kanagawa: "神奈川県",
  "Kanagawa Prefecture": "神奈川県",
  "Saitama Prefecture": "埼玉県",
  "Chiba Prefecture": "千葉県",
  "Tokyo Metropolis": "東京都"
};

export async function reverseGeocode(lat: number, lon: number): Promise<ReverseGeocodeResult> {
  const url = new URL("https://nominatim.openstreetmap.org/reverse");
  url.searchParams.set("format", "jsonv2");
  url.searchParams.set("lat", String(lat));
  url.searchParams.set("lon", String(lon));
  url.searchParams.set("accept-language", "ja");

  const response = await fetch(url);
  if (!response.ok) {
    throw new Error("Reverse geocoding failed");
  }

  const data = await response.json();
  const address = data.address ?? {};
  const prefecture = address.province ?? address.state ?? address.region ?? "";

  return {
    prefecture: PREFECTURE_ALIASES[prefecture] ?? prefecture,
    municipality:
      address.city_district ??
      address.municipality ??
      address.city ??
      address.town ??
      address.village ??
      address.county ??
      address.suburb ??
      ""
  };
}
