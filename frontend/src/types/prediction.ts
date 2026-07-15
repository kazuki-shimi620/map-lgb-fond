export type SupportedRegion =
  | "tokyo"
  | "saitama"
  | "chiba"
  | "kanagawa"
  | "regional_hokkaido"
  | "regional_tohoku"
  | "regional_kanto"
  | "regional_chubu"
  | "regional_kinki"
  | "regional_chugoku"
  | "regional_shikoku"
  | "regional_kyushu";

export type StationRegion =
  | "hokkaido"
  | "aomori"
  | "iwate"
  | "miyagi"
  | "akita"
  | "yamagata"
  | "fukushima"
  | "ibaraki"
  | "tochigi"
  | "gunma"
  | "saitama"
  | "chiba"
  | "tokyo"
  | "kanagawa"
  | "niigata"
  | "toyama"
  | "ishikawa"
  | "fukui"
  | "yamanashi"
  | "nagano"
  | "gifu"
  | "shizuoka"
  | "aichi"
  | "mie"
  | "shiga"
  | "kyoto"
  | "osaka"
  | "hyogo"
  | "nara"
  | "wakayama"
  | "tottori"
  | "shimane"
  | "okayama"
  | "hiroshima"
  | "yamaguchi"
  | "tokushima"
  | "kagawa"
  | "ehime"
  | "kochi"
  | "fukuoka"
  | "saga"
  | "nagasaki"
  | "kumamoto"
  | "oita"
  | "miyazaki"
  | "kagoshima"
  | "okinawa";

export type PredictionRequest = {
  prefecture: string;
  municipality: string;
  station: string;
  area: number;
  age: number;
  stationDistance: number;
  roomLayout: string;
  buildingType: string;
  predictionYear: number;
  stationPassengerLog?: number;
  stationLineCount?: number;
  stationOperatorCount?: number;
  stationRank?: string;
  landPriceCityAvgYenPerSqm?: number;
  landPriceCityYoyRate?: number;
  landPricePointsCityCount?: number;
  nearestLandPriceYenPerSqm?: number;
  nearestLandPriceDistanceKm?: number;
  landPricePointsWithin2km?: number;
  hasLandPriceData?: number;
  isCommercialZone?: number;
  isResidentialZone?: number;
  floorAreaRatio?: number;
  buildingCoverageRatio?: number;
  hasZoningData?: number;
  cityPlanningAreaType?: string;
  zoningType?: string;
  locationOptimizationArea?: string;
};

export type PredictionResult = {
  predictedPrice: number;
  pricePerSquareMeter: number;
  lowerPrice: number;
  upperPrice: number;
};

export type EncodedPredictionRequest = {
  prefecture: number;
  municipality: number;
  station: number;
  area: number;
  age: number;
  stationDistance: number;
  roomLayout: number;
  buildingType: number;
  predictionYear: number;
  stationPassengerLog: number;
  stationLineCount: number;
  stationOperatorCount: number;
  effectiveStationScale: number;
  hasStationPassengerData: number;
  stationRank: number;
  landPriceCityAvgYenPerSqm: number;
  landPriceCityYoyRate: number;
  landPricePointsCityCount: number;
  nearestLandPriceYenPerSqm: number;
  nearestLandPriceDistanceKm: number;
  landPricePointsWithin2km: number;
  hasLandPriceData: number;
  isCommercialZone: number;
  isResidentialZone: number;
  floorAreaRatio: number;
  buildingCoverageRatio: number;
  hasZoningData: number;
  cityPlanningAreaType: number;
  zoningType: number;
  locationOptimizationArea: number;
};

export type PredictionFormState = PredictionRequest & {
  lat: number | null;
  lon: number | null;
};
