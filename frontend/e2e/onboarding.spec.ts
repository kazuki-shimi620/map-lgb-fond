import { expect, test } from "@playwright/test";
import { PredictionPage } from "./pages/prediction-page";

test("初回だけ3段階の案内を表示し画面左上から再表示できる", async ({ page }) => {
  const predictionPage = new PredictionPage(page);
  await predictionPage.goto();

  const guide = page.getByLabel("はじめての使い方");
  await expect(guide).toBeVisible();
  await expect(page.getByRole("button", { name: "使い方" })).toHaveCount(0);
  await expect(guide).toContainText("地図で場所を選ぶ");
  await expect(guide).toContainText("面積・築年数などを入力");
  await expect(guide).toContainText("予測価格と理由を確認");

  await page.getByRole("button", { name: "わかりました" }).click();
  await expect(guide).toHaveCount(0);
  await page.reload();
  await expect(guide).toHaveCount(0);

  await page.getByRole("button", { name: "使い方" }).click();
  await expect(guide).toBeVisible();
  await expect(page.getByRole("button", { name: "使い方" })).toHaveCount(0);
});
