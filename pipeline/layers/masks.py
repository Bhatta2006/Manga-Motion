"""Original-pixel masks with a conservative continuous inverse-transform envelope.

For scale s>=1 about an anchor inside the crop and zero translation, inverse
coordinates move toward the anchor. Each original subject pixel cell traces a
bounded rectangle between s=1 and s=max; adding two sampling pixels encloses
all inverse bilinear reads. The union of these rectangles proves coverage for
all intervening poses. Added alpha selects existing source RGB, never new art.
A clean paper boundary and continuous swept text/panel guard remain required.
"""
import math
import numpy as np
from PIL import Image
from pipeline.cache import page_sha256
from pipeline.ingest.hashes import object_hash

REVISION='source-inverse-envelope-v1'
SCALE=1.035

def dilate(mask,radius):
    side=radius*2+1
    summed=np.pad(mask.astype('int32'),((radius,radius),(radius,radius)))
    summed=np.pad(summed,((1,0),(1,0))).cumsum(0,dtype='int32').cumsum(1,dtype='int32')
    return (summed[side:,side:]-summed[:-side,side:]-summed[side:,:-side]+summed[:-side,:-side])>0

def inverse_envelope(subject,anchor,scale):
    ys,xs=np.nonzero(subject);h,w=subject.shape;ax,ay=anchor
    l=np.floor(np.minimum(xs,ax+(xs-ax)/scale)-2).astype(int).clip(0,w)
    r=np.ceil(np.maximum(xs+1,ax+(xs+1-ax)/scale)+2).astype(int).clip(0,w)
    t=np.floor(np.minimum(ys,ay+(ys-ay)/scale)-2).astype(int).clip(0,h)
    b=np.ceil(np.maximum(ys+1,ay+(ys+1-ay)/scale)+2).astype(int).clip(0,h)
    diff=np.zeros((h+1,w+1),dtype='int32')
    for yy,xx,value in ((t,l,1),(t,r,-1),(b,l,-1),(b,r,1)):np.add.at(diff,(yy,xx),value)
    return diff.cumsum(0,dtype='int32').cumsum(1,dtype='int32')[:-1,:-1]>0

def bounds(mask):
    ys,xs=np.nonzero(mask)
    return None if not len(xs) else [int(xs.min()),int(ys.min()),int(xs.max())+1,int(ys.max())+1]

def uncovered(subject,mask,anchor,scale):
    """Dense audit uses bilinear alpha's four neighboring original mask cells."""
    ys,xs=np.nonzero(subject);x=anchor[0]+(xs+.5-anchor[0])/scale-.5;y=anchor[1]+(ys+.5-anchor[1])/scale-.5
    # Edge pixels sample with clamp-to-edge inside the source crop.
    l=np.floor(x).astype(int);t=np.floor(y).astype(int);h,w=mask.shape
    covered=np.ones(len(xs),dtype=bool)
    for dx,dy in ((0,0),(1,0),(0,1),(1,1)):covered&=mask[np.clip(t+dy,0,h-1),np.clip(l+dx,0,w-1)]
    return int((~covered).sum())

def swept_guard(mask,box,anchor,poses,panel,texts):
    """Affine corner extrema at knots enclose every intervening opaque cell."""
    ys,xs=np.nonzero(mask);w,h=box[2]-box[0],box[3]-box[1];ax,ay=box[0]+anchor[0]*w,box[1]+anchor[1]*h
    l=np.full(len(xs),np.inf);t=l.copy();r=np.full(len(xs),-np.inf);b=r.copy()
    for pose in poses:
        s=pose['scale'];dx,dy=pose['offset'];dx*=panel[2]-panel[0];dy*=panel[3]-panel[1]
        l=np.minimum(l,ax+(box[0]+xs-ax)*s+dx);r=np.maximum(r,ax+(box[0]+xs+1-ax)*s+dx)
        t=np.minimum(t,ay+(box[1]+ys-ay)*s+dy);b=np.maximum(b,ay+(box[1]+ys+1-ay)*s+dy)
    if l.min()<panel[0] or t.min()<panel[1] or r.max()>panel[2] or b.max()>panel[3]:return 'motion_crosses_panel'
    for text in texts:
        if np.any((l<text[2]+2)&(r>text[0]-2)&(t<text[3]+2)&(b>text[1]-2)):return 'motion_intersects_protected_text'
    return None

def prepare_mask(rgb,raw,source_bbox,panel,texts,prompt,region=None):
    """Return a proven candidate plus private audit; perception still needs review."""
    full=np.zeros(rgb.shape[:2],dtype=bool);x,y,r,b=source_bbox;full[y:b,x:r]=raw
    px,py,pr,pb=[math.ceil(v) if i<2 else math.floor(v) for i,v in enumerate(region or panel)]
    subject=full[py:pb,px:pr].copy();patch=rgb[py:pb,px:pr];ink=np.min(patch,axis=2)<245
    if not subject.any():return None,'empty_subject'
    initial=bounds(subject);box=initial
    # A cropped torso stays attached to the nearest panel edge; free subjects
    # expand around their center. Never shrink or translate to invent a reveal.
    anchor_point=[0 if initial[0]<=3 else subject.shape[1] if initial[2]>=subject.shape[1]-3 else (initial[0]+initial[2])/2,
                  subject.shape[0] if region else 0 if initial[1]<=3 else subject.shape[0] if initial[3]>=subject.shape[0]-12 else (initial[1]+initial[3])/2]
    if initial[0]<=3 and initial[2]>=subject.shape[1]-3:return None,'subject_spans_panel_width'
    if not region and initial[1]<=3 and initial[3]>=subject.shape[0]-3:return None,'subject_spans_panel_height'
    # Add missed original ink only inside the inverse envelope. This grows
    # inward around concavities rather than grabbing a wide background collar.
    for _ in range(32):
        mask=inverse_envelope(subject,anchor_point,SCALE);added=mask&ink&~subject
        if not added.any():break
        subject|=added
    else:return None,'no_clean_original_paper_boundary'
    collar=mask&~subject
    box=bounds(mask);box[0]=min(box[0],math.floor(anchor_point[0]));box[1]=min(box[1],math.floor(anchor_point[1]));box[2]=max(box[2],math.ceil(anchor_point[0]));box[3]=max(box[3],math.ceil(anchor_point[1]));x,y,r,b=box;source=[px+x,py+y,px+r,py+b]
    # Reject SAM masks that absorb unrelated background far from the box prompt.
    margin=max(prompt[2]-prompt[0],prompt[3]-prompt[1])*.12+8
    sb=bounds(subject);subject_global=[px+sb[0],py+sb[1],px+sb[2],py+sb[3]]
    if any(subject_global[i]<prompt[i]-margin for i in (0,1)) or any(subject_global[i]>prompt[i]+margin for i in (2,3)):return None,'mask_extends_beyond_character_prompt'
    anchor=[(anchor_point[0]-x)/(r-x),(anchor_point[1]-y)/(b-y)]
    if any(a<0 or a>1 for a in anchor):return None,'invalid_anchor'
    poses=[{'u':0,'scale':1,'offset':[0,0]},{'u':.35,'scale':SCALE,'offset':[0,0]},{'u':.8,'scale':SCALE,'offset':[0,0]},{'u':1,'scale':1.01,'offset':[0,0]}]
    cropped=mask[y:b,x:r];reason=swept_guard(cropped,source,anchor,poses,panel,texts)
    if reason:return None,reason
    subject_crop=subject[y:b,x:r];a=[anchor_point[0]-x,anchor_point[1]-y]
    maximum=max(uncovered(subject_crop,cropped,a,1+(SCALE-1)*u) for u in np.linspace(0,1,101))
    if maximum:return None,'dense_sampling_uncovered_source'
    audit={'method':'conservative-mask-envelope-v1','proof':'union of inverse source-cell rectangles, s>=1, zero offset, anchor inside source crop',
           'sampling_guard_pixels':2,
           'dense_scales':101,'max_uncovered_pixels':maximum,'subject_pixels':int(subject.sum()),'collar_pixels':int(collar.sum()),
           'paper_min_rgb':int(patch[collar].min()) if collar.any() else None,'visual_review_required':True}
    return {'source_bbox':source,'anchor':anchor,'poses':poses,'mask_array':cropped,'subject_array':subject_crop,'audit':audit},None

def save_candidate(store,page,panel,raw,prepared):
    rgba=np.full((*prepared['mask_array'].shape,4),255,dtype='uint8');rgba[:,:,3]=prepared['mask_array']*255
    name=f'layers/{page["page_sha256"]}-{panel["id"]}-{raw["id"]}-collar.png';path=store.asset(name);Image.fromarray(rgba,'RGBA').save(path)
    transform={k:prepared[k] for k in ('source_bbox','anchor','poses')}
    return {'id':f'{page["id"]}_{raw["id"]}','kind':'character','source_page':page['id'],**transform,'mask':name,'depth':.7,
            'safety':{'method':'conservative-mask-envelope-v1','source_sha256':page['page_sha256'],'mask_sha256':page_sha256(path),
                      'transform_sha256':object_hash(transform),'max_uncovered_pixels':0}}
