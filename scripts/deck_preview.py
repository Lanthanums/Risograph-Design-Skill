"""Compact contact sheets for slide decks; no poster layout assumptions."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps, ImageFilter
import hashlib

def variants_contact(paths, output, columns=3, width=480):
    paths = list(paths)
    if not paths:
        raise ValueError('No rendered slides for contact sheet')
    columns = min(columns, len(paths))
    height, label, gap = round(width * 9 / 16), 24, 16
    rows = (len(paths) + columns - 1) // columns
    sheet = Image.new('RGB', (columns * (width + gap) + gap,
                              rows * (height + label + gap) + gap), '#eceae5')
    draw = ImageDraw.Draw(sheet)
    for i, path in enumerate(paths):
        x = gap + i % columns * (width + gap)
        y = gap + i // columns * (height + label + gap)
        draw.text((x, y + 3), f'{i + 1:02d}', fill='#333333')
        with Image.open(path) as image:
            thumb = ImageOps.contain(image.convert('RGB'), (width, height))
            sheet.paste(thumb, (x + (width - thumb.width) // 2, y + label))
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)
    return output


RUBRIC = ('focal_point', 'hierarchy', 'evidence', 'print_craft', 'page_rhythm', 'readability')

def review_images(png,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    im=Image.open(png).convert('RGB');thumb=im.resize((max(1,round(im.width*.1)),max(1,round(im.height*.1))),Image.Resampling.LANCZOS)
    thumb.save(out/'thumbnail-10pct.png');thumb.filter(ImageFilter.GaussianBlur(3)).save(out/'blur.png')
    return {'render_sha256':hashlib.sha256(Path(png).read_bytes()).hexdigest(),'render_size':list(im.size),'thumbnail_size':list(thumb.size)}
