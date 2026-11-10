"""Deck-only native object writer; poster writer remains frozen."""
import typefit as tf
import riso_kit as rk

def apply_colors(plan, theme):
    from deck_paper_collage import panel_color
    ink = plan['ink_plan']
    mapping = {ink['main'][0]: theme.display_ink, ink['main'][1]: theme.inkB,
               ink['body']: theme.display_ink if theme.on_red else theme.text,
               ink['accent']: theme.accent1, ink['paper']: theme.inkA if theme.on_red else theme.paper}
    for obj in plan['objects']:
        for key in ('color', 'fill', 'line', 'background'):
            if obj.get(key) in mapping:
                obj[key] = mapping[obj[key]]
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
            for i,s in enumerate(shapes):
                s.name=f"art[{o['id']}]/{i}"
                s.rotation=o.get('rotation',0)
        elif o['kind']=='halftone':
            for i,(cx,cy,r) in enumerate(o['dots']):
                sh=rk.oval(slide,cx,cy,r*2,r*2,fill=o['fill']);sh.name=f"art[{o['id']}]/{i}"
        else:
            kind=MSO_SHAPE.CHEVRON if o['kind']=='arrow' else MSO_SHAPE.ROUNDED_RECTANGLE if o.get('slot')=='badge' else MSO_SHAPE.RECTANGLE
            sh=rk.shape(slide,kind,x,y,w,h,fill=o.get('fill'),line=o.get('line'),lw=2 if o.get('slot')=='stamp' else .75)
            sh.name=f"art[{o['id']}]"
            sh.rotation=o.get('rotation',0)
