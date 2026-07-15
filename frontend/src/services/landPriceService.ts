import type { LandPriceSummary } from "../types/assets";
import { fetchJson } from "./http";

let landPriceSummaryPromise: Promise<LandPriceSummary> | null = null;

export function loadLandPriceSummary(): Promise<LandPriceSummary> {
  landPriceSummaryPromise ??= fetchJson<LandPriceSummary>(
    "./land-prices/municipality_land_prices.json"
  );
  return landPriceSummaryPromise;
}
