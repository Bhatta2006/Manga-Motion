"""Panel audio-clock extent shared with the reader, without Auto reading policy."""

import math

PANEL_TAIL_SECONDS = .4


def timeline_duration(events, clip_durations=None) -> float:
    clip_durations = clip_durations or {}
    ends = [.8]
    for event in events:
        duration = event.get("dur", clip_durations.get(event.get("file"), 0))
        if any(type(x) not in (int, float) or not math.isfinite(x) or x < 0 for x in (event["t"], duration)):
            raise ValueError("Invalid timeline time/duration")
        ends.append(event["t"] + duration)
    return max(ends) + PANEL_TAIL_SECONDS
