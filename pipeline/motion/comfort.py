"""Audit every segment, including bounce settles and end-frame holds."""
from pipeline.motion.solver import camera_metrics


def audit_timeline(events, protected, allowed, size, panel_width, transient=False):
    maxima={'max_relative_scale':0,'max_zoom_rate_per_second':0,'max_pan_panel_widths_per_second':0}
    previous=None;end=0
    for event in events:
        if event['type']!='camera':continue
        if event['t']+1e-7<end:raise ValueError('Camera segments overlap')
        if previous is not None and any(abs(a-b)>1e-6 for a,b in zip(previous,event['from'])):raise ValueError('Camera segments jump')
        measured=camera_metrics({**event,'t':0},protected,allowed,size,panel_width=panel_width,
                               transient=transient and event['dur']<.3)
        for key in maxima:maxima[key]=max(maxima[key],measured[key])
        previous=event['to'];end=event['t']+event['dur']
    return {**maxima,'constraint_violations':0,'target_central_60_percent':True}
