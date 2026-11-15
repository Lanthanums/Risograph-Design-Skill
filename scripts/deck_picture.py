"""Pictures supplied for a deck page, printed in the deck's own inks.

An author who can make or source an image hands it to the page as
``image``. It is never placed as it came. The picture is separated into the
two deck inks as halftone screens on paper stock, then mounted in the page
collage as a taped print with a torn edge. That keeps a picture from any
source inside the print language of the deck.
"""
from pathlib import Path

import numpy as np
from PIL import Image

TREATMENTS = ('duotone', 'mono', 'keep')


def resolve(value, base_dir):
    """Normalise a page's ``image`` setting to {path, treatment}, with an absolute path."""
    from artifact_io import input_path

    setting = dict(path=value) if isinstance(value, str) else dict(value) if isinstance(value, dict) else None
    if not setting or not isinstance(setting.get('path'), str):
        raise ValueError('image must be a file path or an object with a path')
    treatment = setting.get('treatment', 'duotone')
    if treatment not in TREATMENTS:
        raise ValueError(f"image treatment must be one of {', '.join(TREATMENTS)}")
    path = input_path(setting['path'], base_dir, 'deck image')
    if path.suffix.lower() not in ('.png', '.jpg', '.jpeg', '.webp'):
        raise ValueError('image must be a PNG, JPEG or WebP file')
    with Image.open(path) as image:
        width, height = image.size
    if min(width, height) < 400:
        raise ValueError(f'image {path.name} is {width}x{height}; supply at least 400 px on the short side')
    return dict(path=str(path), treatment=treatment, aspect=width / height)


def _cover(path, width, height):
    """Load, flatten on white and crop to fill the box, keeping the centre."""
    with Image.open(path) as source:
        image = source.convert('RGBA')
    flat = Image.new('RGBA', image.size, 'white')
    flat.alpha_composite(image)
    scale = max(width / flat.width, height / flat.height)
    size = (max(width, round(flat.width * scale)), max(height, round(flat.height * scale)))
    flat = flat.convert('RGB').resize(size, Image.LANCZOS)
    left, top = (size[0] - width) // 2, (size[1] - height) // 2
    return np.asarray(flat.crop((left, top, left + width, top + height)), np.float32) / 255


def riso_print(setting, width, height, theme, scale, rng):
    """Return the picture as paper with ink on it: an (H, W, 3) float array."""
    import deck_paper_stock as ps

    pixels = _cover(setting['path'], width, height)
    paper = np.broadcast_to(ps.stock_colors(theme)['bone'][None, None, :], (height, width, 3)).copy()
    if setting['treatment'] == 'keep':
        # The source colours, laid on the stock like a process print.
        return paper * (.12 + .88 * pixels)
    luminance = pixels @ np.array([.299, .587, .114], np.float32)
    low, high = np.percentile(luminance, (2, 98))
    dark = 1 - np.clip((luminance - low) / max(high - low, 1e-3), 0, 1)
    origin = (int(rng.integers(0, 64)), int(rng.integers(0, 64)))
    wobble = 1 + .05 * ps.noise2(height, width, 26 * scale, rng)
    if setting['treatment'] == 'mono':
        cover = ps.halftone(height, width, dark ** .9 * wobble, 3.0, 45, scale, origin)
        return ps._ink(paper, theme['inkA'], cover * .96)
    # The second ink carries the middle of the picture; the first ink closes the shadows.
    middle = np.clip(dark / .72, 0, 1) ** 1.15 * .9
    shadow = np.clip((dark - .34) / .66, 0, 1) ** .9
    paper = ps._ink(paper, theme['inkB'], ps.halftone(height, width, middle * wobble, 3.4, 15, scale, origin) * .92)
    return ps._ink(paper, theme['inkA'], ps.halftone(height, width, shadow * wobble, 3.0, 45, scale, origin) * .96)


def mount(composer, opening, setting):
    """Tape the print into an opening, over a sliver of colour. Returns its rect."""
    rng = composer.rng
    width_room, height_room = opening[2] - opening[0], opening[3] - opening[1]
    aspect = min(1.8, max(.75, setting['aspect']))
    width = min(width_room - 22, 390, (height_room - 20) * aspect)
    height = width / aspect
    if width < 150 or height < 104:
        raise ValueError('No room for the picture beside this copy')
    x0 = opening[2] - width - 12 if opening[0] + width_room / 2 > 480 else opening[0] + 12
    y0 = opening[1] + (height_room - height) * .42
    rect = [x0, y0, x0 + width, y0 + height]
    tilt = rng.uniform(1.2, 2.4) * rng.choice((-1, 1))
    back = composer.fit([rect[0] + 14, rect[1] + 16, rect[2] + 16, rect[3] + 15], pad=4)
    if back:
        composer.sheet(composer.under, 'sliver', back, composer.field_name(1), ('torn', 'rip', 'torn', 'cut'),
                       -tilt * 1.3)
    composer.sheet(composer.under, 'picture', rect, None, ('cut', 'cut', 'torn', 'cut'), tilt,
                   picture=dict(path=setting['path'], treatment=setting['treatment'], margin=6))
    composer.tape(rect[0] + width * rng.uniform(.3, .7), rect[1] + 1)
    return rect
