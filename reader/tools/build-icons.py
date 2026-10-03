"""Rasterize the project's own geometric M icon; no source manga is involved."""
from pathlib import Path
from PIL import Image,ImageDraw
root=Path(__file__).resolve().parents[1]/'public'
for size in (192,512):
    image=Image.new('RGB',(size,size),'#171d1f');draw=ImageDraw.Draw(image)
    shape=[(40,136),(40,56),(64,56),(96,98),(128,56),(152,56),(152,136),(128,136),(128,92),(96,132),(64,92),(64,136)]
    draw.polygon([(round(x*size/192),round(y*size/192)) for x,y in shape],fill='#d6f192')
    image.save(root/f'icon-{size}.png',optimize=True)
