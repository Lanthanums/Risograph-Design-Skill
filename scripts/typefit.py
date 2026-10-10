"""Shared measured wrapping, bounded fitting, and editable text drawing.

No copy is truncated. Requested sizes are ceilings; floors are readability
constraints. Callers allocate regions before drawing, including print offsets.
"""
import sys
sys.dont_write_bytecode = True
from dataclasses import dataclass, asdict
import math
import re
import textmetrics as tm

CLOSING = set('，。！？；：、）》】」』〕〉…,.!?;:%')
OPENING = set('（《【「『〔〈(')
TOKEN = re.compile(r"[A-Za-z0-9]+(?:['’\-][A-Za-z0-9]+)*|[^\S\n]+|[^\s]")


def source_text(value):
    if isinstance(value,(list,tuple)):
        if all(isinstance(v,(list,tuple)) and len(v)==2 and isinstance(v[1],dict) for v in value):
            return ''.join(str(v[0]) for v in value)
        return '\n'.join(source_text(v) for v in value)
    return str(value)


def _units_of(paragraph):
    units=[]
    for token in TOKEN.findall(paragraph):
        if units and (token[0] in CLOSING or units[-1][-1] in OPENING):
            units[-1]+=token
        else:units.append(token)
    return units


def lines_of(value, family, size, width, bold=False, spc=0):
    """Latin words and CJK characters, with basic opening/closing kinsoku.

    Explicit newlines, including blank paragraphs, survive. Whitespace at an
    automatic line boundary becomes the boundary; every nonspace character is
    preserved. A long indivisible Latin word fails, never becomes an ellipsis.
    """
    if width <= 0:
        raise ValueError('no positive line width')
    if not tm.resolve(family, bold):
        raise ValueError(f'font not resolvable: {family!r}')
    result = []
    for para in source_text(value).split('\n'):
        units = _units_of(para)
        current = ''
        for token in units:
            trial = current + token
            if current.strip() and not token.isspace() and tm.advance(trial, family, size, bold, spc) > width:
                result.append(current.rstrip())
                current = token.lstrip()
            else:
                current = trial
            if not current.isspace() and tm.advance(current.rstrip(), family, size, bold, spc) > width:
                raise ValueError(f'unbreakable token {current.strip()!r} needs {tm.advance(current.strip(), family, size, bold, spc):.1f}pt width')
        result.append(current.rstrip())
    return result


def wrap_runs(runs,width):
    """The same word/kinsoku units with each rich run's real face and size."""
    value=''.join(t for t,_ in runs)
    spans=[];at=0
    for text,opts in runs:
        spans.append((at,at+len(text),opts));at+=len(text)
    def slice_runs(start,end):
        return [(value[max(start,a):min(end,b)],o) for a,b,o in spans if max(start,a)<min(end,b)]
    def measured(start,end):
        return sum(tm.advance(t,o['font'],o['size'],o['bold'],o['spc']) for t,o in slice_runs(start,end))
    output=[];start=0
    for paragraph in value.split('\n'):
        line=start;position=start
        for token in _units_of(paragraph):
            end=position+len(token)
            if value[line:position].strip() and not token.isspace() and measured(line,end)>width:
                previous=position
                while previous>line and value[previous-1].isspace():previous-=1
                output.append(slice_runs(line,previous));line=position
            if not token.isspace() and measured(line,end)>width:
                raise ValueError(f'unbreakable rich-text token needs {measured(line,end):.1f}pt width')
            position=end
        output.append(slice_runs(line,position) or [('',runs[0][1])])
        start+=len(paragraph)+1
    return output


@dataclass(frozen=True)
class Fit:
    text: str
    lines: tuple
    font: str
    size: float
    bold: bool
    ls: float
    spc: float
    width: float
    height: float
    pitch: float
    offset: float = 0

    def to_dict(self):
        return asdict(self)


def fit(value, family, size, width, height, *, minimum=16, bold=False,
        ls=1.12, spc=0, role='body', block_index=None, offset=None):
    requested = float(size)
    value = source_text(value)
    minimum = float(minimum)
    if not all(math.isfinite(v) and v > 0 for v in (requested, minimum, width, height, ls)):
        raise ValueError(f'{role} block={block_index}: invalid fitting region {width}x{height}, requested={requested}, minimum={minimum}')
    if minimum > requested:
        raise ValueError(f'{role} block={block_index}: requested {requested}pt below minimum {minimum}pt in {width}x{height}pt')
    reason = 'no candidate size'
    # Re-evaluate exact font metrics at every candidate, rather than assume
    # proportional rounding. A bounded half-point search includes the floor.
    candidates = [requested - i * .5 for i in range(int((requested-minimum)/.5)+1)]
    if candidates[-1] > minimum + 1e-6:
        candidates.append(minimum)
    from riso_kit import NO_WRAP
    for chosen in candidates:
        shadow = float(offset(chosen) if callable(offset) else offset or 0)
        available = (width-shadow-NO_WRAP['pad_pt']) / NO_WRAP['slack']
        try:
            lines = lines_of(value, family, chosen, available, bold, spc)
        except ValueError as exc:
            reason = str(exc)
            continue
        pitch = tm.line_height(family, chosen, bold, ls)
        needed = len(lines) * pitch + shadow
        if needed <= height + 1e-6:
            measured = max((tm.advance(t, family, chosen, bold, spc) for t in lines), default=0)
            return Fit(str(value), tuple(lines), family, chosen, bold, ls, spc, measured, needed, pitch, shadow)
        reason = f'{len(lines)} measured lines need {needed:.1f}pt height'
    raise ValueError(f'{role} block={block_index}: cannot fit region {width:.1f}x{height:.1f}pt; requested {requested:g}pt, minimum {minimum:g}pt; {reason}. Reallocate content or change the layout.')


def draw(slide, x, y, width, fitted, theme, *, role='body', block_index=None,
         display=False, alignment='l', color=None, offsets=None):
    import riso_kit as rk
    start = len(slide.shapes)
    face=tm.font(fitted.font,fitted.size,fitted.bold)
    left_pad=max(0,-min((face.getbbox(line)[0] for line in fitted.lines if line),default=0))+.5
    x+=left_pad
    width-=left_pad
    if display:
        for i, line in enumerate(fitted.lines):
            rk.stack(slide, x, y+i*fitted.pitch, width-fitted.offset,
                     fitted.pitch, [(line, fitted.font, fitted.size, fitted.bold)],
                     theme, front=color or theme.front_ink, back=theme.back_ink,
                     offsets=offsets, align=alignment, ls=fitted.ls,
                     spc=fitted.spc, autofit=False)
    else:
        rk.text(slide, x, y, width, fitted.height,
                [dict(runs=[(t,{})], font=fitted.font, size=fitted.size,
                      bold=fitted.bold, ls=fitted.ls, spc=fitted.spc,
                      color=color or theme.front_ink, align=alignment) for t in fitted.lines],
                wrap=False, fit_nowrap=False)
    shapes = list(slide.shapes)[start:]
    for i, sh in enumerate(shapes):
        # rk.stack keeps its intentional layer marker after this role prefix.
        sh.name = f'{role}[{block_index if block_index is not None else ""}]/{i}/' + sh.name
    return shapes
