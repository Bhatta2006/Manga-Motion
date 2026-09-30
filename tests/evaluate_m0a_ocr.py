"""Score private OCR artifacts against saved visual references; never train on them."""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path


def words(text: str) -> list[str]:
    value = unicodedata.normalize("NFKC", text).casefold().replace("’", "'")
    return re.findall(r"[^\W_]+(?:'[^\W_]+)*", value)


def edit_distance(reference: list[str], prediction: list[str]) -> int:
    row = list(range(len(prediction) + 1))
    for index, token in enumerate(reference, 1):
        next_row = [index]
        for column, other in enumerate(prediction, 1):
            next_row.append(min(row[column] + 1, next_row[-1] + 1,
                                row[column - 1] + (token != other)))
        row = next_row
    return row[-1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, help="e.g. baberu-cpu-t4.json or ocr.json")
    parser.add_argument("--label", required=True)
    parser.add_argument("--chapter", default="golden-m0")
    args = parser.parse_args()
    if any(not re.fullmatch(r"[A-Za-z0-9_-]+", value) for value in (args.label, args.chapter)) or Path(args.candidate).name != args.candidate:
        parser.error("Use simple local file names and labels")
    root = Path(__file__).resolve().parents[1]
    private = root / "library" / args.chapter
    reference = json.loads((private / "ocr-reference.json").read_text(encoding="utf-8"))
    scores = {name: {"crops": 0, "nonempty": 0, "reference_words": 0,
                    "word_edits": 0, "lexical_exact_crops": 0} for name in ("dialogue", "dialogue_caption", "all")}
    rows = []
    for index, page in enumerate(reference["pages"], 1):
        folder = private / "cache" / f"p{index:03d}-{page['page_sha256'][:12]}"
        candidate = json.loads((folder / args.candidate).read_text(encoding="utf-8"))
        assert candidate["page_sha256"] == page["page_sha256"]
        assert len(candidate["ocr"]) == len(page["items"])
        for expected, observed in zip(page["items"], candidate["ocr"]):
            assert expected["text_index"] == observed["text_index"]
            text = observed.get("text", " ".join(observed.get("raw", {}).get("ocr_texts", [])))
            ref_tokens, pred_tokens = words(expected["reference"]), words(text)
            edits = edit_distance(ref_tokens, pred_tokens)
            rows.append({"page": index, **expected, "prediction": text, "word_edits": edits})
            for name, score in scores.items():
                included = name == "all" or expected["category"] == "dialogue" or (
                    name == "dialogue_caption" and expected["category"] == "caption")
                if not included:
                    continue
                score["crops"] += 1
                score["nonempty"] += int(bool(text.strip()))
                score["reference_words"] += len(ref_tokens)
                score["word_edits"] += edits
                score["lexical_exact_crops"] += int(ref_tokens == pred_tokens)
    for score in scores.values():
        score["word_error_rate"] = score["word_edits"] / score["reference_words"]
    report = {"candidate": args.candidate, "normalization": "NFKC, lowercase, punctuation ignored except apostrophes inside words",
              "reference_method": reference["method"], "scores": scores, "rows": rows}
    (root / "reports" / f"M0a-opt-quality-{args.label}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(scores, indent=2))


if __name__ == "__main__":
    main()
