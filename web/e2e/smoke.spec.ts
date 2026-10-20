import { expect, type Page, test } from "@playwright/test";

async function openApp(page: Page): Promise<string[]> {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(String(error)));
  await page.goto("/");
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await expect(page.locator(".kpi-grid")).toBeVisible({ timeout: 30_000 });
  return errors;
}

test("every view renders without page errors", async ({ page }) => {
  const errors = await openApp(page);
  const tabs = page.locator(".view-tab");
  await expect(tabs).toHaveCount(5);

  await tabs.nth(1).click(); // 1D DBF
  await expect(page.locator(".js-plotly-plot")).toHaveCount(2, { timeout: 30_000 });
  await tabs.nth(2).click(); // 2D DBF
  await expect(page.locator(".js-plotly-plot .heatmaplayer, .js-plotly-plot .hm").first()).toBeAttached({ timeout: 30_000 });
  await tabs.nth(3).click(); // angle performance: error + margin per axis
  await expect(page.locator(".js-plotly-plot")).toHaveCount(4, { timeout: 30_000 });
  await tabs.nth(4).click(); // band sweep and comparison
  await expect(page.locator(".metric-table").first()).toBeVisible({ timeout: 30_000 });
  await tabs.nth(0).click();
  await expect(page.locator("g.element")).toHaveCount(16);

  expect(errors).toEqual([]);
});

test("out-of-range coordinates and ambiguous numbers are rejected", async ({ page }) => {
  await openApp(page);
  await page.locator("g.element").filter({ hasText: "Tx1" }).first().click();
  const x = page.locator(".inspector input").first();
  const original = await x.inputValue();
  for (const text of ["-1e6", "501"]) {
    await x.fill(text);
    await expect(x).toHaveAttribute("aria-invalid", "true");
    await expect(x).toHaveAttribute("title", /±500 λ/);
    await x.press("Enter");
    await expect(x).toHaveValue(original);
  }
  await page.waitForTimeout(800);
  await expect(page.locator(".overview .callout.danger")).toHaveCount(0);

  const frequency = page.locator(".param-input").first();
  for (const text of ["1,000", "0x4D", "Infinity"]) {
    await frequency.fill(text);
    await expect(frequency).toHaveAttribute("aria-invalid", "true");
    await expect(frequency).toHaveAttribute("title", /十进制/);
    await frequency.press("Enter");
    await expect(frequency).toHaveValue("77");
  }
});

test("Escape cancels a numeric edit and Enter commits it", async ({ page }) => {
  await openApp(page);
  const status = page.locator(".statusbar");
  const frequency = page.locator(".param-input").first();
  await frequency.fill("60");
  await frequency.press("Escape");
  await expect(frequency).toHaveValue("77");
  await expect(status).toContainText("@ 77 GHz");

  await page.locator("g.element").filter({ hasText: "Tx1" }).first().click();
  const x = page.locator(".inspector input").first();
  const original = await x.inputValue();
  await x.fill("7");
  await x.press("Escape");
  await expect(x).toHaveValue(original);
  // Nothing was committed, so there is nothing to undo.
  await expect(page.getByRole("button", { name: "撤销" })).toBeDisabled();

  await frequency.fill("60");
  await frequency.press("Enter");
  await expect(status).toContainText("@ 60 GHz");
});

test("a share link opens the same configuration in another browser", async ({ page, browser }) => {
  await openApp(page);
  await page.locator(".param-button").first().click();
  await page.getByRole("menuitemradio", { name: /60G/ }).click();
  await page.getByRole("button", { name: "自动排阵" }).click();
  const counts = page.locator(".popover-form input");
  await counts.nth(0).fill("3");
  await counts.nth(1).fill("4");
  await page.locator(".popover-form").getByRole("button").last().click();
  await expect(page.locator("g.element")).toHaveCount(7);

  await page.getByRole("button", { name: "分享" }).click();
  const link = page.locator(".share-link input");
  await expect(link).toHaveValue(/\/s\/[0-9A-Za-z]{12}$/, { timeout: 15_000 });
  const url = await link.inputValue();

  const other = await browser.newContext({ locale: "zh-CN", viewport: { width: 1440, height: 900 } });
  const recipient = await other.newPage();
  await recipient.goto(url);
  await expect(recipient.locator(".kpi-grid")).toBeVisible({ timeout: 30_000 });
  await expect(recipient.locator("g.element")).toHaveCount(7);
  await expect(recipient.locator(".param-button").first()).toContainText("60G");
  expect(new URL(recipient.url()).pathname).toBe("/");
  await other.close();
});

test("concurrent saves of one library project ask instead of overwriting", async ({ page: alice, browser }) => {
  await openApp(alice);
  const name = `并发保存 ${Date.now()}`;
  await alice.locator(".project-name-input").fill(name);
  await alice.getByRole("button", { name: "保存", exact: true }).click();
  await expect(alice.locator(".save-state")).toContainText("已保存");

  // Bob opens the same library project in his own browser.
  const context = await browser.newContext({ locale: "zh-CN", viewport: { width: 1440, height: 900 } });
  const bob = await context.newPage();
  await openApp(bob);
  await bob.getByRole("button", { name: /项目库/ }).click();
  await bob.locator(".project-row").filter({ hasText: name }).getByRole("button", { name: "打开" }).click();
  await expect(bob.locator(".project-name-input")).toHaveValue(name);

  // Alice saves first; Bob's later save must not silently discard it.
  const aliceFrequency = alice.locator(".param-input").first();
  await aliceFrequency.fill("60");
  await aliceFrequency.press("Enter");
  await alice.getByRole("button", { name: "保存", exact: true }).click();
  await expect(alice.locator(".save-state")).toContainText("已保存");

  const bobMargin = bob.locator(".param-input").nth(1);
  await bobMargin.fill("3");
  await bobMargin.press("Enter");
  await bob.getByRole("button", { name: "保存", exact: true }).click();
  const dialog = bob.getByRole("dialog");
  await expect(dialog).toContainText("项目已被他人修改");
  await dialog.getByRole("button", { name: "另存为新项目" }).click();
  await expect(bob.locator(".save-state")).toContainText("已保存");
  await expect(bob.locator(".project-name-input")).toHaveValue(`${name}（副本）`);

  // Alice's version is intact and Bob's edit lives in its own project.
  const library = await (await alice.request.get("/api/projects")).json();
  const mine = library.filter((item: { name: string }) => item.name.startsWith(name));
  expect(mine).toHaveLength(2);
  const original = mine.find((item: { name: string }) => item.name === name);
  expect(original.frequency_ghz).toBe(60);
  await context.close();
});
