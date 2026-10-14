import { hashJson, verifyHexDigest } from "@ledgeit/proof-core";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { VerifyChecklist } from "../src/components/VerifyChecklist";
import { loadKey, saveKey, sign } from "../src/lib/keys";
import { generateKeypair } from "@ledgeit/proof-core";

describe("browser keys", () => {
  it("persists keys in IndexedDB and signs JCS digests the server can verify", async () => {
    const kp = generateKeypair();
    await saveKey("QE-1", kp);
    expect(await loadKey("QE-1")).toEqual(kp);
    const s = sign({ b: 1, a: "x" }, kp);
    expect(s.digest).toBe(hashJson({ a: "x", b: 1 }));
    expect(verifyHexDigest(s.digest, s.signature, kp.publicKeyB64)).toBe(true);
  });
});

describe("VerifyChecklist", () => {
  it("renders the five checks in order with problems", () => {
    const mk = (status: string, problems: string[] = []) => ({ status, title: status, problems, facts: {} }) as any;
    render(<VerifyChecklist checks={{ anchor: mk("FAIL", ["root not on-chain"]), evidence: mk("PASS"), model: mk("PASS"),
                                      signature: mk("PASS"), chain: mk("PENDING") }} />);
    const items = screen.getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("1.");
    expect(screen.getByText("root not on-chain")).toBeInTheDocument();
  });
});
