import type { SupportedRegion } from "../types/prediction";

const PREFECTURE_TO_REGION: Record<string, SupportedRegion> = {
  東京都: "tokyo",
  埼玉県: "saitama",
  千葉県: "chiba",
  神奈川県: "kanagawa"
};

const REGION_TO_LABEL: Record<SupportedRegion, string> = {
  tokyo: "東京都",
  saitama: "埼玉県",
  chiba: "千葉県",
  kanagawa: "神奈川県"
};

export const supportedRegions = Object.values(PREFECTURE_TO_REGION);
export function getRegionFromPrefecture(prefecture: string): SupportedRegion | null {
  return PREFECTURE_TO_REGION[prefecture] ?? null;
}

export function getPrefectureLabel(region: SupportedRegion): string {
  return REGION_TO_LABEL[region];
}

export const supportedPrefectures = Object.keys(PREFECTURE_TO_REGION);
