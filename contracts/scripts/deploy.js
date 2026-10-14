// Deploys LedgeitAnchor and writes deployments/<network>.json (address, chainId, block, abi).
const fs = require("fs");
const path = require("path");
const hre = require("hardhat");

async function main() {
  const [deployer] = await hre.ethers.getSigners();
  const net = await hre.ethers.provider.getNetwork();
  console.log(`Deploying LedgeitAnchor to ${hre.network.name} (chainId ${net.chainId}) from ${deployer.address}`);
  const c = await hre.ethers.deployContract("LedgeitAnchor");
  const receipt = await c.deploymentTransaction().wait();
  const address = await c.getAddress();
  const artifact = await hre.artifacts.readArtifact("LedgeitAnchor");
  const out = {
    network: hre.network.name,
    chainId: Number(net.chainId),
    address,
    deployer: deployer.address,
    txHash: receipt.hash,
    blockNumber: receipt.blockNumber,
    deployedAt: new Date().toISOString(),
    abi: artifact.abi,
  };
  const dir = path.join(__dirname, "..", "deployments");
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, `${hre.network.name}.json`), JSON.stringify(out, null, 2) + "\n");
  console.log(`LedgeitAnchor deployed at ${address}`);
}

main().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
