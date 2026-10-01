"""Crop geometry validation shared by chapter OCR and quality audits."""

from pipeline.adapters.magi import _crop_box


def crop_boxes(texts: list[list[float]], size: list[int]) -> list[list[int]]:
    result = []
    for index, text in enumerate(texts):
        box = _crop_box(text, *size, pad=8)
        if box is None:
            raise ValueError(f"Invalid normalized text box {index}")
        result.append(list(box))
    return result
