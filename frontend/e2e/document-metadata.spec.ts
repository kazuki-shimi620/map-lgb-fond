import { expect, test } from "@playwright/test";

test("タブ・共有・ホーム画面向けメタデータを公開する", async ({ page }) => {
  await page.goto("./");

  await expect(page).toHaveTitle("中古マンション価格予測マップ");
  await expect(page.locator('meta[name="description"]')).toHaveAttribute("content", /中古マンション/);
  await expect(page.locator('meta[name="theme-color"]')).toHaveAttribute("content", "#d9ecff");
  await expect(page.locator('meta[property="og:title"]')).toHaveAttribute(
    "content",
    "中古マンション価格予測マップ"
  );
  await expect(page.locator('link[rel="icon"]')).toHaveAttribute("href", "./app-icon.svg");
  await expect(page.locator('link[rel="apple-touch-icon"]')).toHaveAttribute(
    "href",
    "./apple-touch-icon.png"
  );
  await expect(page.locator('link[rel="manifest"]')).toHaveAttribute("href", "./site.webmanifest");

  const response = await page.request.get("./site.webmanifest");
  expect(response.ok()).toBe(true);
  const manifest = await response.json();
  expect(manifest.name).toBe("中古マンション価格予測マップ");
  expect(manifest.icons).toEqual(
    expect.arrayContaining([
      expect.objectContaining({ src: "./app-icon.svg", type: "image/svg+xml" }),
      expect.objectContaining({ src: "./app-icon-192.png", sizes: "192x192" }),
      expect.objectContaining({ src: "./app-icon-512.png", sizes: "512x512" })
    ])
  );
});
