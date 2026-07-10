export type HazardType =
  | "flood"
  | "inland_flood"
  | "landslide"
  | "tsunami"
  | "storm_surge"
  | "flood_collapse"
  | "flood_duration"
  | "shelter";

export type HazardStatus =
  | "affected"
  | "not_affected"
  | "unknown"
  | "not_applicable";

export type RiskLevel = 0 | 1 | 2 | 3 | 4 | 5;

export type HazardDetail = {
  status: HazardStatus;
  riskLevel: RiskLevel | null;
  score: number | null;
  depth?: {
    min: number | null;
    max: number | null;
    unit: "m";
    category: string | null;
  } | null;
  zoneType?: string | null;
  scenario?: string | null;
  message: string;
  sourceAvailable: boolean;
};

export type HazardAssessmentResponse = {
  location: {
    latitude: number;
    longitude: number;
    meshCode?: string | null;
    h3Index?: string | null;
  };
  assessment: {
    score: number | null;
    grade: string | null;
    level: "low" | "moderate" | "high" | "unknown";
    label: string;
    confidence: "low" | "medium" | "high" | "unknown";
    evaluatedHazardCount: number;
    availableHazardCount: number;
  };
  hazards: Partial<Record<HazardType, HazardDetail>>;
  metadata: {
    scoringVersion: string;
    dataSource: string[];
    evaluatedAt: string;
    disclaimer: string;
  };
};
