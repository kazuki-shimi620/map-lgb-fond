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
    await predictionPage.openDetailsPanel();

    await predictionPage.waitForPredictionResult();
    await expect(page.getByTestId("price-history-chart")).toContainText("価格推移");
    await expect(page.getByText("価格予測に失敗しました")).toHaveCount(0);
    await expect(page.getByText("モデルの読み込みに失敗しました")).toHaveCount(0);
  });

  test("専有面積変更時に予測を自動更新する", async ({ page }) => {
    const predictionPage = new PredictionPage(page);
    await predictionPage.goto();
    await predictionPage.openDetailsPanel();
    await predictionPage.waitForPredictionResult();

    const before = await predictionPage.getPredictedPriceText();
    await predictionPage.fillArea(70);

    await expect(page.getByLabel("面積")).toHaveValue("70");
    await expect.poll(() => predictionPage.getPredictedPriceText()).not.toBe(before);
  });

  test("築年数変更時に予測を自動更新する", async ({ page }) => {
    const predictionPage = new PredictionPage(page);
    await predictionPage.goto();
    await predictionPage.openDetailsPanel();
    await predictionPage.waitForPredictionResult();

    const before = await predictionPage.getPredictedPriceText();
    await predictionPage.fillAge(25);

    await expect(page.getByLabel("築年数")).toHaveValue("25");
    await expect.poll(() => predictionPage.getPredictedPriceText()).not.toBe(before);
  });

  test("学習範囲外の条件では予測結果より前に注意を表示する", async ({ page }) => {
    const predictionPage = new PredictionPage(page);
    await predictionPage.goto();
    await predictionPage.openDetailsPanel();
    await predictionPage.waitForPredictionResult();

    await predictionPage.fillArea(200);

    const warning = page.getByRole("status", { name: "予測の注意事項" });
    await expect(warning).toBeVisible();
    await expect(warning).toContainText("面積200㎡");
    await expect(warning).toContainText("学習範囲");
    await expect(warning).toContainText("予測誤差が大きくなる可能性があります");
  });

  test("類似取引を確認できない条件では価格より前に注意を表示する", async ({ page }) => {
    await page.route("**/histories/tokyo_latest_history.json", async (route) => {
      await route.fulfill({ json: [] });
    });
    const predictionPage = new PredictionPage(page);
    await predictionPage.goto();
    await predictionPage.openDetailsPanel();
    await predictionPage.waitForPredictionResult();

    const warning = page.getByRole("status", { name: "予測の注意事項" });
    await expect(warning).toBeVisible();
    await expect(warning).toContainText("同じ駅の直近データを確認できません");
    await expect(warning).toContainText("モデル全体の傾向による参考値");
  });

  test("間取りを変更できる", async ({ page }) => {
    const predictionPage = new PredictionPage(page);
    await predictionPage.goto();
    await predictionPage.openDetailsPanel();
    await predictionPage.waitForPredictionResult();

    await predictionPage.selectRoomLayout("3LDK");

    await expect(predictionPage.selectTrigger("間取り")).toContainText("3LDK");
    await predictionPage.waitForPredictionResult();
  });

  test("建物構造変更時に予測を自動更新する", async ({ page }) => {
    const predictionPage = new PredictionPage(page);
    await predictionPage.goto();
    await predictionPage.openDetailsPanel();
    await predictionPage.waitForPredictionResult();

    const before = await predictionPage.getPredictedPriceText();
    await predictionPage.selectBuildingType("ＳＲＣ");

    await expect(predictionPage.selectTrigger("建物構造")).toContainText("ＳＲＣ");
    await expect.poll(() => predictionPage.getPredictedPriceText()).not.toBe(before);
  });
});
