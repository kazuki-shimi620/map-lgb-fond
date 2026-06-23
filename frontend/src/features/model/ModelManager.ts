import type { InferenceSession, Tensor } from "onnxruntime-web";
import type { CategoryDictionary, ModelMetadata } from "../../types/assets";
import type {
  EncodedPredictionRequest,
  PredictionRequest,
  PredictionResult,
  SupportedRegion
} from "../../types/prediction";
import { fetchJson } from "../../services/http";

type OrtModule = typeof import("onnxruntime-web");

const FEATURE_ALIASES: Record<string, keyof EncodedPredictionRequest> = {
  station_distance: "stationDistance",
  room_layout: "roomLayout",
  building_type: "buildingType",
  transaction_year: "predictionYear"
};

function encodeCategory(dictionary: Record<string, number>, value: string, unknownId: number): number {
  return dictionary[value] ?? unknownId;
}

export class ModelManager {
  private region: SupportedRegion;
  private ort: OrtModule | null = null;
  private session: InferenceSession | null = null;
  private dictionary: CategoryDictionary | null = null;
  private metadata: ModelMetadata | null = null;
  private isUsingFallback = false;

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

  async loadModel(): Promise<void> {
    try {
      this.ort = await import("onnxruntime-web");
      const onnxAssetBase = `${import.meta.env.BASE_URL}onnx/`;
      this.ort.env.wasm.wasmPaths = {
        wasm: `${onnxAssetBase}ort-wasm-simd-threaded.jsep.wasm`
      };
      this.ort.env.wasm.numThreads = 1;
      this.session = await this.ort.InferenceSession.create(`./models/${this.region}_latest.onnx`);
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

  async loadAll(): Promise<void> {
    await Promise.all([this.loadMetadata(), this.loadCategoryDictionary()]);
    await this.loadModel();
  }

  encode(request: PredictionRequest): EncodedPredictionRequest {
    if (!this.dictionary) {
      throw new Error("カテゴリ辞書が読み込まれていません");
    }

    const unknownId = this.dictionary.unknownId;

    return {
      prefecture: encodeCategory(this.dictionary.prefectures, request.prefecture, unknownId),
      municipality: encodeCategory(this.dictionary.municipalities, request.municipality, unknownId),
      station: encodeCategory(this.dictionary.stations, request.station, unknownId),
      area: request.area,
      age: request.age,
      stationDistance: request.stationDistance,
      roomLayout: encodeCategory(this.dictionary.roomLayouts, request.roomLayout, unknownId),
      buildingType: encodeCategory(this.dictionary.buildingTypes, request.buildingType, unknownId),
      predictionYear: request.predictionYear
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
      return typeof value === "number" ? value : 0;
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

  private toResult(predictedPrice: number, area: number): PredictionResult {
    const mae = this.metadata?.mae ?? 0;

    return {
      predictedPrice,
      pricePerSquareMeter: area > 0 ? predictedPrice / area : 0,
      lowerPrice: Math.max(0, predictedPrice - mae),
      upperPrice: predictedPrice + mae
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
