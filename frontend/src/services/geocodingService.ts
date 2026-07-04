export type ReverseGeocodeResult = {
  prefecture: string;
  municipality: string;
};

export type PlaceSearchResult = {
  label: string;
  lat: number;
  lon: number;
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

const PREFECTURE_BY_ISO_CODE: Record<string, string> = {
  "JP-01": "北海道",
  "JP-02": "青森県",
  "JP-03": "岩手県",
  "JP-04": "宮城県",
  "JP-05": "秋田県",
  "JP-06": "山形県",
  "JP-07": "福島県",
  "JP-08": "茨城県",
  "JP-09": "栃木県",
  "JP-10": "群馬県",
  "JP-11": "埼玉県",
  "JP-12": "千葉県",
  "JP-13": "東京都",
  "JP-14": "神奈川県",
  "JP-15": "新潟県",
  "JP-16": "富山県",
  "JP-17": "石川県",
  "JP-18": "福井県",
  "JP-19": "山梨県",
  "JP-20": "長野県",
  "JP-21": "岐阜県",
  "JP-22": "静岡県",
  "JP-23": "愛知県",
  "JP-24": "三重県",
  "JP-25": "滋賀県",
  "JP-26": "京都府",
  "JP-27": "大阪府",
  "JP-28": "兵庫県",
  "JP-29": "奈良県",
  "JP-30": "和歌山県",
  "JP-31": "鳥取県",
  "JP-32": "島根県",
  "JP-33": "岡山県",
  "JP-34": "広島県",
  "JP-35": "山口県",
  "JP-36": "徳島県",
  "JP-37": "香川県",
  "JP-38": "愛媛県",
  "JP-39": "高知県",
  "JP-40": "福岡県",
  "JP-41": "佐賀県",
  "JP-42": "長崎県",
  "JP-43": "熊本県",
  "JP-44": "大分県",
  "JP-45": "宮崎県",
  "JP-46": "鹿児島県",
  "JP-47": "沖縄県"
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
  const isoCode = address["ISO3166-2-lvl4"] ?? address["ISO3166-2-lvl3"] ?? "";

  return {
    prefecture: PREFECTURE_BY_ISO_CODE[isoCode] ?? PREFECTURE_ALIASES[prefecture] ?? prefecture,
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

export async function searchPlace(query: string): Promise<PlaceSearchResult | null> {
  const trimmedQuery = query.trim();
  if (!trimmedQuery) {
    return null;
  }

  const url = new URL("https://nominatim.openstreetmap.org/search");
  url.searchParams.set("format", "jsonv2");
  url.searchParams.set("q", trimmedQuery);
  url.searchParams.set("countrycodes", "jp");
  url.searchParams.set("limit", "1");
  url.searchParams.set("accept-language", "ja");

  const response = await fetch(url);
  if (!response.ok) {
    throw new Error("Place search failed");
  }

  const [result] = await response.json();
  if (!result) {
    return null;
  }

  return {
    label: result.display_name ?? trimmedQuery,
    lat: Number(result.lat),
    lon: Number(result.lon)
  };
}
