"""Conservative text metadata for future pacing/SFX; no fabricated text classes."""

from __future__ import annotations

import unicodedata

from pipeline.vision.panels import box_area, intersection


def normalize_text(text: str) -> str:
    # Preserve punctuation, language and wording. No translation or autocorrection.
    return " ".join(unicodedata.normalize("NFC", text).split())


def text_metadata(normalized: dict, ocr: dict) -> dict:
    texts = normalized["detections"]["texts"]
    if len(texts) != len(ocr["ocr"]):
        raise ValueError("OCR/text detection count mismatch")
    panels = normalized["panels"]
    ordered = {value: i for i, value in enumerate(normalized["order"]["panel_ids"])}
    items = []
    review = [{"kind": "confidence", "reason": "ocr_confidence_unavailable"}] if texts else []
    for index, (box, result) in enumerate(zip(texts, ocr["ocr"])):
        if result["text_index"] != index or result["bbox"] != box:
            raise ValueError(f"OCR geometry/index mismatch at text {index}")
        overlaps = [(intersection(box, panel["bbox"]) / box_area(box), panel["id"]) for panel in panels]
        overlaps.sort(key=lambda pair: (-pair[0], ordered[pair[1]]))
        overlap, panel_id = overlaps[0]
        reasons = []
        if overlap < 0.5:
            reasons.append("text_outside_detected_panels")
            panel_id = None
        elif len(overlaps) > 1 and overlaps[1][0] > 0.5 and overlap - overlaps[1][0] < 0.1:
            reasons.append("ambiguous_text_panel")
        value = normalize_text(result["text"])
        if not value:
            reasons.append("empty_ocr")
        if result["status"] != "text_returned_unverified":
            reasons.append(result["status"])
        essential = normalized["essential_text"][index]
        if type(essential) is not bool:
            essential = None
            reasons.append("essential_text_class_unknown")
        # The binary Magi flag does not distinguish dialogue/caption/SFX/sign.
        item = {**{k: v for k, v in result.items() if k != "run_seconds"},
                "id": f"text_{normalized['source_indices']['texts'][index]:03d}",
                "source_index": normalized["source_indices"]["texts"][index],
                "raw_text": result["text"], "text": value, "panel_id": panel_id,
                "panel_overlap": overlap, "kind": "unknown", "kind_confidence": None,
                "is_essential": essential, "reading_candidate": essential is True and panel_id is not None,
                "confidence": None, "confidence_status": "uncalibrated",
                "review_reasons": reasons, "needs_review": bool(reasons)}
        items.append(item)
        review += [{"kind": "text", "id": item["id"], "reason": reason} for reason in reasons]
    return {"texts": items, "review": review,
            "confidence_note": "OCR accuracy and text kinds are uncalibrated; essential flags are model hints, not final classes."}
