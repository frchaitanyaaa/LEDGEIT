const { expect } = require("chai");
const { ethers } = require("hardhat");
const { anyValue } = require("@nomicfoundation/hardhat-chai-matchers/withArgs");

const ROOT = "0x" + "ab".repeat(32);
const ROOT2 = "0x" + "cd".repeat(32);

describe("LedgeitAnchor", function () {
  async function deploy() {
    const [owner, worker, stranger] = await ethers.getSigners();
    const c = await ethers.deployContract("LedgeitAnchor");
    return { c, owner, worker, stranger };
  }

  it("owner is an anchorer and can anchor a root", async function () {
    const { c, owner } = await deploy();
    expect(await c.owner()).to.equal(owner.address);
    await expect(c.anchor(ROOT, 7, 10, 1))
      .to.emit(c, "RootAnchored")
      .withArgs(ROOT, 7, 10, 1, anyValue);
    expect(await c.isAnchored(ROOT)).to.equal(true);
    const a = await c.anchors(ROOT);
    expect(a.leafCount).to.equal(10n);
    expect(a.riskLevel).to.equal(1n);
    expect(a.timestamp).to.be.greaterThan(0n);
    expect(await c.anchorCount()).to.equal(1n);
  });

  it("reverts on duplicate root (no overwrite possible)", async function () {
    const { c } = await deploy();
    await c.anchor(ROOT, 1, 1, 2);
    const before = await c.anchors(ROOT);
    await expect(c.anchor(ROOT, 2, 99, 0)).to.be.revertedWithCustomError(c, "AlreadyAnchored").withArgs(ROOT);
    const after = await c.anchors(ROOT);
    expect(after.timestamp).to.equal(before.timestamp);
    expect(after.leafCount).to.equal(1n);
  });

  it("reverts for non-anchorers", async function () {
    const { c, stranger } = await deploy();
    await expect(c.connect(stranger).anchor(ROOT, 1, 1, 0)).to.be.revertedWithCustomError(c, "NotAnchorer");
  });

  it("only owner can add anchorers, and added anchorer can anchor", async function () {
    const { c, worker, stranger } = await deploy();
    await expect(c.connect(stranger).setAnchorer(worker.address, true)).to.be.revertedWithCustomError(c, "NotOwner");
    await expect(c.setAnchorer(worker.address, true)).to.emit(c, "AnchorerSet").withArgs(worker.address, true);
    await c.connect(worker).anchor(ROOT2, 1, 3, 0);
    expect(await c.isAnchored(ROOT2)).to.equal(true);
    await c.setAnchorer(worker.address, false);
    await expect(c.connect(worker).anchor(ROOT, 2, 3, 0)).to.be.revertedWithCustomError(c, "NotAnchorer");
  });

  it("rejects empty batches, zero root and bad risk level", async function () {
    const { c } = await deploy();
    await expect(c.anchor(ROOT, 1, 0, 0)).to.be.revertedWithCustomError(c, "EmptyBatch");
    await expect(c.anchor(ethers.ZeroHash, 1, 1, 0)).to.be.revertedWithCustomError(c, "ZeroRoot");
    await expect(c.anchor(ROOT, 1, 1, 3)).to.be.revertedWithCustomError(c, "BadRiskLevel").withArgs(3);
  });

  it("exposes no mutating function besides anchor/setAnchorer", async function () {
    const { c } = await deploy();
    const mutating = c.interface.fragments
      .filter((f) => f.type === "function" && !["view", "pure"].includes(f.stateMutability))
      .map((f) => f.name)
      .sort();
    expect(mutating).to.deep.equal(["anchor", "setAnchorer"]);
  });

  it("gas snapshot for one anchor call (feeds Economics page)", async function () {
    const { c } = await deploy();
    const tx = await c.anchor(ROOT, 1, 100, 0);
    const r = await tx.wait();
    console.log(`      gas used by anchor(): ${r.gasUsed}`);
    expect(r.gasUsed).to.be.lessThan(120000n);
  });
});
