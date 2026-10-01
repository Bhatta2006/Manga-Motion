"""Reading budgets compiled into ordinary v1 camera holds."""

import math
import re
import unicodedata

PANEL_TAIL_SECONDS = .4
PACING_REVISION = 'reading-1'
READING_KINDS = {'dialogue', 'caption'}
EXCLUDED_KINDS = {'sfx', 'watermark', 'translator_note', 'sign', 'nonverbal'}


def reading_rate(value):
    if type(value) is not int or not 80 <= value <= 600:
        raise ValueError('Reading speed must be an integer from 80 to 600 words/minute')
    return value


def word_count(text):
    return len(re.findall(r"[^\W_]+(?:['’][^\W_]+)*", unicodedata.normalize('NFKC', text), re.UNICODE))


def reading_budget(texts, wpm=240, *, art_seconds=2.0):
    """Unknown OCR is an estimate, never an asserted dialogue classification.

    Known non-reading kinds contribute nothing. Unclassified essential candidates
    use a separate conservative estimate plus a 2 s uncertainty margin; unreadable
    crops receive at least 6 s. Empty panels receive only art time. No upper cap.
    """
    reading_rate(wpm)
    if type(art_seconds) not in (int, float) or not math.isfinite(art_seconds) or art_seconds < 0:
        raise ValueError('Invalid art time')
    words = estimated = failed = 0
    issues = []
    for text in texts:
        kind = text.get('kind', 'unknown')
        if kind in EXCLUDED_KINDS:
            continue
        value = text.get('text') or ''
        count = word_count(value)
        if kind in READING_KINDS:
            words += count
            if not count:
                failed += 1
                issues.append({'text_id':text['id'], 'reason':'reading_text_empty'})
        elif text.get('is_essential') is not False:
            estimated += count
            issues.append({'text_id':text['id'], 'reason':'text_kind_unknown'})
            if not count:
                failed += 1
    seconds = art_seconds + (words + estimated) * 60 / wpm
    if issues:
        seconds += 2
    if failed:
        seconds = max(seconds, 6 + 2 * (failed - 1))
    return {'reading_wpm':wpm, 'words':words, 'estimated_unknown_words':estimated,
            'failed_crops':failed, 'seconds':round(seconds + PANEL_TAIL_SECONDS, 6),
            'needs_review':bool(issues), 'issues':issues}


def timeline_duration(events, clip_durations=None) -> float:
    clip_durations = clip_durations or {}
    ends = [.8]
    for event in events:
        if event.get('type') in ('music', 'ambience'):
            continue  # reserved future policy: a bed is never the reading clock
        duration = event.get("dur", clip_durations.get(event.get("file"), 0))
        if event.get('type') == 'line':
            duration = max(duration, clip_durations.get(event.get('audio'), 0))
        if any(type(x) not in (int, float) or not math.isfinite(x) or x < 0 for x in (event["t"], duration)):
            raise ValueError("Invalid timeline time/duration")
        ends.append(event["t"] + duration)
    return max(ends) + PANEL_TAIL_SECONDS
