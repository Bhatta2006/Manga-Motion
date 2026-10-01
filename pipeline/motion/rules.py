"""Restrained M1c recipes; semantic directing belongs to M3."""

import math


def panel_rule(index: int, has_text: bool, single_panel: bool) -> tuple[str, str]:
    if single_panel:
        return "pull_out", "wide"
    return ("push_in", "pull_out", "pan")[index % 3], "medium" if has_text else "wide"


def safe_transition(previous, following, *, panel_widths=None) -> tuple[dict, dict]:
    """Cut when a 400 ms glide would exceed sustained camera speed limits."""
    a, b = previous['to'], following['from']
    widths = [r[2]-r[0] for r in (a,b)]
    heights = [r[3]-r[1] for r in (a,b)]
    centers = [[(r[0]+r[2])/2,(r[1]+r[3])/2] for r in (a,b)]
    slope = math.pi/(2*.4)
    pan = math.dist(*centers)/min(panel_widths or widths)*slope
    zoom = max(max(widths)*abs(widths[1]-widths[0])/min(widths)**2,
               max(heights)*abs(heights[1]-heights[0])/min(heights)**2)*slope
    allowed = pan <= 1.2 and zoom <= .6
    return ({'type':'glide','dur':.4} if allowed else {'type':'cut','dur':0}), {
        'glide_allowed':allowed,'candidate_pan_rate':pan,'candidate_zoom_rate':zoom,
        'reason':None if allowed else 'glide_exceeds_comfort_speed'}
