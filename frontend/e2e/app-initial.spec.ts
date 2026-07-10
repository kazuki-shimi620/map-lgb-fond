import { expect, test } from "@playwright/test";
import { PredictionPage } from "./pages/prediction-page";

test.describe("初期表示", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("https://*.tile.openstreetmap.org/**", async (route) => {
      await route.abort();
    });
  });

  test("アプリケーションを表示できる", async ({ page }) => {
    const pageErrors: Error[] = [];
    page.on("pageerror", (error) => pageErrors.push(error));

    const predictionPage = new PredictionPage(page);
    await predictionPage.goto();

    await predictionPage.expectLoaded();
    await expect(page.getByTestId("prediction-form")).toBeVisible();
    await expect(page.getByTestId("prediction-result")).toBeVisible();
    await expect(page.getByTestId("price-history-chart")).toBeVisible();
    expect(pageErrors).toHaveLength(0);
  });

  test("初期値が設定される", async ({ page }) => {
    const predictionPage = new PredictionPage(page);
    await predictionPage.goto();

    await predictionPage.expectInitialFormValues();
  });
});
