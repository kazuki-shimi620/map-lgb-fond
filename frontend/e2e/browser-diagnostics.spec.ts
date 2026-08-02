import { expect, test } from "@playwright/test";

test("ブラウザIssueとフォーム属性不足が発生しない", async ({ page, context }) => {
  const client = await context.newCDPSession(page);
  const issues: unknown[] = [];
  const consoleErrors: string[] = [];
  client.on("Audits.issueAdded", ({ issue }) => issues.push(issue));
  page.on("console", (message) => {
    if (message.type() === "error") {
      const location = message.location();
      consoleErrors.push(`${message.text()} ${location.url}`.trim());
    }
  });
  await client.send("Audits.enable");
  await page.goto("./");
  await expect(page.getByTestId("property-map")).toBeVisible();
  await page.waitForTimeout(3_000);
  const fieldsWithoutIdentifier = await page.locator("input:not([id]):not([name]), select:not([id]):not([name]), textarea:not([id]):not([name])").count();
  // GSI hazard tiles use 404 to represent areas without hazard data. The app
  // converts those responses into transparent tiles; Chrome still reports the
  // HTTP status in the console even though it is handled intentionally.
  const unexpectedConsoleErrors = consoleErrors.filter(
    (message) =>
      !message.includes("https://disaportaldata.gsi.go.jp/raster/") ||
      !message.startsWith("Failed to load resource: the server responded with a status of 404")
  );
  expect(fieldsWithoutIdentifier).toBe(0);
  expect(issues).toEqual([]);
  expect(unexpectedConsoleErrors).toEqual([]);
});
