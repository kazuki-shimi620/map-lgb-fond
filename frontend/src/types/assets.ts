export type CategoryDictionary = {
  prefectures: Record<string, number>;
  municipalities: Record<string, number>;
  stations: Record<string, number>;
  roomLayouts: Record<string, number>;
  buildingTypes: Record<string, number>;
  unknownId: number;
};

export type ModelMetadata = {
  region: string;
  modelName: string;
  mae: number;
  latestTrainingYear: number;
  featureOrder: string[];
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
};

export type PriceHistoryPoint = {
  station: string;
  year: number;
  avg_price: number;
  kind?: "actual" | "forecast";
};
