"""Print a page's collage onto its background plate."""
import hashlib
from pathlib import Path

from PIL import Image


def tokens(theme, reverse=False):
    """Palette roles for the paper engine. A reversed page already floods ink A."""
    return dict(paper=theme.paper, inkA=theme.ink if reverse else theme.inkA, inkB=theme.inkB,
                ink=theme.ink, accent1=theme.accent1, accent2=theme.accent2)


def bake(slide, picture, source, collage, theme, seed, page, media, regions=(), manifest=None,
         reverse=False, canvas=(960.0, 540.0)):
    """Composite the collage over the page field and swap it into the slide."""
    import deck_collage
    import make_textures as mt

    with Image.open(source) as original:
        image = original.convert('RGB')
    if regions:
        image = mt.quiet_plate(image, list(regions), mt.hex2rgb(theme.inkA if reverse else theme.paper),
                               mt.seed_for(seed, page), canvas)
    scale = image.width / canvas[0]
    plate = deck_collage.render(collage, tokens(theme, reverse), seed * 977 + page, canvas, scale)
    layer = plate.image()
    if layer.size != image.size:
        layer = layer.resize(image.size, Image.LANCZOS)
    image.paste(layer, (0, 0), layer)
    path = Path(media) / f'bg{page}-collage.jpg'
    image.save(path, quality=88, subsampling=0)
    data = path.read_bytes()
    part = slide.part.related_part(picture._element.blip_rId)
    part._blob = data
    if manifest:
        record = next((row for row in manifest['pages'] if row['page'] == page), None)
        if record is not None:
            record.update(file=path.name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest()[:16],
                          collage=[dict(id=p['id'], role=p['role'], rect=p['rect'], stock=p.get('stock', 'bone'),
                                        rotation=p.get('rotation', 0)) for p in collage['pieces']],
                          **mt.ink_stats(image))
    return path
