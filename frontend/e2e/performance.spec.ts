import { expect, test } from "@playwright/test";
import { PredictionPage } from "./pages/prediction-page";

test("初期表示と周辺施設パネルの性能予算を記録する", async ({ page }, testInfo) => {
  await page.addInitScript(() => {
    const durations: number[] = [];
    (window as Window & { __longTaskDurations?: number[] }).__longTaskDurations = durations;
    new PerformanceObserver((list) => {
      durations.push(...list.getEntries().map((entry) => entry.duration));
    }).observe({ type: "longtask", buffered: true });
  });

  const predictionPage = new PredictionPage(page);
  const navigationStartedAt = Date.now();
  await predictionPage.goto();
  await expect(page.getByTestId("property-map")).toBeVisible();
  await predictionPage.openDetailsPanel();
  await predictionPage.waitForPredictionResult();
  const initialPredictionMs = Date.now() - navigationStartedAt;

  const previousPrice = await predictionPage.getPredictedPriceText();
  const repeatStartedAt = performance.now();
  await predictionPage.fillArea(56);
  await expect(predictionPage.predictionResult.locator(".price-main").first()).not.toHaveText(
    previousPrice
  );
  const repeatPredictionMs = performance.now() - repeatStartedAt;

  const mapBox = await predictionPage.map.boundingBox();
  const frameRatePromise = page.evaluate(async () => {
    let frameCount = 0;
    const startedAt = performance.now();
    await new Promise<void>((resolve) => {
      const measure = (now: number) => {
        frameCount += 1;
        if (now - startedAt >= 700) {
          resolve();
          return;
        }
        requestAnimationFrame(measure);
      };
      requestAnimationFrame(measure);
    });
    const durationMs = performance.now() - startedAt;
    return Math.round((frameCount * 1000 * 10) / durationMs) / 10;
  });
  if (mapBox) {
    await page.mouse.move(mapBox.x + mapBox.width * 0.55, mapBox.y + mapBox.height * 0.5);
    await page.mouse.down();
    await page.mouse.move(mapBox.x + mapBox.width * 0.35, mapBox.y + mapBox.height * 0.5, {
      steps: 12
    });
    await page.mouse.up();
  }
  const mapDragFps = await frameRatePromise;

  const facilityButton = page
    .getByRole("region", { name: "地図" })
    .getByRole("button", { name: "周辺施設" });
  await expect(facilityButton).toBeEnabled();
  await expect(page.locator(".leaflet-overlay-pane canvas")).toBeVisible();

  const panelStartedAt = performance.now();
  await facilityButton.click();
  await expect(page.getByTestId("facility-layer-control")).toBeVisible();
  const panelLatencyMs = performance.now() - panelStartedAt;

  const browserMetrics = await page.evaluate(() => {
    const resources = performance.getEntriesByType("resource") as PerformanceResourceTiming[];
    const facilityResource = resources.find((entry) =>
      entry.name.endsWith("/facilities/nearby_facilities.json")
    );
    const longTasks =
      (window as Window & { __longTaskDurations?: number[] }).__longTaskDurations ?? [];
    const sameOriginResources = resources.filter(
      (entry) => new URL(entry.name).origin === window.location.origin
    );
    const sumDecoded = (pattern: RegExp) =>
      sameOriginResources
        .filter((entry) => pattern.test(new URL(entry.name).pathname))
        .reduce((total, entry) => total + entry.decodedBodySize, 0);
    const performanceWithMemory = performance as Performance & {
      memory?: { usedJSHeapSize?: number };
    };
    const loadedAssets = sameOriginResources
      .filter((entry) => entry.decodedBodySize > 0)
      .map((entry) => ({
        path: new URL(entry.name).pathname,
        decodedBytes: entry.decodedBodySize,
        transferBytes: entry.transferSize
      }))
      .sort((left, right) => right.decodedBytes - left.decodedBytes);
    return {
      facilityDecodedBytes: facilityResource?.decodedBodySize ?? 0,
      sessionDecodedBytes: sameOriginResources.reduce(
        (total, entry) => total + entry.decodedBodySize,
        0
      ),
      sessionTransferBytes: sameOriginResources.reduce(
        (total, entry) => total + entry.transferSize,
        0
      ),
      modelDecodedBytes: sumDecoded(/\/models\/.*\.onnx$/),
      wasmDecodedBytes: sumDecoded(/\/onnx\/.*\.wasm$/),
      metadataDecodedBytes: sumDecoded(/\/metadata\/.*\.json$/),
      historyDecodedBytes: sumDecoded(/\/histories\/.*\.json$/),
      facilityAssetsDecodedBytes: sumDecoded(/\/facilities\/.*\.json$/),
      urbanPlanningDecodedBytes: sumDecoded(/\/urban-planning\/.*\.json$/),
      usedJSHeapBytes: performanceWithMemory.memory?.usedJSHeapSize ?? null,
      facilityCanvasCount: document.querySelectorAll(".leaflet-overlay-pane canvas").length,
      overlaySvgPathCount: document.querySelectorAll(".leaflet-overlay-pane svg path").length,
      longTaskCount: longTasks.length,
      longestTaskMs: Math.max(0, ...longTasks),
      totalLongTaskMs: longTasks.reduce((total, duration) => total + duration, 0),
      loadedAssets
    };
  });

  const metrics = {
    initialPredictionMs,
    repeatPredictionMs: Math.round(repeatPredictionMs),
    mapDragFps,
    panelLatencyMs: Math.round(panelLatencyMs),
    ...browserMetrics
  };
  const { loadedAssets, ...summaryMetrics } = metrics;
  console.info(`performance metrics: ${JSON.stringify(summaryMetrics)}`);
  await testInfo.attach("performance-metrics.json", {
    body: JSON.stringify(metrics, null, 2),
    contentType: "application/json"
  });

  expect(metrics.panelLatencyMs).toBeLessThan(300);
  expect(metrics.initialPredictionMs).toBeLessThan(12_000);
  expect(metrics.repeatPredictionMs).toBeLessThan(3_000);
  expect(metrics.sessionTransferBytes).toBeLessThan(40_000_000);
  expect(metrics.sessionDecodedBytes).toBeLessThan(130_000_000);
  expect(metrics.facilityDecodedBytes).toBeGreaterThan(0);
  expect(metrics.facilityDecodedBytes).toBeLessThan(3_800_000);
  expect(metrics.facilityCanvasCount).toBeGreaterThan(0);
});
