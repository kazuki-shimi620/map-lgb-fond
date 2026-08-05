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
    await page.getByRole("tab", { name: "モデル" }).click();
    await expect(page.getByLabel("近い条件の検証結果")).toBeVisible();
    const reasons = page.getByLabel("予測価格の主な理由");
    await expect(reasons).toBeVisible();
    await expect(reasons).toContainText("因果関係や査定額への効果を示すものではありません");
    expect(Number(await reasons.getAttribute("data-compute-ms"))).toBeLessThan(200);
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

  test("モデル詳細に近い条件の検証件数と誤差を表示する", async ({ page }) => {
    await page.route("**/metadata/tokyo_latest_metadata.json", async (route) => {
      const response = await route.fetch();
      const metadata = await response.json();
      const metricRow = (label: string, count = 500) => ({
        label,
        count,
        metrics: count >= 100 ? { mae: 4_000_000, rmse: 5_000_000, mape: 12 } : null,
        residualQuantiles: count >= 100 ? { p025: -8_000_000, p975: 9_000_000 } : null
      });
      metadata.evaluation.segments = {
        minimumSampleCount: 100,
        dimensions: {
          price: [
            metricRow("3000万円未満"),
            metricRow("3000〜5000万円"),
            metricRow("5000〜8000万円"),
            metricRow("8000万円以上")
          ],
          age: [metricRow("築10〜19年", 420)],
          area: [metricRow("40〜59㎡", 380)],
          prefecture: [metricRow("東京都", 3_200)]
        }
      };
      await route.fulfill({ response, json: metadata });
    });
    const predictionPage = new PredictionPage(page);
    await predictionPage.goto();
    await predictionPage.openDetailsPanel();
    await predictionPage.waitForPredictionResult();
    await page.getByRole("tab", { name: "モデル" }).click();

    const evaluation = page.getByLabel("近い条件の検証結果");
    await expect(evaluation).toBeVisible();
    await expect(evaluation).toContainText("築年数帯: 築10〜19年");
    await expect(evaluation).toContainText("面積帯: 40〜59㎡");
    await expect(evaluation).toContainText("MAE 400万円");
    await expect(evaluation).toContainText("420件");
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

  test("建物構造を変更しても予測エラーにならない", async ({ page }) => {
    const predictionPage = new PredictionPage(page);
    await predictionPage.goto();
    await predictionPage.openDetailsPanel();
    await predictionPage.waitForPredictionResult();

    await predictionPage.selectBuildingType("ＳＲＣ");

    await expect(predictionPage.selectTrigger("建物構造")).toContainText("ＳＲＣ");
    await predictionPage.waitForPredictionResult();
    await expect(page.getByText("価格予測に失敗しました")).toHaveCount(0);
  });
});
