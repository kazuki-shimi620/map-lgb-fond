import { expect, type Locator, type Page } from "@playwright/test";

export class PredictionPage {
  readonly page: Page;
  readonly map: Locator;
  readonly locationTooltip: Locator;
  readonly predictionResult: Locator;
  readonly priceHistory: Locator;

  constructor(page: Page) {
    this.page = page;
    this.map = page.getByRole("region", { name: "地図" });
    this.locationTooltip = page.locator(".map-location-tooltip");
    this.predictionResult = page.getByTestId("prediction-result");
    this.priceHistory = page.getByTestId("price-history-chart");
  }

  async goto() {
    await this.page.goto("./");
  }

  async expectLoaded() {
    await expect(this.map).toBeVisible();
    await expect(this.page.getByTestId("prediction-sheet")).toBeVisible();
  }

  async openDetailsPanel() {
    const sheet = this.page.getByTestId("prediction-sheet");
    if ((await sheet.getAttribute("class"))?.includes("sheet-collapsed")) {
      await this.page.getByTestId("sheet-handle").dispatchEvent("click");
    }
    await expect(this.page.getByTestId("prediction-form")).toBeVisible();
    await expect(this.page.getByTestId("prediction-result")).toBeVisible();
    await expect(this.page.getByTestId("price-history-chart")).toBeVisible();
  }

  async expectInitialFormValues() {
    await expect(this.locationTooltip).toContainText("東京都");
    await expect(this.locationTooltip).toContainText("千代田区");
    await expect(this.locationTooltip).toContainText("東京");
    await expect(this.locationTooltip).toContainText("8分");
    await expect(this.page.getByLabel("面積")).toHaveValue("55");
    await expect(this.page.getByLabel("築年数")).toHaveValue("15");
    await expect(this.selectTrigger("間取り")).toContainText("2LDK");
  }

  async waitForPredictionResult() {
    await expect(this.predictionResult.getByText("予測価格", { exact: true })).toBeVisible({
      timeout: 30_000
    });
    await expect(this.predictionResult.getByText("平米単価", { exact: true })).toBeVisible();
    await expect(this.predictionResult.getByText("参考価格帯", { exact: true })).toBeVisible();
  }

  async fillArea(value: number) {
    await this.page.getByLabel("面積").fill(String(value));
  }

  async fillAge(value: number) {
    await this.page.getByLabel("築年数").fill(String(value));
  }

  async fillStationDistance(value: number) {
    await this.page.getByLabel("駅徒歩").fill(String(value));
  }

  async fillMunicipality(value: string) {
    await this.page.getByLabel("市区町村").fill(value);
  }

  async fillStation(value: string) {
    await this.page.getByLabel("最寄駅").fill(value);
  }

  async selectPrefecture(value: string) {
    await this.selectOption("都道府県", value);
  }

  async selectRoomLayout(value: string) {
    await this.selectOption("間取り", value);
  }

  async selectBuildingType(value: string) {
    await this.selectOption("建物構造", value);
  }

  async searchMap(query: string) {
    await this.page.getByLabel("地図検索").fill(query);
    await this.page.getByRole("button", { name: "検索" }).click();
  }

  async clickMapCenter() {
    const box = await this.map.boundingBox();
    if (!box) {
      throw new Error("Map is not visible");
    }
    await this.page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
  }

  async loadArchiveHistory() {
    await this.page.getByRole("button", { name: /以前の実績を表示/ }).click();
  }

  async closeArchiveHistory() {
    await this.page.getByRole("button", { name: /年以降の表示に戻す/ }).click();
  }

  async toggleModelDetails() {
    await this.page.getByRole("button", { name: /条件・モデル詳細を表示|詳細を閉じる/ }).click();
  }

  async getPredictedPriceText() {
    return this.predictionResult.locator(".price-main").first().innerText();
  }

  selectTrigger(label: string) {
    return this.page
      .locator(".custom-select-field")
      .filter({ hasText: label })
      .locator(".custom-select-trigger");
  }

  private async selectOption(label: string, value: string) {
    await this.selectTrigger(label).click();
    await this.page.getByRole("option", { name: value }).click();
  }
}
