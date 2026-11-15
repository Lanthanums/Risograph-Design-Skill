"""Deck-only native object writer; poster writer remains frozen."""
import typefit as tf
import riso_kit as rk

def _turn(shape, obj):
    """Rotate a native shape about the centre of the paper it sits on."""
    angle = obj.get('rotation', 0)
    pivot = obj.get('pivot')
    if not angle:
        return
    if pivot:
        import math
        from pptx.util import Pt
        cx, cy = shape.left.pt + shape.width.pt / 2, shape.top.pt + shape.height.pt / 2
        c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
        nx = pivot[0] + (cx - pivot[0]) * c - (cy - pivot[1]) * s
        ny = pivot[1] + (cx - pivot[0]) * s + (cy - pivot[1]) * c
        shape.left, shape.top = Pt(nx - shape.width.pt / 2), Pt(ny - shape.height.pt / 2)
    shape.rotation = angle


def face_color(theme, stock):
    import deck_paper_stock as ps
    tokens = dict(paper=theme.paper, ink=theme.ink)
    return ps.to_hex(ps.stock_colors(tokens).get(stock, ps.stock_colors(tokens)['bone']))


def apply_colors(plan, theme):
    from deck_paper_collage import panel_color
    ink = plan['ink_plan']
    # Copy on a reading face is printed in the page inks, on any page field.
    printed = {ink['main'][0]: theme.inkA, ink['main'][1]: theme.inkB, ink['body']: theme.text,
               ink['accent']: theme.accent1}
    for obj in plan['objects']:
        if not obj.get('on_face') or obj['kind'] == 'paper':
            continue
        stock = face_color(theme, obj.get('face_stock', 'bone'))
        for key in ('color', 'fill', 'line'):
            if obj.get(key) in printed:
                obj[key] = printed[obj[key]]
            elif obj.get(key) == ink['paper']:
                obj[key] = stock
        for item in obj.get('spans', ()):
            if item.get('color') in printed:
                item['color'] = printed[item['color']]
        if 'background' in obj:
            obj['background'] = stock
    mapping = {ink['main'][0]: theme.display_ink, ink['main'][1]: theme.inkB,
               ink['body']: theme.display_ink if theme.on_red else theme.text,
               ink['accent']: theme.accent1, ink['paper']: theme.inkA if theme.on_red else theme.paper}
    for obj in plan['objects']:
        for key in ('color', 'fill', 'line', 'background'):
            if obj.get(key) in mapping:
                obj[key] = mapping[obj[key]]
        for item in obj.get('spans', ()):
            if item.get('color') in mapping:
                item['color'] = mapping[item['color']]
        material = obj.get('material', '')
        if material.startswith('list-paper-'):
            obj['fill'] = panel_color(theme, material, obj['paper_style'])
        if obj.get('paper_panel'):
            obj['color'] = theme.text
            obj['background'] = panel_color(theme, 'list-paper-face', obj['paper_style'])
        for key in ('color', 'fill', 'line'):
            if obj.get(key) and obj[key] not in theme.t.values():
                theme.t[f'evidence-{len(theme.t)}'] = obj[key]


def draw(slide,p,theme):
    """Native vectors and text. Multiply intersections remain editable objects."""
    from pptx.enum.shapes import MSO_SHAPE
    for o in p['objects']:
        x,y,x1,y1=o['rect'];w=x1-x;h=y1-y
        if o['kind']=='paper':
            continue  # printed on the page plate
        if o['kind']=='path':
            from native_vectors import native_path
            shape = native_path(slide,o)
            if o.get('stroke_opacity') is not None:
                from pptx.oxml.ns import qn
                color = shape._element.spPr.find(
                    f"{qn('a:ln')}/{qn('a:solidFill')}/{qn('a:srgbClr')}")
                color.append(color.makeelement(qn('a:alpha'), {
                    'val': str(int(o['stroke_opacity'] * 1000))}))
        elif o['kind']=='text':
            f=tf.Fit(**dict(o['fit'],lines=tuple(o['fit']['lines'])))
            if o.get('type_plates'):
                from deck_ink_render import draw as draw_plates
                draw_plates(slide, x, y, w, f, theme, o['type_plates'],
                            f"art[{o['id']}]", color=o['color'])
                continue
            shapes=tf.draw(slide,x,y,w,f,theme,color=o['color'],role='poster-art',
                           alignment=o.get('alignment','l'))
            if p.get('version') in ('3.5','3.6','3.7','3.8'):
                # The fit records an absolute measured pitch. Relative spacing
                # is renderer/font dependent and accumulated line-position
                # drift in long CJK paragraphs. Preserve the measured pitch in
                # native OOXML instead of weakening raster legibility checks.
                from pptx.util import Pt
                for shape in shapes:
                    for paragraph in shape.text_frame.paragraphs:
                        paragraph.line_spacing=Pt(f.pitch)
            if o.get('spans') and shapes:
                from deck_sheet_type import apply_spans
                apply_spans(shapes[0], o, theme)
            for i,s in enumerate(shapes):
                s.name=f"art[{o['id']}]/{i}"
                _turn(s, o)
        elif o['kind']=='halftone':
            for i,(cx,cy,r) in enumerate(o['dots']):
                sh=rk.oval(slide,cx,cy,r*2,r*2,fill=o['fill']);sh.name=f"art[{o['id']}]/{i}"
        else:
            kind=MSO_SHAPE.CHEVRON if o['kind']=='arrow' else MSO_SHAPE.ROUNDED_RECTANGLE if o.get('slot')=='badge' else MSO_SHAPE.RECTANGLE
            sh=rk.shape(slide,kind,x,y,w,h,fill=o.get('fill'),line=o.get('line'),lw=2 if o.get('slot')=='stamp' else .75)
            sh.name=f"art[{o['id']}]"
            _turn(sh, o)
