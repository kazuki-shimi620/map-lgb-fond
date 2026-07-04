import type { ModelAsset, ModelManifest } from "../../types/assets";
import type { SupportedRegion } from "../../types/prediction";
import { fetchJson } from "../../services/http";

export type ModelLoadPriority = "critical" | "high" | "idle";

type DownloadTask = {
  asset: ModelAsset;
  key: string;
  priority: ModelLoadPriority;
  controller: AbortController;
  promise: Promise<ArrayBuffer>;
  resolve: (value: ArrayBuffer) => void;
  reject: (reason?: unknown) => void;
};

const CACHE_NAME = "model-assets-v1";
const PRIORITY_VALUE: Record<ModelLoadPriority, number> = {
  critical: 0,
  high: 1,
  idle: 2
};

let manifestPromise: Promise<ModelManifest> | null = null;

function loadManifest() {
  manifestPromise ??= fetchJson<ModelManifest>("./model-manifest.json");
  return manifestPromise;
}

function resolveAssetUrl(asset: ModelAsset) {
  const url = new URL(asset.path, document.baseURI);
  url.searchParams.set("model-version", asset.version);
  return url.href;
}

class ModelAssetLoader {
  private queue: DownloadTask[] = [];
  private pending = new Map<string, DownloadTask>();
  private current: DownloadTask | null = null;

  async load(region: SupportedRegion, priority: ModelLoadPriority = "critical") {
    const manifest = await loadManifest();
    const asset = manifest.models[region];
    if (!asset) {
      throw new Error(`${region} のモデルはマニフェストに登録されていません`);
    }
    return this.enqueue(asset, priority);
  }

  async prefetchCapitalRegions(activeRegion: SupportedRegion) {
    const connection = (navigator as Navigator & {
      connection?: { saveData?: boolean; effectiveType?: string };
    }).connection;
    if (connection?.saveData || connection?.effectiveType === "slow-2g" || connection?.effectiveType === "2g") {
      return;
    }

    const manifest = await loadManifest();
    const regions = manifest.capitalRegionPriority.filter(
      (region): region is SupportedRegion => region !== activeRegion && region in manifest.models
    );
    await Promise.allSettled(regions.map((region) => this.load(region, "idle")));
  }

  interruptIdleDownloads() {
    if (this.current?.priority === "idle") {
      this.current.controller.abort();
    }
    const interrupted = this.queue.filter((task) => task.priority === "idle");
    this.queue = this.queue.filter((task) => task.priority !== "idle");
    for (const task of interrupted) {
      this.pending.delete(task.key);
      task.reject(new DOMException("Background model download was interrupted", "AbortError"));
    }
  }

  private enqueue(asset: ModelAsset, priority: ModelLoadPriority) {
    const key = resolveAssetUrl(asset);
    const existing = this.pending.get(key);
    if (existing) {
      if (PRIORITY_VALUE[priority] < PRIORITY_VALUE[existing.priority]) {
        existing.priority = priority;
        this.sortQueue();
      }
      return existing.promise;
    }

    let resolve!: (value: ArrayBuffer) => void;
    let reject!: (reason?: unknown) => void;
    const promise = new Promise<ArrayBuffer>((nextResolve, nextReject) => {
      resolve = nextResolve;
      reject = nextReject;
    });
    const task: DownloadTask = {
      asset,
      key,
      priority,
      controller: new AbortController(),
      promise,
      resolve,
      reject
    };

    this.pending.set(key, task);
    this.queue.push(task);
    this.sortQueue();

    if (priority === "critical" && this.current && this.current.key !== key) {
      this.current.controller.abort();
    }
    void this.processNext();
    return promise;
  }

  private sortQueue() {
    this.queue.sort((left, right) => PRIORITY_VALUE[left.priority] - PRIORITY_VALUE[right.priority]);
  }

  private async processNext() {
    if (this.current) {
      return;
    }

    const task = this.queue.shift();
    if (!task) {
      return;
    }

    this.current = task;
    try {
      task.resolve(await this.readAsset(task));
    } catch (error) {
      task.reject(error);
    } finally {
      this.pending.delete(task.key);
      this.current = null;
      void this.processNext();
    }
  }

  private async readAsset(task: DownloadTask) {
    if (!("caches" in window)) {
      return this.fetchAsset(task);
    }

    const request = new Request(task.key);
    let cache: Cache;
    try {
      cache = await caches.open(CACHE_NAME);
      const cached = await cache.match(request);
      if (cached) {
        return cached.arrayBuffer();
      }
    } catch {
      return this.fetchAsset(task);
    }

    const response = await fetch(request, { signal: task.controller.signal });
    if (!response.ok) {
      throw new Error(`Failed to load ${task.asset.path}: ${response.status}`);
    }
    try {
      await cache.put(request, response.clone());
      await this.removePreviousVersions(cache, request);
    } catch {
      // Cache Storage is an optimization; quota errors must not block prediction.
    }
    return response.arrayBuffer();
  }

  private async fetchAsset(task: DownloadTask) {
    const response = await fetch(task.key, { signal: task.controller.signal });
    if (!response.ok) {
      throw new Error(`Failed to load ${task.asset.path}: ${response.status}`);
    }
    return response.arrayBuffer();
  }

  private async removePreviousVersions(cache: Cache, currentRequest: Request) {
    const currentUrl = new URL(currentRequest.url);
    const requests = await cache.keys();
    await Promise.all(
      requests.map((request) => {
        const url = new URL(request.url);
        return url.pathname === currentUrl.pathname && url.href !== currentUrl.href
          ? cache.delete(request)
          : Promise.resolve(false);
      })
    );
  }
}

export const modelAssetLoader = new ModelAssetLoader();
