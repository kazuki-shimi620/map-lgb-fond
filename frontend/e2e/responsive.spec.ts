import { expect, test } from "@playwright/test";
import { mockSuccessfulGeocoding } from "./fixtures/geocoding";
import { PredictionPage } from "./pages/prediction-page";

test.describe("レスポンシブ表示", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("https://*.tile.openstreetmap.org/**", async (route) => {
      await route.abort();
    });
  });

  test("デスクトップで主要パネルを表示できる", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    const predictionPage = new PredictionPage(page);
    await predictionPage.goto();
    await predictionPage.waitForPredictionResult();

    await expect(page.getByTestId("property-map")).toBeVisible();
    await expect(page.getByTestId("prediction-form")).toBeVisible();
    await expect(page.getByTestId("prediction-result")).toBeVisible();
    await expect(page.getByTestId("price-history-chart")).toBeVisible();

    const hasHorizontalOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth
    );
    expect(hasHorizontalOverflow).toBe(false);
  });

  test("スマートフォンでボトムシートを表示できる", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await mockSuccessfulGeocoding(page);
    const predictionPage = new PredictionPage(page);
    await predictionPage.goto();

    await expect(page.getByTestId("property-map")).toBeVisible();
    await expect(page.getByTestId("prediction-sheet")).toBeVisible();
    await expect(page.getByTestId("sheet-handle")).toBeVisible();

    await predictionPage.clickMapCenter();
    await expect(page.getByText("地図から自動算出")).toBeVisible();

    const hasHorizontalOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth
    );
    expect(hasHorizontalOverflow).toBe(false);
  });
});
