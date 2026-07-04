import { ModelManager } from "./ModelManager";
import type { SupportedRegion } from "../../types/prediction";
import { modelAssetLoader } from "./modelAssetLoader";

const managers = new Map<SupportedRegion, ModelManager>();
const recentRegions: SupportedRegion[] = [];
const MAX_ACTIVE_SESSIONS = 2;
let scheduledIdleCallback: number | null = null;
let scheduledTimeout: number | null = null;

export function getModelManager(region: SupportedRegion): ModelManager {
  const current = managers.get(region);
  if (current) {
    return current;
  }

  const manager = new ModelManager(region);
  managers.set(region, manager);
  return manager;
}

export function markModelManagerUsed(region: SupportedRegion) {
  const currentIndex = recentRegions.indexOf(region);
  if (currentIndex >= 0) {
    recentRegions.splice(currentIndex, 1);
  }
  recentRegions.push(region);

  while (recentRegions.length > MAX_ACTIVE_SESSIONS) {
    const oldestRegion = recentRegions.shift();
    if (oldestRegion) {
      void managers.get(oldestRegion)?.release();
    }
  }
}

export function prefetchCapitalRegionModels(activeRegion: SupportedRegion) {
  cancelScheduledPrefetch();
  const schedule = () => void modelAssetLoader.prefetchCapitalRegions(activeRegion);
  const idleCallback = (window as Window & {
    requestIdleCallback?: (callback: () => void, options?: { timeout: number }) => number;
  }).requestIdleCallback;
  if (idleCallback) {
    scheduledIdleCallback = idleCallback(() => {
      scheduledIdleCallback = null;
      schedule();
    }, { timeout: 3000 });
    return;
  }
  scheduledTimeout = window.setTimeout(() => {
    scheduledTimeout = null;
    schedule();
  }, 1000);
}

export function interruptModelPrefetch() {
  cancelScheduledPrefetch();
  modelAssetLoader.interruptIdleDownloads();
}

function cancelScheduledPrefetch() {
  if (scheduledIdleCallback !== null) {
    (window as Window & { cancelIdleCallback?: (handle: number) => void }).cancelIdleCallback?.(
      scheduledIdleCallback
    );
    scheduledIdleCallback = null;
  }
  if (scheduledTimeout !== null) {
    window.clearTimeout(scheduledTimeout);
    scheduledTimeout = null;
  }
}
