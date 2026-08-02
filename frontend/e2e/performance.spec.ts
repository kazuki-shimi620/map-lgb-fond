import { expect, test } from "@playwright/test";

test("初期表示と周辺施設パネルの性能予算を記録する", async ({ page }, testInfo) => {
  await page.addInitScript(() => {
    const durations: number[] = [];
    (window as Window & { __longTaskDurations?: number[] }).__longTaskDurations = durations;
    new PerformanceObserver((list) => {
      durations.push(...list.getEntries().map((entry) => entry.duration));
    }).observe({ type: "longtask", buffered: true });
  });

  await page.goto("./");
  await expect(page.getByTestId("property-map")).toBeVisible();

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
    return {
      facilityDecodedBytes: facilityResource?.decodedBodySize ?? 0,
      facilityCanvasCount: document.querySelectorAll(".leaflet-overlay-pane canvas").length,
      overlaySvgPathCount: document.querySelectorAll(".leaflet-overlay-pane svg path").length,
      longTaskCount: longTasks.length,
      longestTaskMs: Math.max(0, ...longTasks),
      totalLongTaskMs: longTasks.reduce((total, duration) => total + duration, 0)
    };
  });

  const metrics = {
    panelLatencyMs: Math.round(panelLatencyMs),
    ...browserMetrics
  };
  console.info(`performance metrics: ${JSON.stringify(metrics)}`);
  await testInfo.attach("performance-metrics.json", {
    body: JSON.stringify(metrics, null, 2),
    contentType: "application/json"
  });

  expect(metrics.panelLatencyMs).toBeLessThan(300);
  expect(metrics.facilityDecodedBytes).toBeGreaterThan(0);
  expect(metrics.facilityDecodedBytes).toBeLessThan(3_800_000);
  expect(metrics.facilityCanvasCount).toBeGreaterThan(0);
});
