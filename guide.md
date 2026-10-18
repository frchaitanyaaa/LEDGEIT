# Demo guide

Step-by-step walkthrough of the LEDGEIT demo at http://localhost:5173. Log in as `qe@ledgeit.dev` / `ledgeit123` unless a step says otherwise.

Before you start, in PowerShell from the project folder, set a shortcut for the Docker commands used in steps 7 and 8:

```
$C = "docker compose -f infra/docker-compose.yml"
```

## Step 1: click Live Feed in the left menu

This shows the first stage of the project: a simulated camera sends inspections, the AI judges each one, and the system seals them as they arrive.

Tell the judges: "every product gets inspected and the decision is recorded the moment it happens."

## Step 2: click Inspections in the left menu, then click any FAIL row

This opens that inspection's detail page. Point out these four things:

- The **image and heatmap** show what the AI saw and why it decided.
- The **sealed record** shows the record hash and the device signature.
- The **timeline** shows each event chained to the one before it.
- The **model name, version and weights hash** show which AI made the call.

Tell the judges: "everything about this decision is locked into one record the moment it happens."

## Step 3: on that inspection page, click the blue "Verify now" button (top right)

You should see 5 checks turn green and the result show VERIFIED:

1. **Evidence:** the stored image still matches its hash.
2. **Model:** the AI model matches the registry and was approved.
3. **Signatures:** the device signature is valid.
4. **Event chain:** no event was deleted or reordered.
5. **Blockchain:** the record's fingerprint is in a batch anchored on-chain.

If check 5 shows PENDING, the record is still waiting for its batch to be anchored. Pick an older inspection and try again.

Tell the judges: "anyone can re-check this record at any time, and it independently proves nothing has changed."

## Step 4: click Blockchain Explorer in the left menu

This shows the batches of records that were anchored on the blockchain. Point out these three things:

- Each **batch** has a Merkle root, which is one fingerprint that covers many records.
- The **transaction** (hash, block number and fee) is the proof it was written to the chain.
- **HIGH** risk records are anchored immediately, while LOW and MEDIUM ones are grouped to save cost.

Tell the judges: "the chain only allows adding records, never changing them, so this is the part nobody can rewrite."

The chain here is a local test chain, not the public Polygon testnet, so there is no Polygonscan link yet.

## Step 5: override a decision (as `qe`, still logged in)

1. Click **Inspections**, then open a **FAIL** inspection.
2. In the **Human decision** box, click **Override to PASS**.
3. Fill in the form: pick a reason (for example FALSE_POSITIVE), write a short comment, then sign it.
4. The status changes to **PENDING_APPROVAL**.

Your browser signs it with your own key, which is the "signing key ready" shown at bottom left. Point out that the record now shows who overrode it, why, and which evidence they reviewed.

Tell the judges: "when a human disagrees with the AI, that decision is signed and sealed the same way, so nobody can quietly change it."

Pick a record that isn't flagged DUPLICATE_EVIDENCE if you can, so the story stays clean.

## Step 6: approve the override (as `qm`)

1. Click **Sign out** (bottom left), then log in as `qm@ledgeit.dev` / `ledgeit123`.
2. Click **Override Center** and open the pending override.
3. Approve it and sign.
4. Open that inspection again and click **Verify now**. It should still show VERIFIED, now including the override and approval signatures.

Tell the judges: "an override needs two people, the engineer and the manager, and both signatures are sealed and checked."

## Step 7: attack the database, then re-verify

This is the key moment. Run this in PowerShell (use an inspection code from your Inspections list):

```
Invoke-Expression "$C exec api python /app/scripts/tamper-lab/tamper_lab.py edit-decision INS-20261018-A01-000002"
```

This flips a decision in the database, like a malicious insider would. Then open that inspection and click **Verify now**.

- Expected: **FAILED**, with the signature and event-chain checks red.
- Other attacks, each on a different inspection: swap `edit-decision` for `swap-image` (the evidence check fails) or `delete-event` (the event-chain check fails).

If the command can't find the script, copy it into the container first: `Invoke-Expression "$C cp scripts api:/app/scripts"`.

Tell the judges: "the record was edited behind the system's back, and verification catches it immediately."

## Step 8: the smart insider and a replay attack

**Smart insider.** Run, on another inspection:

```
Invoke-Expression "$C exec api python /app/scripts/tamper-lab/tamper_lab.py smart-insider INS-20261018-A01-000005"
```

The attacker rewrites the record and recomputes every hash and signature so the database looks consistent. Click **Verify now**: it still shows **FAILED**, and **only check 5 (blockchain)** is red.

**Replay.** Send an old image again as a new unit:

```
Invoke-Expression "$C --profile demo run --rm edge-simulator --replay 3"
```

Then open **Risk & Tampering** to see the **DUPLICATE_EVIDENCE** alert, and use **Acknowledge** or **Resolve** on it.

Tell the judges: "the database can be rewritten, but the blockchain can't, so even a perfect cover-up is caught."

## Step 9: generate a compliance report and scan the QR (as `qm`)

1. Click **Compliance Reports**, choose a report type, and click **Generate report**. It verifies the records first, so tampered ones show up as failed.
2. Click the download button on the new row to get the PDF.
3. Scan the QR code on the PDF with a phone, or open the public verify link. The page checks the record against the chain right in the browser, with no login.

Tell the judges: "an auditor or regulator can check any record independently, without trusting our system."

## Step 10: show the economics (as `qm`)

Click **Economics**. Point out:

- The **fee per anchor** transaction, taken from real transaction receipts.
- The **cost per inspection**.
- The **saving from batching**: many records share one transaction instead of one each.

Tell the judges: "the blockchain cost per inspection is tiny because routine records are batched, and only critical ones are anchored immediately."

## Notes

- The AI is a placeholder model, and the project is about the integrity layer that works around any AI. The YOLO model training is in progress.
- The chain is a local test chain. Deploying to the Polygon Amoy testnet is still pending.
