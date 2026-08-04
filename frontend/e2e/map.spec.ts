import { expect, test } from "@playwright/test";
import {
  mockFailedReverseGeocoding,
  mockSuccessfulGeocoding,
  mockUnsupportedReverseGeocoding
} from "./fixtures/geocoding";
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

    await predictionPage.clickMapCenter();

    await expect(page.getByTestId("prediction-form")).toBeVisible();
    await expect(predictionPage.locationTooltip).toContainText("駅徒歩");
    await expect(predictionPage.locationTooltip).toContainText("千代田区");
    await expect(predictionPage.locationTooltip).toContainText("東京");
    await predictionPage.waitForPredictionResult();
  });

  test("住所検索で地図を移動し物件位置を更新できる", async ({ page }) => {
    await mockSuccessfulGeocoding(page);
    const predictionPage = new PredictionPage(page);
    await predictionPage.goto();

    await predictionPage.searchMap("東京駅");

    await expect(page.getByTestId("prediction-form")).toBeVisible();
    await expect(page.getByLabel("地図検索")).toHaveValue("東京駅");
    await expect(predictionPage.locationTooltip).toContainText("駅徒歩");
    await expect(predictionPage.locationTooltip).toContainText("千代田区");
    await expect(predictionPage.locationTooltip).toContainText("東京");
    await predictionPage.waitForPredictionResult();
  });

  test("対応外地点では古い予測を残さず案内を表示する", async ({ page }) => {
    await mockUnsupportedReverseGeocoding(page);
    const predictionPage = new PredictionPage(page);
    await predictionPage.goto();
    await predictionPage.openDetailsPanel();
    await predictionPage.waitForPredictionResult();

    await predictionPage.clickMapCenter();

    await expect(page.getByText(/対応エリア外です/)).toBeVisible();
    await expect(predictionPage.predictionResult).toContainText("条件を入力して予測してください。");
  });

  test("逆ジオコーディング障害時は古い予測を残さず再選択を案内する", async ({ page }) => {
    await mockFailedReverseGeocoding(page);
    const predictionPage = new PredictionPage(page);
    await predictionPage.goto();
    await predictionPage.openDetailsPanel();
    await predictionPage.waitForPredictionResult();

    await predictionPage.clickMapCenter();

    await expect(page.getByText(/対応エリア外です/)).toBeVisible();
    await expect(predictionPage.predictionResult).toContainText("条件を入力して予測してください。");
  });
});
