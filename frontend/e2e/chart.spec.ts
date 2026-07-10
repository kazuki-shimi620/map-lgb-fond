import { expect, test } from "@playwright/test";
import { PredictionPage } from "./pages/prediction-page";

test.describe("価格推移グラフ", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("https://*.tile.openstreetmap.org/**", async (route) => {
      await route.abort();
    });
  });

  test("価格推移グラフを表示できる", async ({ page }) => {
    const predictionPage = new PredictionPage(page);
    await predictionPage.goto();
    await predictionPage.waitForPredictionResult();

    await expect(predictionPage.priceHistory).toContainText("価格推移");
    await expect(predictionPage.priceHistory.getByText("対象駅の類似実績")).toBeVisible();
    await expect(predictionPage.priceHistory.getByText("入力条件の予測")).toBeVisible();
  });

  test("過去データを追加表示して閉じられる", async ({ page }) => {
    const predictionPage = new PredictionPage(page);
    await predictionPage.goto();
    await predictionPage.waitForPredictionResult();

    await predictionPage.loadArchiveHistory();
    await expect(
      predictionPage.priceHistory.getByRole("button", { name: /年以降の表示に戻す/ })
    ).toBeVisible();

    await predictionPage.closeArchiveHistory();
    await expect(
      predictionPage.priceHistory.getByRole("button", { name: /以前の実績を表示/ })
    ).toBeVisible();
  });
});
