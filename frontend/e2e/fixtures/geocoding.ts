import type { Page } from "@playwright/test";
import geocoding from "./geocoding.json" with { type: "json" };

export async function mockSuccessfulGeocoding(page: Page) {
  await page.route("https://nominatim.openstreetmap.org/reverse**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(geocoding.reverseTokyo)
    });
  });

  await page.route("https://nominatim.openstreetmap.org/search**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(geocoding.searchTokyoStation)
    });
  });
}

export async function mockUnsupportedReverseGeocoding(page: Page) {
  await page.route("https://nominatim.openstreetmap.org/reverse**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(geocoding.reverseUnsupported)
    });
  });
}

export async function mockFailedReverseGeocoding(page: Page) {
  await page.route("https://nominatim.openstreetmap.org/reverse**", async (route) => {
    await route.fulfill({
      status: 500,
      contentType: "application/json",
      body: JSON.stringify({ error: "reverse geocoding failed" })
    });
  });
}

export async function mockEmptySearch(page: Page) {
  await page.route("https://nominatim.openstreetmap.org/search**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(geocoding.searchEmpty)
    });
  });
}
