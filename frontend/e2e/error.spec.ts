import { expect, test } from "@playwright/test";
import { PredictionPage } from "./pages/prediction-page";

test.describe("エラー処理", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("https://*.tile.openstreetmap.org/**", async (route) => {
      await route.abort();
    });
  });

  test("モデル読み込み失敗時にエラーを表示する", async ({ page }) => {
    await page.route("**/model-manifest.json", async (route) => {
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ error: "model manifest unavailable" })
      });
    });

    const predictionPage = new PredictionPage(page);
    await predictionPage.goto();

    await expect(page.getByText("モデルの読み込みに失敗しました")).toBeVisible();
    await expect(predictionPage.predictionResult).toContainText("条件を入力して予測してください。");
  });

  test("駅マスタまたは価格推移データ読み込み失敗時にエラーを表示する", async ({ page }) => {
    await page.route("**/stations/tokyo_stations.json", async (route) => {
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ error: "station master unavailable" })
      });
    });

    const predictionPage = new PredictionPage(page);
    await predictionPage.goto();

    await expect(
      page.getByText("駅マスタまたは価格推移データを読み込めませんでした")
    ).toBeVisible();
  });

  test("価格予測失敗時にエラーを表示する", async ({ page }) => {
    await page.route("**/metadata/tokyo_latest_metadata.json", async (route) => {
      const response = await route.fetch();
      const metadata = await response.json();
      metadata.featureOrder = [...metadata.featureOrder, "__e2e_invalid_extra_feature"];
      await route.fulfill({
        response,
        contentType: "application/json",
        body: JSON.stringify(metadata)
      });
    });

    const predictionPage = new PredictionPage(page);
    await predictionPage.goto();

    await expect(page.getByText("価格予測に失敗しました")).toBeVisible();
    await expect(predictionPage.predictionResult).toContainText("条件を入力して予測してください。");
  });
});
