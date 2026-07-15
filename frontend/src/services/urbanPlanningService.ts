import type { UrbanPlanningCollection } from "../types/assets";
import { fetchJson } from "./http";

let urbanPlanningPromise: Promise<UrbanPlanningCollection> | null = null;

export function loadUrbanPlanningCollection(): Promise<UrbanPlanningCollection> {
  urbanPlanningPromise ??= fetchJson<UrbanPlanningCollection>(
    "./urban-planning/urban_planning_areas.json"
  );
  return urbanPlanningPromise;
}
