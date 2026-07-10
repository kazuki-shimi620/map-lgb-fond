import { expect, test } from "@playwright/test";
import { PredictionPage } from "./pages/prediction-page";

test.describe("価格予測", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("https://*.tile.openstreetmap.org/**", async (route) => {
      await route.abort();
    });
  });

  test("初期条件で価格を予測できる", async ({ page }) => {
    const predictionPage = new PredictionPage(page);
    await predictionPage.goto();

    await predictionPage.waitForPredictionResult();
    await expect(page.getByTestId("price-history-chart")).toContainText("価格推移");
    await expect(page.getByText("価格予測に失敗しました")).toHaveCount(0);
    await expect(page.getByText("モデルの読み込みに失敗しました")).toHaveCount(0);
  });
});
