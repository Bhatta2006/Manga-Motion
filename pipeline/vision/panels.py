"""Normalize Magi output and attach measurable geometry/review information."""

from __future__ import annotations

import math

from pipeline.vision.order import reading_order
from pipeline.adapters.magi import _crop_box

NORMALIZATION_REVISION = "vision-normalize-2"


def box_area(box: list[float]) -> float:
    return (box[2] - box[0]) * (box[3] - box[1])


def intersection(a: list[float], b: list[float]) -> float:
    return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))


def union_area(boxes: list[list[float]]) -> float:
    """Exact rectangle union, so overlaps cannot inflate page coverage."""
    xs = sorted({b[x] for b in boxes for x in (0, 2)})
    area = 0.0
    for left, right in zip(xs, xs[1:]):
        intervals = sorted((b[1], b[3]) for b in boxes if b[0] < right and b[2] > left)
        height = 0.0
        end = float("-inf")
        for lo, hi in intervals:
            height += max(0, hi - max(end, lo))
            end = max(end, hi)
        area += (right - left) * height
    return area


def clean_box(raw: object, size: list[int]) -> tuple[list[float] | None, str | None]:
    if not isinstance(raw, (tuple, list)) or len(raw) != 4:
        return None, "invalid_box"
    try:
        values = [float(x) for x in raw]
    except (TypeError, ValueError):
        return None, "invalid_box"
    if not all(math.isfinite(v) for v in values):
        return None, "nonfinite_box"
    if any(v < -2 or v > size[i % 2] + 2 for i, v in enumerate(values)):
        return None, "box_outside_page"
    clipped = [max(0, min(size[i % 2], v)) for i, v in enumerate(values)]
    if clipped[0] >= clipped[2] or clipped[1] >= clipped[3]:
        return None, "invalid_box"
    return clipped, "detector_edge_roundoff_clamped" if clipped != values else None


def normalize_detections(raw: dict, size: list[int], direction: str) -> dict:
    if len(size) != 2 or any(type(v) is not int or v <= 0 for v in size):
        raise ValueError("Invalid source image dimensions")
    data = raw["detections"]
    boxes = {}
    indices = {}
    review = [{"kind": "confidence", "reason": "detector_confidence_unavailable"}]
    for kind in ("panels", "texts", "characters", "tails"):
        values = data.get(kind, [])
        if not isinstance(values, list) or len(values) > (256 if kind == "panels" else 2048):
            raise ValueError(f"Invalid or excessive {kind} detections")
        boxes[kind], indices[kind] = [], []
        for index, value in enumerate(values):
            box, reason = clean_box(value, size)
            if box is not None and kind == "texts" and _crop_box(box, *size, pad=8) == (0, 0, size[0], size[1]):
                box, reason = None, "full_page_text_box_rejected"
            if reason:
                review.append({"kind": kind, "source_index": index, "reason": reason})
            if box is not None:
                boxes[kind].append(box)
                indices[kind].append(index)
    fallback = not boxes["panels"]
    if fallback:
        boxes["panels"] = [[0, 0, size[0], size[1]]]
        indices["panels"] = [None]
        review.append({"kind": "panels", "reason": "no_panels_full_page_fallback"})
    coverage = union_area(boxes["panels"]) / (size[0] * size[1])
    if coverage < 0.70:
        review.append({"kind": "panels", "reason": "panel_coverage_below_70_percent"})
    for i, first in enumerate(boxes["panels"]):
        for j in range(i + 1, len(boxes["panels"])):
            if intersection(first, boxes["panels"][j]) / min(box_area(first), box_area(boxes["panels"][j])) > 0.10:
                review.append({"kind": "panels", "indices": [i, j], "reason": "overlapping_panels"})
    order, reasons = reading_order(boxes["panels"], direction)
    review += [{"kind": "order", "reason": reason} for reason in reasons]
    panels = [{"id": f"panel_{i:03d}", "source_index": indices["panels"][i], "bbox": box,
               "confidence": None, "origin": "full_page_fallback" if fallback else "detected"}
              for i, box in enumerate(boxes["panels"])]
    # Preserve raw associations only as provenance. Speaker assignment is M2.
    return {"image_size": size, "detections": boxes, "source_indices": indices, "panels": panels,
            "essential_text": [data.get("is_essential_text", [])[i]
                               if i < len(data.get("is_essential_text", [])) else None for i in indices["texts"]],
            "raw_associations": {key: data.get(key, []) for key in
                                 ("text_character_associations", "text_tail_associations", "character_cluster_labels")},
            "coverage": {"fraction": coverage, "method": "rectangle-union", "threshold": 0.70,
                         "measured_from_fallback": fallback},
            "order": {"panel_ids": [panels[i]["id"] for i in order], "direction": direction,
                      "method": "bounded-xycut-1", "needs_review": bool(reasons or fallback), "reasons": reasons},
            "review": review,
            "detector_revision": raw["adapter_revision"], "page_sha256": raw["page_sha256"]}
