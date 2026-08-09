import { expect, test } from "@playwright/test";
import { mockSuccessfulGeocoding } from "./fixtures/geocoding";
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
    await predictionPage.openDetailsPanel();
    await predictionPage.waitForPredictionResult();

    await expect(page.getByTestId("property-map")).toBeVisible();
    await expect(page.getByTestId("prediction-form")).toBeVisible();
    await expect(page.getByTestId("prediction-forecast-controls")).toBeVisible();
    await expect(page.getByRole("radiogroup", { name: "将来シナリオ" })).toBeVisible();
    await expect(page.getByTestId("prediction-result")).toBeVisible();
    await expect(page.getByTestId("price-history-chart")).toBeVisible();
    await expect(page.getByTestId("supporting-info-tabs")).toBeVisible();
    await expect(page.getByTestId("commercial-facility-card")).toBeVisible();

    await page.getByRole("tab", { name: "駅規模" }).click();
    await expect(page.getByTestId("station-scale-card")).toBeVisible();

    await page.getByRole("tab", { name: "災害リスク" }).click();
    await expect(page.getByTestId("hazard-risk-card")).toBeVisible();

    await page.getByRole("tab", { name: "モデル" }).click();
    await expect(page.getByTestId("model-detail-panel")).toBeVisible();

    const panelOrder = await page.evaluate(() => {
      const ids = [
        "property-map",
        "prediction-form",
        "prediction-result",
        "price-history-chart",
        "supporting-info-tabs"
      ];
      return ids.map((id) => document.querySelector(`[data-testid="${id}"]`)).every(Boolean)
        ? ids.every((id, index) => {
            if (index === 0) {
              return true;
            }
            const previous = document.querySelector(`[data-testid="${ids[index - 1]}"]`);
            const current = document.querySelector(`[data-testid="${id}"]`);
            return Boolean(previous?.compareDocumentPosition(current!) & Node.DOCUMENT_POSITION_FOLLOWING);
          })
        : false;
    });
    expect(panelOrder).toBe(true);

    const desktopMapSidebarLayout = await page.evaluate(() => {
      const map = document.querySelector('[data-testid="property-map"]');
      const sheet = document.querySelector('[data-testid="prediction-sheet"]');
      if (!map || !sheet) {
        return false;
      }
      const mapRect = map.getBoundingClientRect();
      const sheetRect = sheet.getBoundingClientRect();
      return (
        mapRect.width >= window.innerWidth - 1 &&
        mapRect.height >= window.innerHeight - 1 &&
        sheetRect.left <= 1 &&
        sheetRect.top <= 1 &&
        sheetRect.width >= 320
      );
    });
    expect(desktopMapSidebarLayout).toBe(true);

    const hasHorizontalOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth
    );
    expect(hasHorizontalOverflow).toBe(false);
  });

  test("スマートフォンでボトムシートを表示できる", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.addInitScript(() => {
      window.localStorage.setItem("map-lgb-fond:onboarding-completed", "1");
    });
    await mockSuccessfulGeocoding(page);
    const predictionPage = new PredictionPage(page);
    await predictionPage.goto();

    await expect(page.getByTestId("property-map")).toBeVisible();
    await expect(page.getByTestId("prediction-sheet")).toBeVisible();
    await expect(page.getByTestId("sheet-handle")).toBeVisible();

    await predictionPage.openDetailsPanel();
    await expect(page.getByTestId("prediction-sheet")).not.toHaveClass(/sheet-collapsed/);
    await expect(page.getByRole("button", { name: "使い方" })).toHaveCount(0);
    await predictionPage.map.getByRole("button", { name: "周辺施設" }).click();
    await expect(page.getByTestId("prediction-sheet")).toHaveClass(/sheet-collapsed/);
    await expect(page.getByTestId("facility-layer-control")).toBeVisible();
    await expect(page.getByRole("button", { name: "使い方" })).toHaveCount(0);
    await expect(page.getByText("小規模", { exact: true })).toBeVisible();
    await expect(page.getByText("美術館・ギャラリー", { exact: true })).toBeVisible();
    await expect(page.getByText("博物館・資料館", { exact: true })).toBeVisible();
    await expect(page.getByText("銭湯", { exact: true })).toBeVisible();
    await expect(page.getByText("スーパー銭湯・スパ", { exact: true })).toBeVisible();
    await expect(page.getByText("シネコン", { exact: true })).toBeVisible();
    await expect(page.getByText("ミニシアター・その他", { exact: true })).toBeVisible();

    await predictionPage.map.getByRole("button", { name: "ハザード" }).click();
    await expect(page.getByTestId("facility-layer-control")).toHaveCount(0);
    await expect(page.getByTestId("hazard-layer-control")).toBeVisible();
    await expect(page.getByRole("button", { name: "使い方" })).toHaveCount(0);
    await page.getByRole("button", { name: "ハザードを閉じる" }).click();
    await expect(page.getByRole("button", { name: "使い方" })).toBeVisible();

    await predictionPage.clickMapCenter();
    await expect(predictionPage.locationTooltip).toContainText("駅徒歩");

    const formMatchesSheetWidth = await page.evaluate(() => {
      const sheet = document.querySelector('[data-testid="prediction-sheet"]');
      const form = document.querySelector('[data-testid="prediction-form"]');
      if (!sheet || !form) {
        return false;
      }
      const sheetRect = sheet.getBoundingClientRect();
      const formRect = form.getBoundingClientRect();
      return (
        Math.abs(formRect.left - sheetRect.left) <= 1 &&
        Math.abs(formRect.right - sheetRect.right) <= 1
      );
    });
    expect(formMatchesSheetWidth).toBe(true);

    await predictionPage.openDetailsPanel();
    await page.getByTestId("sheet-handle").click();
    await expect(page.getByTestId("prediction-sheet")).toHaveClass(/sheet-collapsed/);
    await expect(page.getByTestId("prediction-form")).toHaveCSS("display", "grid");

    const hasHorizontalOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth
    );
    expect(hasHorizontalOverflow).toBe(false);
  });
});
