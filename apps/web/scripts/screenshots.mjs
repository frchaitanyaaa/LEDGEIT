// Capture one PNG per dashboard page into docs/screenshots/ for the project report and PPT.
//
//   npx playwright install chromium     # once
//   npm run screenshots                 # needs the stack running and seeded (see README)
//
// Env: BASE_URL (default http://localhost:5173), LEDGEIT_PASSWORD (default: the demo password), OUT_DIR,
//      BROWSER_CHANNEL (chrome | msedge: skip the Playwright download and use the installed browser).

import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const BASE = (process.env.BASE_URL ?? "http://localhost:5173").replace(/\/$/, "");
const PASSWORD = process.env.LEDGEIT_PASSWORD ?? "ledgeit123";
const OUT = process.env.OUT_DIR ?? fileURLToPath(new URL("../../../docs/screenshots/", import.meta.url));
const VIEWPORT = { width: 1440, height: 900 };

// [file name, path, user]. Each role sees the pages it would use in the demo.
const PAGES = [
  ["executive", "/", "qm"],
  ["live-feed", "/feed", "qe"],
  ["inspections", "/inspections", "qe"],
  ["overrides", "/overrides", "qm"],
  ["explorer", "/explorer", "auditor"],
  ["verification", "/verification", "auditor"],
  ["risk", "/risk", "qm"],
  ["models", "/models", "qm"],
  ["reports", "/reports", "auditor"],
  ["economics", "/economics", "qm"],
  ["integrations", "/integrations", "admin"],
];

async function settle(page) {
  await page.waitForLoadState("networkidle").catch(() => undefined);
  // Wait for spinners to disappear and charts to finish their entry animation.
  await page.waitForFunction(() => !document.querySelector(".animate-spin"), null, { timeout: 15000 }).catch(() => undefined);
  await page.waitForTimeout(800);
}

async function shot(page, name) {
  const file = `${OUT}${name}.png`;
  await page.screenshot({ path: file, fullPage: true });
  console.log(`  saved ${name}.png`);
}

async function login(browser, user) {
  const ctx = await browser.newContext({ viewport: VIEWPORT, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  await page.goto(`${BASE}/login`);
  await page.fill("#email", `${user}@ledgeit.dev`);
  await page.fill("#password", PASSWORD);
  await page.click("button[type=submit], form button.btn-primary");
  await page.waitForURL((u) => !u.pathname.startsWith("/login"), { timeout: 20000 });
  return { ctx, page };
}

async function main() {
  await mkdir(OUT, { recursive: true });
  // BROWSER_CHANNEL=chrome|msedge uses an installed browser instead of Playwright's bundled Chromium.
  const browser = await chromium.launch(process.env.BROWSER_CHANNEL ? { channel: process.env.BROWSER_CHANNEL } : {});
  const sessions = new Map();
  const session = async (user) => {
    if (!sessions.has(user)) sessions.set(user, await login(browser, user));
    return sessions.get(user).page;
  };

  // Logged-out login page.
  {
    const ctx = await browser.newContext({ viewport: VIEWPORT });
    const page = await ctx.newPage();
    await page.goto(`${BASE}/login`);
    await settle(page);
    await shot(page, "login");
    await ctx.close();
  }

  for (const [name, path, user] of PAGES) {
    const page = await session(user);
    await page.goto(`${BASE}${path}`);
    await settle(page);
    await shot(page, name);
  }

  // Inspection detail: prefer a record that has been verified, so all five checks show.
  const page = await session("qe");
  await page.goto(`${BASE}/inspections`);
  await settle(page);
  const verifiedRow = page.locator("tbody tr", { hasText: "VERIFIED" }).first();
  const anyRow = page.locator("tbody tr").first();
  const row = (await verifiedRow.count()) ? verifiedRow : anyRow;
  if (await row.count()) {
    await row.locator("a").first().click();
    await settle(page);
    await shot(page, "inspection-verified");
  } else {
    console.warn("  no inspections yet: skipped inspection-verified.png");
  }

  // Public verify page for the newest report, opened logged out as a regulator would via the QR code.
  const auditor = await session("auditor");
  const reports = await auditor.evaluate(async () => {
    const t = JSON.parse(localStorage.getItem("ledgeit.tokens") ?? "null");
    const r = await fetch("/api/v1/reports", { headers: t ? { Authorization: `Bearer ${t.access_token}` } : {} });
    return r.ok ? r.json() : [];
  });
  if (reports.length) {
    const ctx = await browser.newContext({ viewport: VIEWPORT });
    const pub = await ctx.newPage();
    await pub.goto(`${BASE}/verify/${reports[0].verification_code}`);
    await settle(pub);
    await shot(pub, "public-verify");
    await ctx.close();
  } else {
    console.warn("  no reports yet: skipped public-verify.png (generate one on /reports or run the demo)");
  }

  for (const { ctx } of sessions.values()) await ctx.close();
  await browser.close();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
