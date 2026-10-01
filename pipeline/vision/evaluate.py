"""Objective matching/error counts against explicitly supplied reference labels."""

from __future__ import annotations

import re
import unicodedata

from pipeline.vision.panels import box_area, intersection


def words(text: str) -> list[str]:
    value = unicodedata.normalize("NFKC", text).casefold().replace("’", "'")
    return re.findall(r"[^\W_]+(?:'[^\W_]+)*", value)


def edit_distance(reference: list, prediction: list) -> int:
    row = list(range(len(prediction) + 1))
    for i, value in enumerate(reference, 1):
        next_row = [i]
        for j, other in enumerate(prediction, 1):
            next_row.append(min(row[j] + 1, next_row[-1] + 1, row[j - 1] + (value != other)))
        row = next_row
    return row[-1]


def panel_matches(expected: list[dict], observed: list[dict], threshold: float) -> dict[int, int]:
    """Maximum-cardinality one-to-one matching at a predeclared IoU threshold."""
    if not 0 < threshold <= 1:
        raise ValueError("IoU threshold must be in (0, 1]")
    edges = []
    for golden in expected:
        candidates = []
        for index, prediction in enumerate(observed):
            if prediction.get("origin", "detected") != "detected":
                continue  # A page fallback is not a successful learned detection.
            area = intersection(golden["bbox"], prediction["bbox"])
            total = box_area(golden["bbox"]) + box_area(prediction["bbox"]) - area
            iou = area / total if total > 0 else 0
            if iou >= threshold:
                candidates.append((iou, index))
        edges.append([index for _, index in sorted(candidates, reverse=True)])
    assignment = {}

    def augment(golden: int, seen: set[int]) -> bool:
        for predicted in edges[golden]:
            if predicted in seen:
                continue
            seen.add(predicted)
            if predicted not in assignment or augment(assignment[predicted], seen):
                assignment[predicted] = golden
                return True
        return False

    for golden in range(len(expected)):
        augment(golden, set())
    return {golden: predicted for predicted, golden in assignment.items()}


def score_analysis(analysis: dict, reference: dict) -> dict:
    if len(analysis["pages"]) != len(reference["pages"]):
        raise ValueError("Reference/analysis page count mismatch")
    tp = fp = fn = correct_order = words_total = word_edits = crops = missing_crops = unlabeled_crops = 0
    per_page = []
    for page, golden in zip(analysis["pages"], reference["pages"]):
        if page["page_sha256"] != golden["page_sha256"] or analysis["direction"] != golden["direction"]:
            raise ValueError(f"Reference input/direction mismatch: {page['id']}")
        matched = panel_matches(golden["panels"], page["panels"], reference["iou_threshold"])
        count = len(matched)
        tp += count
        fp += len(page["panels"]) - count
        fn += len(golden["panels"]) - count
        predicted_to_gold = {page["panels"][p]["id"]: golden["panels"][g]["id"] for g, p in matched.items()}
        order = [predicted_to_gold.get(i) for i in page["order"]["panel_ids"]]
        order_correct = order == golden["order"]
        correct_order += int(order_correct)
        observed_text = {item["source_index"]: item["text"] for item in page["texts"]}
        labeled = {item["text_index"] for item in golden["ocr"]}
        unlabeled_crops += len(set(observed_text) - labeled)
        page_edits = 0
        for item in golden["ocr"]:
            if item["category"] != "dialogue":
                continue
            expected = words(item["reference"])
            prediction = words(observed_text.get(item["text_index"], ""))
            error = edit_distance(expected, prediction)
            word_edits += error
            page_edits += error
            words_total += len(expected)
            crops += 1
            missing_crops += int(item["text_index"] not in observed_text)
        per_page.append({"id": page["id"], "matched_panels": count,
                         "predicted_panels": len(page["panels"]), "reference_panels": len(golden["panels"]),
                         "fully_correct_order": order_correct, "dialogue_word_edits": page_edits,
                         "coverage": page["coverage"]["fraction"], "review_flags": len(page["review"])})
    precision = tp / (tp + fp) if tp + fp else 0
    recall = tp / (tp + fn) if tp + fn else 0
    order_accuracy = correct_order / len(per_page) if per_page else 0
    wer = word_edits / words_total if words_total else None
    return {"label_method": reference["method"], "iou_threshold": reference["iou_threshold"],
            "panel_tp": tp, "panel_fp": fp, "panel_fn": fn, "panel_precision": precision, "panel_recall": recall,
            "fully_correct_pages": correct_order, "pages_total": len(per_page), "page_order_accuracy": order_accuracy,
            "dialogue_crops": crops, "dialogue_reference_words": words_total, "dialogue_word_edits": word_edits,
            "dialogue_lexical_wer": wer, "missing_dialogue_crops": missing_crops, "unlabeled_predicted_crops": unlabeled_crops,
            "ocr_scope": "Detected/reference crop subset only; not full-page text detection recall. Punctuation excluded except in-word apostrophes.",
            "thresholds_met_on_reference_subset": precision >= .95 and recall >= .95 and order_accuracy >= .97 and wer is not None and wer <= .03,
            "pages": per_page}
