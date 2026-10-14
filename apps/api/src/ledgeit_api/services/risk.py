"""Risk engine (CHAITANYA.md §5.6). Thresholds come from config/risk.yaml."""

from __future__ import annotations

from decimal import Decimal

from ..core.yamlconf import risk_config


def classify(result: dict, *, regulated: bool = False, replay_alert: bool = False,
             unapproved_model: bool = False) -> tuple[str, list[str]]:
    cfg = risk_config()["classification"]
    hi, med = cfg["high"], cfg["medium"]
    conf = Decimal(result["confidence"])
    high: list[str] = []
    if result["severity"] in hi["severities"]:
        high.append(f"severity {result['severity']}")
    if conf < Decimal(hi["confidence_below"]):
        high.append(f"confidence {result['confidence']} < {hi['confidence_below']}")
    if regulated and hi.get("regulated_product", True):
        high.append("regulated product")
    if replay_alert and hi.get("replay_alert", True):
        high.append("replay alert")
    if unapproved_model and hi.get("unapproved_model", True):
        high.append("model not approved")
    if high:
        return "HIGH", high
    medium: list[str] = []
    if result["severity"] in med["severities"]:
        medium.append(f"severity {result['severity']}")
    if conf < Decimal(med["confidence_below"]):
        medium.append(f"confidence {result['confidence']} < {med['confidence_below']}")
    if medium:
        return "MEDIUM", medium
    return "LOW", [f"{result['decision']} with confidence {result['confidence']}"]


def human_event_risk() -> str:
    return risk_config()["classification"].get("human_events", "HIGH")
