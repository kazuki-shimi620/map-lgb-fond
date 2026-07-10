import { expect, test } from "@playwright/test";
import { mockSuccessfulGeocoding } from "./fixtures/geocoding";
import { PredictionPage } from "./pages/prediction-page";

test.describe("地図操作", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("https://*.tile.openstreetmap.org/**", async (route) => {
      await route.abort();
    });
  });

  test("地図クリックで物件位置を変更できる", async ({ page }) => {
    await mockSuccessfulGeocoding(page);
    const predictionPage = new PredictionPage(page);
    await predictionPage.goto();
    await predictionPage.waitForPredictionResult();

    await predictionPage.clickMapCenter();

    await expect(page.getByText("地図から自動算出")).toBeVisible();
    await expect(page.getByLabel("市区町村")).toHaveValue("千代田区");
    await expect(page.getByLabel("最寄駅")).toHaveValue("東京");
    await predictionPage.waitForPredictionResult();
  });
});
