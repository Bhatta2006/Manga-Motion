"""Bounded, source-coordinate camera geometry without semantic/model guesses."""

from __future__ import annotations

import math


def rect(value, size=None) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError("Expected a four-coordinate rectangle")
    if any(type(x) not in (int, float) or not math.isfinite(x) for x in value):
        raise ValueError("Rectangle coordinates must be finite numbers")
    x1, y1, x2, y2 = value
    if not (0 <= x1 < x2 and 0 <= y1 < y2):
        raise ValueError("Rectangle must have positive area and nonnegative coordinates")
    if size is not None and (x2 > size[0] or y2 > size[1]):
        raise ValueError("Rectangle leaves its source page")
    return list(value)


def contains(outer, inner, epsilon=1e-7) -> bool:
    return all(a <= b + epsilon for a, b in zip(outer[:2], inner[:2])) and all(
        a + epsilon >= b for a, b in zip(outer[2:], inner[2:]))


def union(boxes) -> list[float]:
    return [min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes)]


def interpolate(a, b, phase) -> list[float]:
    return [x + (y - x) * phase for x, y in zip(a, b)]


def solve_camera(panel, bubbles, size, *, recipe="push_in", duration=2.0) -> tuple[dict, dict]:
    """Protect the panel/text union throughout interpolation.

    Bleed is assigned text overflow plus 4% of protected width/height, clipped
    to the page. The focus target is the protected union center, not every
    bubble center. Only original page geometry is used.
    """
    if len(size) != 2 or any(type(x) is not int or x <= 0 for x in size):
        raise ValueError("Expected positive integer source dimensions")
    if recipe not in ("push_in", "pull_out", "pan", "hold"):
        raise ValueError("Unsupported bounded camera recipe")
    if type(duration) not in (int, float) or not math.isfinite(duration) or duration < .8:
        raise ValueError("Camera duration must be finite and at least 0.8 seconds")
    panel = rect(panel, size)
    bubbles = [rect(b, size) for b in bubbles]
    protected = union([panel, *bubbles])
    w, h = protected[2] - protected[0], protected[3] - protected[1]
    allowed = [max(0, protected[0] - w * .04), max(0, protected[1] - h * .04),
               min(size[0], protected[2] + w * .04), min(size[1], protected[3] + h * .04)]
    if recipe == "push_in":
        start, end = allowed, protected
    elif recipe == "pull_out":
        start, end = protected, allowed
    elif recipe == "pan":
        start = [allowed[0], allowed[1], protected[2], allowed[3]]
        end = [protected[0], allowed[1], allowed[2], allowed[3]]
    else:
        start = end = protected
    if start == end:
        recipe = "hold"
    event = {"t": 0, "type": "camera", "move": recipe, "from": start, "to": end,
             "dur": duration, "ease": "inOutSine"}
    audit = camera_metrics(event, protected, allowed, size, panel_width=panel[2]-panel[0])
    audit["protected"] = protected
    audit["allowed"] = allowed
    audit["text_overflow_bleed"] = not contains(panel, protected)
    return event, audit


def camera_metrics(event, protected, allowed, size, *, panel_width=None) -> dict:
    """Conservative analytic bounds for continuous inOutSine rectangle motion."""
    a, b = rect(event["from"], size), rect(event["to"], size)
    if event["ease"] != "inOutSine" or event["t"] != 0:
        raise ValueError("Solver audit expects its continuous sine event at t=0")
    if any(not contains(allowed, r) or not contains(r, protected) for r in (a, b)):
        raise ValueError("Camera leaves allowed bounds or crops protected art/text")
    pw, ph = protected[2] - protected[0], protected[3] - protected[1]
    widths = [r[2] - r[0] for r in (a, b)]
    heights = [r[3] - r[1] for r in (a, b)]
    bw, bh = allowed[2] - allowed[0], allowed[3] - allowed[1]
    max_relative_scale = max(bw / min(widths), bh / min(heights))
    slope = math.pi / (2 * event["dur"])
    zoom_rate = max(bw * abs(widths[1] - widths[0]) / min(widths)**2,
                    bh * abs(heights[1] - heights[0]) / min(heights)**2) * slope
    centers = [[(r[0] + r[2]) / 2, (r[1] + r[3]) / 2] for r in (a, b)]
    pan_rate = math.dist(*centers) / (panel_width if panel_width is not None else pw) * slope
    target = [(protected[0] + protected[2]) / 2, (protected[1] + protected[3]) / 2]
    # Margin inequalities are affine in frame edges; endpoints cover every pose.
    central = all(r[0] + .2 * (r[2] - r[0]) <= target[0] <= r[0] + .8 * (r[2] - r[0])
                  and r[1] + .2 * (r[3] - r[1]) <= target[1] <= r[1] + .8 * (r[3] - r[1]) for r in (a, b))
    if max_relative_scale > 1.4 or zoom_rate > .6 or pan_rate > 1.2 or not central:
        raise ValueError("Camera comfort constraint failed")
    return {"max_relative_scale": max_relative_scale, "max_zoom_rate_per_second": zoom_rate,
            "max_pan_panel_widths_per_second": pan_rate, "target_central_60_percent": central,
            "shake_count": 0, "constraint_violations": 0}
