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


def review_sheets(paths, folder, per=6, width=640):
    """Numbered sheets of six slides, large enough to read body copy.

    One sheet costs about as much to look at as a single full-size slide, so
    a reviewer can see the whole deck first and open a page only to confirm
    a defect.
    """
    paths = list(paths)
    folder = Path(folder)
    for old in folder.glob('sheet-*.png'):
        old.unlink()
    sheets = []
    for start in range(0, len(paths), per):
        group = paths[start:start + per]
        columns = 2 if len(group) > 1 else 1
        height, label, gap = round(width * 9 / 16), 20, 10
        rows = (len(group) + columns - 1) // columns
        sheet = Image.new('RGB', (columns * (width + gap) + gap, rows * (height + label + gap) + gap), '#eceae5')
        draw = ImageDraw.Draw(sheet)
        for i, path in enumerate(group):
            x = gap + i % columns * (width + gap)
            y = gap + i // columns * (height + label + gap)
            draw.text((x, y + 4), f'{start + i + 1:02d}', fill='#333333')
            with Image.open(path) as image:
                sheet.paste(image.convert('RGB').resize((width, height), Image.Resampling.LANCZOS), (x, y + label))
        output = folder / f'sheet-{len(sheets) + 1:02d}.png'
        sheet.save(output)
        sheets.append(output)
    return sheets


def page_map(style, pages):
    """One short line per decision a reviewer would otherwise dig out of the sidecar."""
    paper = {}
    for record in style.get('paper_collage', ()):
        if record.get('purpose') == 'collage' and record.get('role') in ('face', 'strata', 'slip', 'picture'):
            paper.setdefault(record['page'], set()).add(
                dict(strata='scene', picture='picture').get(record['role'], 'paper'))
    quotes = {row['page']: row['layout'] for row in style.get('quote_compositions', ())}
    flooded = set(style.get('reversed_pages', ()))
    cells = []
    for number, kind in enumerate(pages, 1):
        notes = [kind or 'page']
        if number in quotes:
            notes.append(quotes[number])
        if 'paper' in paper.get(number, ()):
            notes.append('paper')
        elif 'scene' in paper.get(number, ()):
            notes.append('scene')
        if 'picture' in paper.get(number, ()):
            notes.append('picture')
        if number in flooded:
            notes.append('flood')
        cells.append(f'{number:02d} ' + ' '.join(notes))
    lines = ['pages: ' + ' | '.join(cells)]
    for row in style.get('refinement_fallbacks', ()):
        lines.append(f"adjusted: p{row['page']:02d} " + str(row['reasons'][0])[:110])
    return lines


RUBRIC = ('focal_point', 'hierarchy', 'evidence', 'print_craft', 'page_rhythm', 'readability')

def review_images(png,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    im=Image.open(png).convert('RGB');thumb=im.resize((max(1,round(im.width*.1)),max(1,round(im.height*.1))),Image.Resampling.LANCZOS)
    thumb.save(out/'thumbnail-10pct.png');thumb.filter(ImageFilter.GaussianBlur(3)).save(out/'blur.png')
    return {'render_sha256':hashlib.sha256(Path(png).read_bytes()).hexdigest(),'render_size':list(im.size),'thumbnail_size':list(thumb.size)}
