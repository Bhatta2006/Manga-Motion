"""Conservative source-only foreground feasibility, without a segmentation model.

A source rectangle with an exactly uniform paper guard can be scaled/translated
over its old position without revealing the original subject underneath. The
guard is inspected on both sides of the boundary. No background fill is made.
"""
import math
import numpy as np


def intersects(a, b):
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


def parallax_pose(box, phase):
    w, h = box[2]-box[0], box[3]-box[1]
    # Always cover the old rectangle; differential motion <= 0.4% of its width.
    return 1.02, math.sin(phase*math.pi*2)*w*.004, math.sin(phase*math.pi)*h*.004


def eligible_region(rgb, character, panel, texts):
    """Return safe integer source rectangle or a specific rejection reason."""
    height, width = rgb.shape[:2]
    box = [math.floor(character[0])-12, math.floor(character[1])-12,
           math.ceil(character[2])+12, math.ceil(character[3])+12]
    guard = math.ceil(max(box[2]-box[0], box[3]-box[1])*.015)+3
    outer = [box[0]-guard, box[1]-guard, box[2]+guard, box[3]+guard]
    if outer[0] < max(0, panel[0]) or outer[1] < max(0, panel[1]) or outer[2] > min(width, panel[2]) or outer[3] > min(height, panel[3]):
        return None, "region/guard crosses panel edge"
    if any(intersects(outer, text) for text in texts):
        return None, "region/guard intersects text"
    x0,y0,x1,y1 = box
    ox0,oy0,ox1,oy1 = outer
    patch = rgb[oy0:oy1, ox0:ox1]
    ring = np.ones(patch.shape[:2], dtype=bool)
    ring[guard*2:patch.shape[0]-guard*2, guard*2:patch.shape[1]-guard*2] = False
    colors = patch[ring]
    if not len(colors) or np.any(colors != colors[0]) or min(colors[0]) < 245:
        return None, "boundary is not uniform original paper"
    return box, None
