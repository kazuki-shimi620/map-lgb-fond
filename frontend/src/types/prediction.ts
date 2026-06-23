export type SupportedRegion = "tokyo" | "saitama" | "chiba" | "kanagawa";

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
};

export type PredictionFormState = PredictionRequest & {
  lat: number | null;
  lon: number | null;
};
