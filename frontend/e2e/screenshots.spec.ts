import { mkdir } from "node:fs/promises";
import path from "node:path";

import { test } from "@playwright/test";

import { mockSuccessfulGeocoding } from "./fixtures/geocoding";
import { PredictionPage } from "./pages/prediction-page";

const screenshotsDir = path.resolve(process.cwd(), "../docs/images");

test.skip(
  process.env.README_SCREENSHOTS !== "1",
  "README用スクリーンショット生成コマンドでだけ実行する"
);

async function prepareReadmeView(page: PredictionPage) {
  await mockSuccessfulGeocoding(page.page);
  await page.goto();
  await page.expectLoaded();
  await page.openDetailsPanel();
  await page.waitForPredictionResult();
}

test.beforeEach(async () => {
  await mkdir(screenshotsDir, { recursive: true });
});

test("README用デスクトップ画面を生成する", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const predictionPage = new PredictionPage(page);
  await prepareReadmeView(predictionPage);

  await page.screenshot({
    path: path.join(screenshotsDir, "app-desktop.png"),
    fullPage: true,
    animations: "disabled"
  });
});

test("README用の予測結果画像を生成する", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const predictionPage = new PredictionPage(page);
  await prepareReadmeView(predictionPage);

  await predictionPage.predictionResult.screenshot({
    path: path.join(screenshotsDir, "app-prediction-result.png"),
    animations: "disabled"
  });
});

test("README用の価格推移グラフ画像を生成する", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const predictionPage = new PredictionPage(page);
  await prepareReadmeView(predictionPage);

  await predictionPage.priceHistory.screenshot({
    path: path.join(screenshotsDir, "app-price-history.png"),
    animations: "disabled"
  });
});

test("README用スマートフォン画面を生成する", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockSuccessfulGeocoding(page);
  const predictionPage = new PredictionPage(page);
  await predictionPage.goto();
  await predictionPage.clickMapCenter();
  await predictionPage.openDetailsPanel();
  await predictionPage.waitForPredictionResult();

  await page.screenshot({
    path: path.join(screenshotsDir, "app-mobile.png"),
    fullPage: true,
    animations: "disabled"
  });
});
