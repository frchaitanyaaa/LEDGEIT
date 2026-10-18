# Model card — LEDGEIT defect inspector

| | |
|---|---|
| Task | Surface-defect detection on hot-rolled steel (6 classes) → PASS/FAIL, class, severity, confidence, boxes, heatmap |
| Classes | crazing, inclusion, patches, pitted_surface, rolled-in_scale, scratches |
| Versions | `ledgeit-defect-stub@1.0.0`, `@1.1.0` (classical CV baseline); `ledgeit-defect-yolo@1.0.0` (YOLOv8n), `@1.1.0` (YOLOv8s) |
| Identity | Every version is identified by the SHA-256 of its weights file; that hash is sealed into every inspection record and checked against the Model Registry during verification |

## Stub baseline (always available)
Background subtraction (Gaussian σ=9) → robust z-score of the residual → morphology → connected components.
Class is assigned per image from component shape (PCA elongation, fill ratio, count, polarity).
Measured on 300 synthetic frames (`simulator.synth`, seed 7): **0 false FAILs on 196 good surfaces, 4/104 missed defects (v1.0.0), 0/104 (v1.1.0)**; class accuracy ≈ 80%.
It is a baseline so the integrity pipeline can be demoed without GPU training — not a production detector.

## YOLOv8 (trained on NEU-DET)
1,800 images, 200×200 grayscale, 300 per class, 80/20 split (`training/prepare_neu_det.py`, seed 42).
Train on Colab with `training/colab_train.ipynb` (writes metrics + dates into `models/manifest.json` automatically), or locally with `training/train.py`.

| Version | Base | mAP@50 | Precision | Recall |
|---|---|---|---|---|
| 1.0.0 | yolov8n | _fill after training_ | | |
| 1.1.0 | yolov8s | _fill after training_ | | |

## Severity mapping (`app/severity.py`)
Base: crazing/patches/rolled-in_scale = MINOR; pitted_surface/inclusion/scratches = MAJOR.
+1 level if defects cover ≥12% of the surface; +1 more at ≥30% (or structural class ≥8% with conf ≥0.9). Capped at CRITICAL.

## Explanation
YOLO: EigenCAM on the penultimate layer (first principal component of activations). Stub: smoothed residual saliency.
The heatmap PNG is hashed into the record (`explanation.heatmap_sha256`).

## Limitations
- NEU-DET contains only defective images; PASS behaviour for YOLO must be validated on defect-free crops or another dataset.
- Synthetic frames are not real steel; stub metrics do not transfer.
- Confidence is not calibrated. Drift monitoring in the MVP = override rate + confidence trend per model version.

## Replay-detection tuning (`training/tune_phash.py`, run on the real 1,800 NEU-DET images)
Exhaustive all-pairs pHash: the closest *distinct* pair is at Hamming distance 8 (only one byte-identical duplicate pair exists in the dataset, `patches_101`/`patches_105`), so `replay.phash_max_distance: 6` gives **0 false alarms** with margin. Tampered copies caught at 6: JPEG q75/q40, brightness, contrast and noise (about 83% overall); the main miss is a 5% crop-and-resize (mean distance 11), which would need threshold >= 12 and starts colliding with genuine surfaces at 8+. Exact SHA-256 replay is always caught.

## Stub on REAL NEU-DET images (`training/eval_backend.py`, 600 images, 100 per class)
The synthetic-frame figures above do **not** transfer. On real steel: detection recall 79.7%, class accuracy 15.8%, box hit-rate (IoU>=0.5) 18.5%; per-class recall ranges from 60% (patches) to 100% (scratches). Latency p50 16 ms / p95 32 ms (about 53 img/s, CPU). Conclusion: the stub is an integrity-pipeline placeholder only; real detection quality must come from the trained YOLO models. Re-run the same script with `--kind yolo --version 1.0.0` after training and paste the table here.
