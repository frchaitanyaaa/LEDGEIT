# edge-simulator

Plays the role of an AI camera on the line: grabs a frame, calls the AI inspector, builds a
`ledgeit.inspection.v1` record, **signs it with the device's Ed25519 key**, and posts it to the API.

```bash
pip install -e .                       # or: pip install -r requirements.txt
python -m simulator --count 50 --rate 2
python -m simulator --device CAM-B-01                 # regulated product line (HIGH risk)
python -m simulator --model-version 1.1.0             # unapproved model -> MODEL_MISMATCH alert
python -m simulator --replay 5                        # exact replay attack -> DUPLICATE_EVIDENCE
python -m simulator --near-replay 5                   # brightened copy -> POSSIBLE_REPLAY
python -m simulator --source dir:datasets/NEU-DET/IMAGES
```

- Keys: `keys/<DEVICE>.json` (git-ignored) are created by `make seed`; the API only stores public keys.
- Frames: `simulator/synth.py` generates deterministic synthetic steel surfaces with NEU-DET-style
  defects so the demo runs without the dataset. Frame *N* is always the same image, which makes `--replay N` reproducible.
- The device keeps a per-device record chain (`prev_record_hash`) and resyncs via `GET /devices/{code}/head`.
