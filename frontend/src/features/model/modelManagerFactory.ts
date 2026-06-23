import { ModelManager } from "./ModelManager";
import type { SupportedRegion } from "../../types/prediction";

const managers = new Map<SupportedRegion, ModelManager>();

export function getModelManager(region: SupportedRegion): ModelManager {
  const current = managers.get(region);
  if (current) {
    return current;
  }

  const manager = new ModelManager(region);
  managers.set(region, manager);
  return manager;
}
