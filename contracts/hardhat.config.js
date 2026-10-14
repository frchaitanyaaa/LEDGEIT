require("@nomicfoundation/hardhat-toolbox");
const fs = require("fs");
const path = require("path");
const { subtask } = require("hardhat/config");
const { TASK_COMPILE_SOLIDITY_GET_SOLC_BUILD } = require("hardhat/builtin-tasks/task-names");

// Load ../.env if present (no dotenv dependency).
const envFile = path.join(__dirname, "..", ".env");
if (fs.existsSync(envFile)) {
  for (const line of fs.readFileSync(envFile, "utf8").split("\n")) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
    if (m && process.env[m[1]] === undefined) process.env[m[1]] = m[2];
  }
}

const SOLC_VERSION = "0.8.24";

// Use the pinned solcjs from npm instead of downloading a native compiler. This keeps builds
// reproducible and works in networks that block binaries.soliditylang.org.
subtask(TASK_COMPILE_SOLIDITY_GET_SOLC_BUILD, async (args, hre, runSuper) => {
  if (args.solcVersion === SOLC_VERSION) {
    const solc = require("solc");
    return {
      compilerPath: require.resolve("solc/soljson.js"),
      isSolcJs: true,
      version: args.solcVersion,
      longVersion: solc.version(),
    };
  }
  return runSuper();
});

const amoyKey = process.env.AMOY_PRIVATE_KEY || process.env.ANCHOR_PRIVATE_KEY;

/** @type import('hardhat/config').HardhatUserConfig */
module.exports = {
  solidity: {
    version: SOLC_VERSION,
    settings: { optimizer: { enabled: true, runs: 200 }, evmVersion: "cancun" },
  },
  paths: { sources: "./src", tests: "./test", cache: "./cache", artifacts: "./artifacts" },
  networks: {
    hardhat: { chainId: 31337 },
    localhost: { url: process.env.RPC_URL_LOCAL || "http://127.0.0.1:8545", chainId: 31337 },
    amoy: {
      url: process.env.RPC_URL_AMOY || "https://rpc-amoy.polygon.technology",
      chainId: 80002,
      accounts: amoyKey && process.env.CHAIN === "amoy" ? [amoyKey] : [],
    },
  },
  gasReporter: { enabled: process.env.REPORT_GAS === "1" },
};
