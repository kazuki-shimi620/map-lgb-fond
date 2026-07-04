import type { StationRegion, SupportedRegion } from "../types/prediction";

type PrefectureConfig = {
  stationRegion: StationRegion;
  modelRegion: SupportedRegion;
};

const PREFECTURE_CONFIG: Record<string, PrefectureConfig> = {
  北海道: { stationRegion: "hokkaido", modelRegion: "regional_hokkaido" },
  青森県: { stationRegion: "aomori", modelRegion: "regional_tohoku" },
  岩手県: { stationRegion: "iwate", modelRegion: "regional_tohoku" },
  宮城県: { stationRegion: "miyagi", modelRegion: "regional_tohoku" },
  秋田県: { stationRegion: "akita", modelRegion: "regional_tohoku" },
  山形県: { stationRegion: "yamagata", modelRegion: "regional_tohoku" },
  福島県: { stationRegion: "fukushima", modelRegion: "regional_tohoku" },
  茨城県: { stationRegion: "ibaraki", modelRegion: "regional_kanto" },
  栃木県: { stationRegion: "tochigi", modelRegion: "regional_kanto" },
  群馬県: { stationRegion: "gunma", modelRegion: "regional_kanto" },
  埼玉県: { stationRegion: "saitama", modelRegion: "saitama" },
  千葉県: { stationRegion: "chiba", modelRegion: "chiba" },
  東京都: { stationRegion: "tokyo", modelRegion: "tokyo" },
  神奈川県: { stationRegion: "kanagawa", modelRegion: "kanagawa" },
  新潟県: { stationRegion: "niigata", modelRegion: "regional_chubu" },
  富山県: { stationRegion: "toyama", modelRegion: "regional_chubu" },
  石川県: { stationRegion: "ishikawa", modelRegion: "regional_chubu" },
  福井県: { stationRegion: "fukui", modelRegion: "regional_chubu" },
  山梨県: { stationRegion: "yamanashi", modelRegion: "regional_chubu" },
  長野県: { stationRegion: "nagano", modelRegion: "regional_chubu" },
  岐阜県: { stationRegion: "gifu", modelRegion: "regional_chubu" },
  静岡県: { stationRegion: "shizuoka", modelRegion: "regional_chubu" },
  愛知県: { stationRegion: "aichi", modelRegion: "regional_chubu" },
  三重県: { stationRegion: "mie", modelRegion: "regional_kinki" },
  滋賀県: { stationRegion: "shiga", modelRegion: "regional_kinki" },
  京都府: { stationRegion: "kyoto", modelRegion: "regional_kinki" },
  大阪府: { stationRegion: "osaka", modelRegion: "regional_kinki" },
  兵庫県: { stationRegion: "hyogo", modelRegion: "regional_kinki" },
  奈良県: { stationRegion: "nara", modelRegion: "regional_kinki" },
  和歌山県: { stationRegion: "wakayama", modelRegion: "regional_kinki" },
  鳥取県: { stationRegion: "tottori", modelRegion: "regional_chugoku" },
  島根県: { stationRegion: "shimane", modelRegion: "regional_chugoku" },
  岡山県: { stationRegion: "okayama", modelRegion: "regional_chugoku" },
  広島県: { stationRegion: "hiroshima", modelRegion: "regional_chugoku" },
  山口県: { stationRegion: "yamaguchi", modelRegion: "regional_chugoku" },
  徳島県: { stationRegion: "tokushima", modelRegion: "regional_shikoku" },
  香川県: { stationRegion: "kagawa", modelRegion: "regional_shikoku" },
  愛媛県: { stationRegion: "ehime", modelRegion: "regional_shikoku" },
  高知県: { stationRegion: "kochi", modelRegion: "regional_shikoku" },
  福岡県: { stationRegion: "fukuoka", modelRegion: "regional_kyushu" },
  佐賀県: { stationRegion: "saga", modelRegion: "regional_kyushu" },
  長崎県: { stationRegion: "nagasaki", modelRegion: "regional_kyushu" },
  熊本県: { stationRegion: "kumamoto", modelRegion: "regional_kyushu" },
  大分県: { stationRegion: "oita", modelRegion: "regional_kyushu" },
  宮崎県: { stationRegion: "miyazaki", modelRegion: "regional_kyushu" },
  鹿児島県: { stationRegion: "kagoshima", modelRegion: "regional_kyushu" },
  沖縄県: { stationRegion: "okinawa", modelRegion: "regional_kyushu" }
};

const REGION_TO_LABEL: Record<SupportedRegion, string> = {
  tokyo: "東京都",
  saitama: "埼玉県",
  chiba: "千葉県",
  kanagawa: "神奈川県",
  regional_hokkaido: "北海道モデル",
  regional_tohoku: "東北モデル",
  regional_kanto: "関東モデル",
  regional_chubu: "中部モデル",
  regional_kinki: "近畿モデル",
  regional_chugoku: "中国モデル",
  regional_shikoku: "四国モデル",
  regional_kyushu: "九州・沖縄モデル"
};

export const supportedRegions = [...new Set(Object.values(PREFECTURE_CONFIG).map((item) => item.modelRegion))];
export function getRegionFromPrefecture(prefecture: string): SupportedRegion | null {
  return PREFECTURE_CONFIG[prefecture]?.modelRegion ?? null;
}

export function getStationRegionFromPrefecture(prefecture: string): StationRegion | null {
  return PREFECTURE_CONFIG[prefecture]?.stationRegion ?? null;
}

export function getPrefectureLabel(region: SupportedRegion): string {
  return REGION_TO_LABEL[region];
}

export const supportedPrefectures = Object.keys(PREFECTURE_CONFIG);
