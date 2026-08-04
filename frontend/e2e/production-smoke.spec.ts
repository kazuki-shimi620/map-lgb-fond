import { expect, test } from "@playwright/test";
import { PredictionPage } from "./pages/prediction-page";

test.describe("公開サイトスモーク", () => {
  test.skip(!process.env.PRODUCTION_SMOKE, "公開サイト監視時だけ実行する");

  test("初期表示・モデル取得・価格予測・地図選択が動作する", async ({ page }) => {
    const failedAssets: string[] = [];
    page.on("response", (response) => {
      if (
        response.status() >= 400 &&
        /\/(models|metadata|stations)\//.test(response.url())
      ) {
        failedAssets.push(`${response.status()} ${response.url()}`);
      }
    });

    const predictionPage = new PredictionPage(page);
    await predictionPage.goto();
    await predictionPage.openDetailsPanel();
    await predictionPage.expectLoaded();
    await predictionPage.waitForPredictionResult();

    await predictionPage.clickMapCenter();
    await expect(predictionPage.locationTooltip).toContainText("駅徒歩");
    await predictionPage.waitForPredictionResult();

    expect(failedAssets).toEqual([]);
    await expect(page.getByText("モデルの読み込みに失敗しました")).toHaveCount(0);
    await expect(page.getByText("価格予測に失敗しました")).toHaveCount(0);
  });
});
