"""Canvas geometry in points. Deck defaults are a compatibility contract."""
import sys
sys.dont_write_bytecode = True
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class CanvasSpec:
    width: float = 960.0
    height: float = 540.0
    safe: tuple = (48.0, 58.0, 912.0, 476.0)
    bleed: float = 12.0
    registration: tuple = (26.0, 9.0, 6.0)  # inset, radius, arm
    chrome_bands: tuple = (0.0, 42.0, 484.0, 540.0)
    artifact: str = 'deck'

    def __post_init__(self):
        if not all(math.isfinite(x) and x > 0 for x in (self.width, self.height)):
            raise ValueError('Canvas dimensions must be positive finite points')
        if self.artifact not in ('deck', 'poster'):
            raise ValueError('Unknown artifact mode')
        x0,y0,x1,y1 = self.safe
        if not (0 <= x0 < x1 <= self.width and 0 <= y0 < y1 <= self.height):
            raise ValueError('Safe bounds must be inside trim')
        if not math.isfinite(self.bleed) or self.bleed < 0:
            raise ValueError('Bleed must be finite and nonnegative')
        if len(self.registration) != 3 or any(not math.isfinite(x) or x < 0
                                              for x in self.registration):
            raise ValueError('Invalid registration geometry')
        if self.chrome_bands and not (len(self.chrome_bands) == 4 and
                0 <= self.chrome_bands[0] <= self.chrome_bands[1] <
                self.chrome_bands[2] <= self.chrome_bands[3] <= self.height):
            raise ValueError('Invalid chrome bands')
        if self.artifact == 'poster' and self.chrome_bands:
            raise ValueError('Poster cannot carry deck chrome bands')

    @property
    def aspect_ratio(self):
        return self.width / self.height

    @property
    def area(self):
        return self.width * self.height

    @property
    def bounds(self):
        return (0.0, 0.0, self.width, self.height)

    @property
    def content_bounds(self):
        return self.safe

    @property
    def bleed_bounds(self):
        b = self.bleed
        return (-b, -b, self.width+b, self.height+b)

    @property
    def attach_frame(self):
        if self.artifact == 'deck':
            return (36.0, 50.0, self.width-36.0, self.height-58.0)
        return self.safe

    @property
    def bands(self):
        return self.chrome_bands or (0.0, 0.0, self.height, self.height)

    def to_dict(self):
        return {'width': self.width, 'height': self.height, 'unit': 'pt',
                'aspect_ratio': self.aspect_ratio, 'safe': list(self.safe),
                'bleed': self.bleed, 'registration': list(self.registration),
                'chrome_bands': list(self.chrome_bands), 'artifact': self.artifact}


DECK_CANVAS = CanvasSpec()
MM = 72.0 / 25.4
POSTER_PRESETS = {
    'a3_portrait': (297*MM, 420*MM),
    'a4_portrait': (210*MM, 297*MM),
    'a2_portrait': (420*MM, 594*MM),
    '4:5': (720.0, 900.0),
    'square': (720.0, 720.0),
}


def poster_canvas(spec=None):
    spec = spec or {}
    if isinstance(spec, str):
        spec = {'preset': spec}
    if not isinstance(spec,dict):
        raise ValueError('Poster canvas must be a preset or dimensions object')
    unknown=set(spec)-{'preset','width','height','unit','ratio','safe','bleed','registration'}
    if unknown:
        raise ValueError(f'Unknown canvas fields: {sorted(unknown)}')
    preset = spec.get('preset', 'a3_portrait')
    if preset not in POSTER_PRESETS:
        raise ValueError(f'Unknown poster preset {preset!r}')
    w,h = POSTER_PRESETS[preset]
    factor = {'pt': 1, 'mm': MM, 'in': 72}.get(spec.get('unit', 'pt'))
    if factor is None:
        raise ValueError('Canvas unit must be pt, mm, or in')
    if 'width' in spec:
        w = float(spec['width']) * factor
    if 'height' in spec:
        h = float(spec['height']) * factor
    if 'ratio' in spec:
        ratio = spec['ratio']
        try:
            if isinstance(ratio,str):
                a,b = ratio.split(':')
                ratio = float(a)/float(b)
            elif isinstance(ratio,(list,tuple)):
                if len(ratio)!=2:raise ValueError('expected two ratio components')
                ratio = float(ratio[0])/float(ratio[1])
            ratio = float(ratio)
        except (ValueError,TypeError,ZeroDivisionError) as exc:
            raise ValueError(f'Invalid canvas ratio {spec["ratio"]!r}: use positive width:height') from exc
        if not math.isfinite(ratio) or ratio <= 0:
            raise ValueError('Ratio must be positive and finite')
        if 'width' in spec and 'height' in spec:
            if abs(w/h-ratio) > 1e-6:
                raise ValueError('Ratio conflicts with dimensions')
        elif 'height' in spec and 'width' not in spec:
            w = h * ratio
        else:
            h = w / ratio
    margin = min(36.0, min(w,h)*0.05)
    return CanvasSpec(w,h,tuple(spec.get('safe',(margin,margin,w-margin,h-margin))),
                      float(spec.get('bleed',24.0)),
                      tuple(spec.get('registration',(26.0,9.0,6.0))),(), 'poster')


def presentation_canvas(prs, style=None):
    style = style or {}
    artifact = style.get('artifact','deck')
    raw = style.get('canvas_spec')
    w,h = prs.slide_width.pt,prs.slide_height.pt
    if raw:
        if abs(raw['width']-w)>0.01 or abs(raw['height']-h)>0.01:
            raise ValueError('PPTX canvas differs from style metadata')
        if raw.get('artifact',artifact) != artifact:
            raise ValueError('Canvas artifact differs from style metadata')
        return CanvasSpec(w,h,tuple(raw['safe']),raw['bleed'],
                          tuple(raw['registration']),tuple(raw['chrome_bands']),artifact)
    if artifact == 'poster':
        return poster_canvas({'width':w,'height':h})
    if abs(w-DECK_CANVAS.width)<0.01 and abs(h-DECK_CANVAS.height)<0.01:
        return DECK_CANVAS
    return CanvasSpec(w,h,(4,4,w-4,h-4),12,(26,9,6),(),artifact)
