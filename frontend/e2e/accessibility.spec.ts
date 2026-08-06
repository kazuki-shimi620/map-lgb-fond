import { expect, test } from "@playwright/test";
import { PredictionPage } from "./pages/prediction-page";

test.describe("キーボードと識別", () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem("map-lgb-fond:onboarding-completed", "1");
    });
  });

  test("主要フォームと参考情報をキーボードだけで操作できる", async ({ page }) => {
    const predictionPage = new PredictionPage(page);
    await predictionPage.goto();
    await predictionPage.openDetailsPanel();
    await predictionPage.waitForPredictionResult();

    const area = page.getByLabel("面積");
    await area.focus();
    await expect(area).toBeFocused();
    expect(await area.evaluate((element) => getComputedStyle(element).outlineStyle)).not.toBe("none");

    await page.keyboard.press("Tab");
    await expect(page.getByLabel("築年数")).toBeFocused();
    await page.keyboard.press("Tab");
    const roomLayout = page.getByRole("button", { name: "間取り" });
    await expect(roomLayout).toBeFocused();
    await page.keyboard.press("ArrowDown");
    await expect(roomLayout).toContainText("3LDK");
    await expect(roomLayout).toBeFocused();

    await page.keyboard.press("Tab");
    const buildingType = page.getByRole("button", { name: "建物構造" });
    await expect(buildingType).toBeFocused();
    await page.keyboard.press("ArrowDown");
    await expect(buildingType).toContainText("ＳＲＣ");

    const modelTab = page.getByRole("tab", { name: "モデル" });
    await modelTab.focus();
    await page.keyboard.press("Enter");
    await expect(modelTab).toHaveAttribute("aria-selected", "true");
    await expect(page.getByTestId("model-detail-panel")).toBeVisible();
  });

  test("選択状態を色以外の属性でも識別できる", async ({ page }) => {
    const predictionPage = new PredictionPage(page);
    await predictionPage.goto();
    await predictionPage.openDetailsPanel();

    const facilitiesTab = page.getByRole("tab", { name: "商業施設" });
    const modelTab = page.getByRole("tab", { name: "モデル" });
    await expect(facilitiesTab).toHaveAttribute("aria-selected", "true");
    await expect(modelTab).toHaveAttribute("aria-selected", "false");
    await modelTab.click();
    await expect(modelTab).toHaveAttribute("aria-selected", "true");
  });
});
