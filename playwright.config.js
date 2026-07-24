const { defineConfig } = require("@playwright/test");

const browserChannel = process.env.PLAYWRIGHT_CHANNEL;

module.exports = defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI
    ? [["line"], ["html", { open: "never" }]]
    : [["line"]],
  use: {
    ...(browserChannel ? { channel: browserChannel } : {}),
    headless: true,
    viewport: { width: 1280, height: 900 },
    trace: "retain-on-failure",
  },
});
