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

  test("専有面積変更時に予測を自動更新する", async ({ page }) => {
    const predictionPage = new PredictionPage(page);
    await predictionPage.goto();
    await predictionPage.waitForPredictionResult();

    const before = await predictionPage.getPredictedPriceText();
    await predictionPage.fillArea(70);

    await expect(page.getByLabel("面積")).toHaveValue("70");
    await expect.poll(() => predictionPage.getPredictedPriceText()).not.toBe(before);
  });

  test("築年数変更時に予測を自動更新する", async ({ page }) => {
    const predictionPage = new PredictionPage(page);
    await predictionPage.goto();
    await predictionPage.waitForPredictionResult();

    const before = await predictionPage.getPredictedPriceText();
    await predictionPage.fillAge(25);

    await expect(page.getByLabel("築年数")).toHaveValue("25");
    await expect.poll(() => predictionPage.getPredictedPriceText()).not.toBe(before);
  });

  test("駅徒歩変更時に手入力値で予測を自動更新する", async ({ page }) => {
    const predictionPage = new PredictionPage(page);
    await predictionPage.goto();
    await predictionPage.waitForPredictionResult();

    const before = await predictionPage.getPredictedPriceText();
    await predictionPage.fillStationDistance(15);

    await expect(page.getByLabel("駅徒歩")).toHaveValue("15");
    await expect(page.getByText("手入力")).toBeVisible();
    await expect.poll(() => predictionPage.getPredictedPriceText()).not.toBe(before);
  });

  test("都道府県変更時に地域モデルを切り替える", async ({ page }) => {
    const predictionPage = new PredictionPage(page);
    await predictionPage.goto();
    await predictionPage.waitForPredictionResult();

    await predictionPage.selectPrefecture("埼玉県");
    await expect(page.getByTestId("prediction-result")).toContainText(
      "条件を入力して予測してください。"
    );

    await predictionPage.fillMunicipality("さいたま市");
    await predictionPage.fillStation("大宮");
    await predictionPage.waitForPredictionResult();
    await expect(predictionPage.selectTrigger("都道府県")).toContainText("埼玉県");
  });
});
