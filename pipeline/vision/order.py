"""Bounded recursive page cuts for explicit RTL/LTR reading order."""

from __future__ import annotations


def _components(boxes: list[list[float]], ids: list[int], axis: int) -> list[list[int]]:
    # Ignore small detector border overlap, without changing returned art boxes.
    intervals = []
    for index in ids:
        box = boxes[index]
        margin = (box[axis + 2] - box[axis]) * 0.02
        intervals.append((box[axis] + margin, box[axis + 2] - margin, index))
    intervals.sort()
    groups: list[list[int]] = []
    end = float("-inf")
    for lo, hi, index in intervals:
        if lo > end:
            groups.append([])
        groups[-1].append(index)
        end = max(end, hi)
    return groups


def reading_order(boxes: list[list[float]], direction: str) -> tuple[list[int], list[str]]:
    if direction not in {"rtl", "ltr"}:
        raise ValueError("Reading direction must be rtl or ltr")
    if len(boxes) > 256:
        raise ValueError("Panel ordering requires at most 256 panels per page")
    reasons = []

    def visit(ids: list[int]) -> list[int]:
        if len(ids) <= 1:
            return ids
        for axis in (1, 0):  # Horizontal page bands, then directional columns.
            groups = _components(boxes, ids, axis)
            if len(groups) > 1:
                if axis == 0 and direction == "rtl":
                    groups.reverse()
                return [index for group in groups for index in visit(group)]
        # Interlocking/inset/borderless layout: never imply it was solved.
        reasons.append("ambiguous_panel_order")
        return sorted(ids, key=lambda i: (boxes[i][1], -boxes[i][0] if direction == "rtl" else boxes[i][0], i))

    return visit(list(range(len(boxes)))), sorted(set(reasons))
