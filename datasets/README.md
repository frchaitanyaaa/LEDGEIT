# Datasets (git-ignored)

## NEU-DET (ADR-006)
NEU surface defect database — 1,800 grayscale 200×200 images of hot-rolled steel, 6 classes × 300, with VOC XML boxes.

1. Download from Kaggle (`kaustubhdikshit/neu-surface-defect-database`) or the NEU site and unzip to `datasets/NEU-DET/`.
2. `python services/ai-inspector/training/prepare_neu_det.py --src datasets/NEU-DET --out datasets/neu-det-yolo`
3. Train: see `services/ai-inspector/training/train.py`.
4. Stream real images: `python -m simulator --source dir:datasets/NEU-DET/IMAGES`

Never commit images or weights.
