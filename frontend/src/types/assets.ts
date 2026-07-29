export type CategoryDictionary = {
  prefectures?: Record<string, number>;
  municipalities?: Record<string, number>;
  stations?: Record<string, number>;
  roomLayouts?: Record<string, number>;
  buildingTypes?: Record<string, number>;
  station_rank?: Record<string, number>;
  city_planning_area_type?: Record<string, number>;
  zoning_type?: Record<string, number>;
  location_optimization_area?: Record<string, number>;
  unknownId: number;
};

export type ModelMetadata = {
  region: string;
  modelName: string;
  mae: number;
  latestTrainingYear: number;
  featureOrder: string[];
  featureDefaults?: Record<string, number>;
  generatedAt?: string;
  evaluation?: {
    split: string;
    trainStartYear: number;
    testYear: number;
    trainCount: number;
    testCount: number;
    metrics: {
      mae: number;
      rmse: number;
      mape: number;
    };
    residualQuantiles?: {
      p025: number;
      p975: number;
    };
  };
  deployment?: {
    trainStartYear: number;
    latestTrainingYear: number;
    trainCount: number;
    trainedWithAllAvailableRows: boolean;
  };
  featureImportance?: Array<{
    feature: string;
    importance: number;
  }>;
  developmentFallback?: boolean;
  fallbackBasePrice?: number;
};

export type StationRecord = {
  station_id: string;
  station_name: string;
  prefecture: string;
  line_name: string;
  lat: number;
  lon: number;
  station_passenger_log?: number;
  station_line_count?: number;
  station_operator_count?: number;
  station_rank?: string;
};

export type PriceHistoryPoint = {
  prefecture?: string;
  station: string;
  year: number;
  avg_price: number;
  avg_unit_price?: number;
  transaction_count?: number;
  comparable_buckets?: Array<[
    areaBand: number,
    ageBand: number,
    avgUnitPrice: number,
    transactionCount: number
  ]>;
  kind?: "actual" | "estimated" | "forecast";
};

export type ModelAsset = {
  path: string;
  version: string;
  bytes: number;
};

export type ModelManifest = {
  schemaVersion: number;
  generatedAt: string;
  capitalRegionPriority: string[];
  models: Record<string, ModelAsset>;
};

export type PriceTrend = {
  annualizedRate: number | null;
  volatility: number | null;
  sampleYears: number;
  startYear: number | null;
  endYear: number | null;
};

export type PriceTrendSummary = {
  schemaVersion: number;
  region: string;
  latestTrainingYear: number | null;
  regionalTrend: PriceTrend;
  stationTrends: Record<string, PriceTrend>;
};

export type CommercialFacilityAreaSummary = {
  prefecture?: string;
  city?: string;
  scCount: number;
  storeAreaSumSqm: number;
  tenantCountSum: number;
  latestOpenYear: number | null;
  facilities?: CommercialFacilityDetail[];
  recentOpenings: CommercialFacilityDetail[];
};

export type CommercialFacilityDetail = {
    name: string;
    openYear: number | null;
    openMonth: number | null;
    storeAreaSqm: number | null;
    tenantCount: number | null;
};

export type CommercialFacilitySummary = {
  schemaVersion: number;
  source: string;
  sourceLabel: string;
  generatedAt: string;
  coverage?: {
    area: string;
    facilityCount: number;
    coordinateCount: number;
    reliableCoordinateCount: number;
    storeAreaMissingCount: number;
    coordinateRate: number;
    reliableCoordinateRate: number;
    storeAreaMissingRate: number;
  };
  latestOpenYear: number | null;
  prefectures: Record<string, CommercialFacilityAreaSummary>;
  cities: Record<string, CommercialFacilityAreaSummary>;
};

export type LandPriceYearSummary = {
  avgPriceYenPerSqm: number;
  yoyRate: number;
  pointCount: number;
};

export type LandPriceCitySummary = {
  prefecture: string;
  municipality: string;
  years: Record<string, LandPriceYearSummary>;
};

export type LandPriceSummary = {
  schemaVersion: number;
  source: string;
  sourceLabel: string;
  generatedAt: string;
  latestYear: number | null;
  cities: Record<string, LandPriceCitySummary>;
};

export type UrbanPlanningGeometry = {
  type: "Polygon" | "MultiPolygon";
  coordinates: unknown;
};

export type UrbanPlanningArea = {
  areaType: string;
  prefecture?: string;
  municipality?: string;
  areaName?: string;
  zoningType?: string;
  floorAreaRatio: number;
  buildingCoverageRatio: number;
  bbox: [number, number, number, number];
  geometry: UrbanPlanningGeometry;
};

export type UrbanPlanningCollection = {
  schemaVersion: number;
  source: string;
  sourceLabel: string;
  generatedAt: string;
  areaCount: number;
  areas: UrbanPlanningArea[];
};

export type NearbyFacilityCategoryId =
  | "hospital"
  | "supermarket"
  | "commercial_facility"
  | "park"
  | "convenience_store"
  | "cinema"
  | "museum"
  | "hot_spring";

export type NearbyFacilityCategory = {
  id: NearbyFacilityCategoryId;
  label: string;
  color: string;
  enabled: boolean;
  sourceLabel?: string;
  sourceUrl?: string;
  licenseLabel?: string;
  coverageArea?: string;
  generatedAt?: string | null;
};

export type NearbyFacilityPoint = {
  id: string;
  categoryId: NearbyFacilityCategoryId;
  name: string;
  lat: number;
  lon: number;
  prefecture?: string;
  municipality?: string;
  address?: string;
  source?: string;
  updatedAt?: string;
};

export type NearbyFacilityCollection = {
  schemaVersion: number;
  source: string;
  sourceLabel: string;
  generatedAt: string | null;
  categories: NearbyFacilityCategory[];
  facilities: NearbyFacilityPoint[];
};
