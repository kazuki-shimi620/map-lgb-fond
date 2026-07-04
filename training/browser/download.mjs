import { existsSync } from "node:fs";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { chromium } from "playwright-core";

const args = parseArgs(process.argv.slice(2));
const required = ["prefecture-code", "from-season", "to-season", "output"];
for (const key of required) {
  if (!args[key]) {
    throw new Error(`--${key} is required`);
  }
}

const chromePath = args["chrome-path"] || findChrome();
const timeout = Number(args["timeout-ms"] || 600000);
const outputPath = path.resolve(args.output);
await mkdir(path.dirname(outputPath), { recursive: true });

const browser = await chromium.launch({ executablePath: chromePath, headless: true });
try {
  const context = await browser.newContext({
    acceptDownloads: true,
    locale: "ja-JP",
    viewport: { width: 1280, height: 900 }
  });
  const page = await context.newPage();
  page.setDefaultTimeout(60000);

  await page.goto("https://www.reinfolib.mlit.go.jp/realEstatePrices/", {
    waitUntil: "networkidle",
    timeout: 120000
  });
  await page.waitForSelector("#cmbPrefectures");

  await page.locator("#cmbPrefectures").selectOption(args["prefecture-code"]);
  await page.locator("#cmbKind").selectOption("used");
  await page.locator("#cmbSeasonFrom").selectOption(args["from-season"]);
  await page.locator("#cmbSeasonTo").selectOption(args["to-season"]);
  await page.locator("#chkTransactionPrice").check();
  await page.locator("#chkClosedPrice").check();
  await page.waitForTimeout(500);

  const downloadButton = page.locator("#btnDownloadList").first();
  if (await downloadButton.isDisabled()) {
    await writeFile(`${outputPath}.no-data`, "", "utf8");
    console.log(`no data for ${args["prefecture-code"]} ${args["from-season"]}-${args["to-season"]}`);
  } else {
    const downloadPromise = page.waitForEvent("download", { timeout });
    await downloadButton.click();
    const download = await downloadPromise;
    const failure = await download.failure();
    if (failure) {
      throw new Error(`browser download failed: ${failure}`);
    }
    await download.saveAs(outputPath);
    console.log(`downloaded ${download.suggestedFilename()} -> ${outputPath}`);
  }
} finally {
  await browser.close();
}

function parseArgs(values) {
  const parsed = {};
  for (let index = 0; index < values.length; index += 2) {
    const key = values[index];
    if (!key?.startsWith("--") || values[index + 1] === undefined) {
      throw new Error(`invalid argument: ${key ?? ""}`);
    }
    parsed[key.slice(2)] = values[index + 1];
  }
  return parsed;
}

function findChrome() {
  const candidates = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser"
  ];
  const found = candidates.find((candidate) => existsSync(candidate));
  if (!found) {
    throw new Error("Chrome or Edge was not found. Set --chrome-path explicitly.");
  }
  return found;
}
