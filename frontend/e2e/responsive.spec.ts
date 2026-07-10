import { expect, test } from "@playwright/test";
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
});
