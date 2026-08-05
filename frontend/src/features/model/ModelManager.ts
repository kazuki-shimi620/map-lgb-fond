import type { InferenceSession, Tensor } from "onnxruntime-web";
import type { CategoryDictionary, ModelMetadata } from "../../types/assets";
import type {
  EncodedPredictionRequest,
  PredictionRequest,
  PredictionResult,
  SupportedRegion
} from "../../types/prediction";
import { fetchJson } from "../../services/http";
import { modelAssetLoader, type ModelLoadPriority } from "./modelAssetLoader";

type OrtModule = typeof import("onnxruntime-web/wasm");

const FEATURE_ALIASES: Record<string, keyof EncodedPredictionRequest> = {
  station_distance: "stationDistance",
  room_layout: "roomLayout",
  building_type: "buildingType",
  transaction_year: "predictionYear",
  station_passenger_log: "stationPassengerLog",
  station_line_count: "stationLineCount",
  station_operator_count: "stationOperatorCount",
  effective_station_scale: "effectiveStationScale",
  has_station_passenger_data: "hasStationPassengerData",
  station_rank: "stationRank",
  land_price_city_avg_yen_per_sqm: "landPriceCityAvgYenPerSqm",
  land_price_city_yoy_rate: "landPriceCityYoyRate",
  land_price_points_city_count: "landPricePointsCityCount",
  nearest_land_price_yen_per_sqm: "nearestLandPriceYenPerSqm",
  nearest_land_price_distance_km: "nearestLandPriceDistanceKm",
  land_price_points_within_2km: "landPricePointsWithin2km",
  has_land_price_data: "hasLandPriceData",
  is_commercial_zone: "isCommercialZone",
  is_residential_zone: "isResidentialZone",
  floor_area_ratio: "floorAreaRatio",
  building_coverage_ratio: "buildingCoverageRatio",
  has_zoning_data: "hasZoningData",
  city_planning_area_type: "cityPlanningAreaType",
  zoning_type: "zoningType",
  location_optimization_area: "locationOptimizationArea"
};

function encodeCategory(dictionary: Record<string, number>, value: string, unknownId: number): number {
  return dictionary[value] ?? unknownId;
}

function normalizeRoomLayout(value: string): string {
  return value.replace(/[0-9A-Za-z]/g, (character) =>
    String.fromCharCode(character.charCodeAt(0) + 0xfee0)
  );
}

export class ModelManager {
  private region: SupportedRegion;
  private ort: OrtModule | null = null;
  private session: InferenceSession | null = null;
  private dictionary: CategoryDictionary | null = null;
  private metadata: ModelMetadata | null = null;
  private isUsingFallback = false;
  private loadPromise: Promise<void> | null = null;

  constructor(region: SupportedRegion) {
    this.region = region;
  }

  async loadMetadata(): Promise<ModelMetadata> {
    this.metadata = await fetchJson<ModelMetadata>(`./metadata/${this.region}_latest_metadata.json`);
    return this.metadata;
  }

  async loadCategoryDictionary(): Promise<CategoryDictionary> {
    this.dictionary = await fetchJson<CategoryDictionary>(`./metadata/${this.region}_latest_categories.json`);
    return this.dictionary;
  }

  async loadModel(priority: ModelLoadPriority = "critical"): Promise<void> {
    try {
      this.ort = await import("onnxruntime-web/wasm");
      const onnxAssetBase = `${import.meta.env.BASE_URL}onnx/`;
      this.ort.env.wasm.wasmPaths = {
        "ort-wasm-simd.wasm": `${onnxAssetBase}ort-wasm-simd.wasm`
      };
      this.ort.env.wasm.numThreads = 1;
      const modelBytes = await modelAssetLoader.load(this.region, priority);
      this.session = await this.ort.InferenceSession.create(modelBytes);
      this.isUsingFallback = false;
    } catch (error) {
      if (this.metadata?.developmentFallback) {
        this.session = null;
        this.isUsingFallback = true;
        return;
      }
      throw error;
    }
  }

  async loadAll(priority: ModelLoadPriority = "critical"): Promise<void> {
    if (this.session || this.isUsingFallback) {
      return;
    }
    this.loadPromise ??= this.loadAssets(priority).finally(() => {
      this.loadPromise = null;
    });
    return this.loadPromise;
  }

  async release(): Promise<void> {
    const session = this.session;
    this.session = null;
    if (session) {
      await session.release();
    }
  }

  encode(request: PredictionRequest): EncodedPredictionRequest {
    if (!this.dictionary) {
      throw new Error("カテゴリ辞書が読み込まれていません");
    }

    const unknownId = this.dictionary.unknownId;
    const stationPassengerLog = request.stationPassengerLog ?? 0;

    return {
      prefecture: encodeCategory(this.dictionary.prefectures ?? {}, request.prefecture, unknownId),
      municipality: encodeCategory(this.dictionary.municipalities ?? {}, request.municipality, unknownId),
      station: encodeCategory(this.dictionary.stations ?? {}, request.station, unknownId),
      area: request.area,
      age: request.age,
      stationDistance: request.stationDistance,
      roomLayout: encodeCategory(
        this.dictionary.roomLayouts ?? {},
        normalizeRoomLayout(request.roomLayout),
        unknownId
      ),
      buildingType: encodeCategory(this.dictionary.buildingTypes ?? {}, request.buildingType, unknownId),
      predictionYear: request.predictionYear,
      stationPassengerLog,
      stationLineCount: request.stationLineCount ?? 0,
      stationOperatorCount: request.stationOperatorCount ?? 0,
      effectiveStationScale:
        stationPassengerLog * Math.exp(-(request.stationDistance * 60) / 1000),
      hasStationPassengerData: stationPassengerLog > 0 ? 1 : 0,
      stationRank: encodeCategory(
        this.dictionary.station_rank ?? {},
        request.stationRank ?? "unknown",
        unknownId
      ),
      landPriceCityAvgYenPerSqm: request.landPriceCityAvgYenPerSqm ?? 0,
      landPriceCityYoyRate: request.landPriceCityYoyRate ?? 0,
      landPricePointsCityCount: request.landPricePointsCityCount ?? 0,
      nearestLandPriceYenPerSqm: request.nearestLandPriceYenPerSqm ?? 0,
      nearestLandPriceDistanceKm: request.nearestLandPriceDistanceKm ?? 0,
      landPricePointsWithin2km: request.landPricePointsWithin2km ?? 0,
      hasLandPriceData: request.hasLandPriceData ?? 0,
      isCommercialZone: request.isCommercialZone ?? 0,
      isResidentialZone: request.isResidentialZone ?? 0,
      floorAreaRatio: request.floorAreaRatio ?? 0,
      buildingCoverageRatio: request.buildingCoverageRatio ?? 0,
      hasZoningData: request.hasZoningData ?? 0,
      cityPlanningAreaType: encodeCategory(
        this.dictionary.city_planning_area_type ?? {},
        request.cityPlanningAreaType ?? "unknown",
        unknownId
      ),
      zoningType: encodeCategory(
        this.dictionary.zoning_type ?? {},
        request.zoningType ?? "unknown",
        unknownId
      ),
      locationOptimizationArea: encodeCategory(
        this.dictionary.location_optimization_area ?? {},
        request.locationOptimizationArea ?? "unknown",
        unknownId
      )
    };
  }

  async predict(request: PredictionRequest): Promise<PredictionResult> {
    if (!this.metadata) {
      throw new Error("モデルが読み込まれていません");
    }

    const encoded = this.encode(request);

    if (this.isUsingFallback) {
      return this.predictWithFallback(encoded, request.area);
    }

    if (!this.ort || !this.session) {
      throw new Error("モデルが読み込まれていません");
    }

    const featureValues = this.metadata.featureOrder.map((featureName) => {
      const encodedKey = FEATURE_ALIASES[featureName] ?? (featureName as keyof EncodedPredictionRequest);
      const value = encoded[encodedKey];
      if (typeof value !== "number") {
        const defaultValue = this.metadata?.featureDefaults?.[featureName];
        if (typeof defaultValue === "number") {
          return defaultValue;
        }
        throw new Error(`未対応の特徴量です: ${featureName}`);
      }
      return value;
    });

    const inputTensor = new this.ort.Tensor("float32", Float32Array.from(featureValues), [
      1,
      featureValues.length
    ]);

    const feeds = this.createFeeds(inputTensor);
    const results = await this.session.run(feeds);
    const firstOutput = Object.values(results)[0];
    const predictedPrice = Number(firstOutput.data[0]);

    return this.toResult(predictedPrice, request.area);
  }

  getMetadata(): ModelMetadata | null {
    return this.metadata;
  }

  isFallbackMode(): boolean {
    return this.isUsingFallback;
  }

  private createFeeds(inputTensor: Tensor): Record<string, Tensor> {
    if (!this.session) {
      throw new Error("モデルが読み込まれていません");
    }

    const inputName = this.session.inputNames[0];
    return { [inputName]: inputTensor };
  }

  private async loadAssets(priority: ModelLoadPriority) {
    await Promise.all([
      this.metadata ? Promise.resolve(this.metadata) : this.loadMetadata(),
      this.dictionary ? Promise.resolve(this.dictionary) : this.loadCategoryDictionary()
    ]);
    await this.loadModel(priority);
  }

  private toResult(predictedPrice: number, area: number): PredictionResult {
    const mae = this.metadata?.mae ?? 0;
    const residualQuantiles = this.metadata?.evaluation?.residualQuantiles;
    const lowerOffset = residualQuantiles?.p025 ?? -mae;
    const upperOffset = residualQuantiles?.p975 ?? mae;

    return {
      predictedPrice,
      pricePerSquareMeter: area > 0 ? predictedPrice / area : 0,
      lowerPrice: Math.max(0, predictedPrice + lowerOffset),
      upperPrice: Math.max(0, predictedPrice + upperOffset)
    };
  }

  private predictWithFallback(encoded: EncodedPredictionRequest, area: number): PredictionResult {
    const basePrice = this.metadata?.fallbackBasePrice ?? 18000000;
    const predictedPrice =
      basePrice +
      encoded.area * 850000 -
      encoded.age * 320000 -
      encoded.stationDistance * 180000 +
      (encoded.predictionYear - (this.metadata?.latestTrainingYear ?? encoded.predictionYear)) * 450000;

    return this.toResult(Math.max(1000000, predictedPrice), area);
  }
}
