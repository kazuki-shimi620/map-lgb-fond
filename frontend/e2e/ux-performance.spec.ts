import { expect, test } from "@playwright/test";
import { PredictionPage } from "./pages/prediction-page";

test("初回予測を確認するまでの時間と操作回数を計測する", async ({ page }, testInfo) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("map-lgb-fond:onboarding-completed", "1");
  });
  const predictionPage = new PredictionPage(page);
  const startedAt = Date.now();
  await predictionPage.goto();

  const sheet = page.getByTestId("prediction-sheet");
  const wasCollapsed = (await sheet.getAttribute("class"))?.includes("sheet-collapsed") ?? false;
  const operationCount = wasCollapsed ? 1 : 0;
  await predictionPage.openDetailsPanel();
  await predictionPage.waitForPredictionResult();
  const elapsedMs = Date.now() - startedAt;
  const metric = {
    project: testInfo.project.name,
    elapsedMs,
    operationCount
  };

  console.log(`UX_METRIC ${JSON.stringify(metric)}`);
  await testInfo.attach("ux-metric", {
    body: JSON.stringify(metric, null, 2),
    contentType: "application/json"
  });
  expect(operationCount).toBeLessThanOrEqual(1);
  expect(elapsedMs).toBeLessThan(12_000);
});
