// `npm run dev`: start the whole stack in Docker, wait until it is ready, print the links.
import { spawnSync } from "node:child_process";

// Build 2 images at a time: parallel pip downloads fight for bandwidth and time out on slow links.
const env = { ...process.env, COMPOSE_PARALLEL_LIMIT: process.env.COMPOSE_PARALLEL_LIMIT ?? "2" };
const run = (args) => spawnSync("docker", ["compose", ...args], { stdio: "inherit", env });

if (spawnSync("docker", ["info"], { stdio: "ignore" }).status !== 0) {
  console.error("\nDocker is not running. Start Docker Desktop, wait until it says 'running', then retry.\n");
  process.exit(1);
}

console.log("Building and starting: postgres, blockchain, seed, api, anchor worker, AI, 2 cameras, web ...");
if (run(["up", "-d", "--build"]).status !== 0) process.exit(1);

const ready = async (url) => {
  try { return (await fetch(url)).ok; } catch { return false; }
};

process.stdout.write("Waiting for the app to be ready ");
for (let i = 0; i < 120; i++) {
  if ((await ready("http://localhost:5173/api/v1/health")) && (await ready("http://localhost:8001/health"))) {
    console.log(`
\n  LEDGEIT is running

  Website         http://localhost:5173
  API docs        http://localhost:8000/docs
  AI inspector    http://localhost:8001/docs
  Blockchain RPC  http://localhost:8545

  Login           qm@ledgeit.dev / ledgeit123   (also qe@, auditor@, operator@, admin@)

  Logs: npm run logs    Stop: npm run stop    Reset all data: npm run reset
`);
    process.exit(0);
  }
  process.stdout.write(".");
  await new Promise((r) => setTimeout(r, 2000));
}
console.error("\nTimed out. Check logs with: npm run logs");
process.exit(1);
