"""Deterministic deck rhythm evidence, not an aesthetic score."""
import sys
sys.dont_write_bytecode = True
from collections import Counter

IDENTICAL_RUN_FAIL = 3
HOMOGENEOUS_RUN_FAIL = 8
REPEATED_SHARE_FAIL = 0.80
SIGNATURE_TOLERANCE = 0.035
CONTENT_WINDOW = 5


def zone(rect, canvas):
    x=(rect[0]+rect[2])/2/canvas.width
    y=(rect[1]+rect[3])/2/canvas.height
    return ('top','middle','bottom')[min(2,max(0,int(y*3)))]+'-'+(
        'left','center','right')[min(2,max(0,int(x*3)))]


def composition(texts, figures, images, canvas):
    # Text copies have already been merged. Ignore decorative imagery and chrome.
    # Font size is typographic hierarchy evidence; figure bbox is composition,
    # never interpreted as actual ink coverage.
    dominant = max(texts, key=lambda t:t['size'], default=None)
    candidates=[]
    for t in texts:
        candidates.append(('text',t['rect'],t['size']))
    for f in figures+images:
        candidates.append(('figure',f['rect'],0))
    candidates.sort(key=lambda c:(c[1][1],c[1][0],c[0]))
    max_size=max([t['size'] for t in texts],default=1) or 1
    signature=[]
    for kind,r,size in candidates:
        signature.append([kind,round(r[0]/canvas.width,3),
                          round(r[1]/canvas.height,3),
                          round((r[2]-r[0])/canvas.width,3),
                          round((r[3]-r[1])/canvas.height,3),
                          round(size/max_size,3)])
    lead=dominant['ink'] if dominant else (images[0]['rect'] if images else canvas.safe)
    return {'protagonist_zone':zone(lead,canvas),'layout_signature':signature}


def similar(a,b):
    if len(a)!=len(b):
        return False
    return all(x[0]==y[0] and all(abs(u-v)<=SIGNATURE_TOLERANCE
                                for u,v in zip(x[1:],y[1:]))
               for x,y in zip(a,b))


def check_deck(pages):
    fails,warns=[],[]
    arches=[p.get('archetype') for p in pages]
    tiers=[p['tier'] for p in pages]
    zones=[p['protagonist_zone'] for p in pages]
    signatures=[p['layout_signature'] for p in pages]
    near_run=1
    broad_run=1
    for i in range(1,len(pages)):
        same_family=(arches[i],zones[i])==(arches[i-1],zones[i-1])
        if signatures[i]==signatures[i-1]:
            warns.append(f'pages {i}-{i+1}: identical adjacent layout signature')
        near_run=near_run+1 if same_family and similar(signatures[i],signatures[i-1]) else 1
        broad_run=broad_run+1 if same_family and tiers[i]==tiers[i-1] else 1
        if near_run==IDENTICAL_RUN_FAIL:
            fails.append(f'pages {i+2-near_run}-{i+1}: near-identical archetype, zone, and skeleton run')
        if broad_run==HOMOGENEOUS_RUN_FAIL:
            fails.append(f'pages {i+2-broad_run}-{i+1}: very long homogeneous composition run')
    if len(pages)>=6:
        largest=0
        for i in range(len(pages)):
            largest=max(largest,sum(arches[i]==arches[j] and zones[i]==zones[j]
                                    and similar(signatures[i],signatures[j])
                                    for j in range(len(pages))))
        if largest/len(pages)>=REPEATED_SHARE_FAIL:
            fails.append(f'{largest}/{len(pages)} pages repeat one composition skeleton')
    mood={'cover','statement','quote','closing','divider'}
    content=[p for p in pages if p.get('archetype') not in mood]
    for start in range(max(0,len(content)-CONTENT_WINDOW+1)):
        window=content[start:start+CONTENT_WINDOW]
        counts=Counter((p['tier'],p['protagonist_zone']) for p in window)
        if max(counts.values())>=4:
            warns.append(f'content pages {window[0]["page"]}-{window[-1]["page"]}: little tier/zone variation')
    if len(pages)>=5 and len(set(tiers))==1 and len(set(zones))==1:
        warns.append('deck has no measured tier/zone breath or emphasis variation')
    return {'archetype_sequence':arches,'text_tier_sequence':tiers,
            'protagonist_zone_sequence':zones,'layout_signatures':signatures,
            'decorative_ink_balance':{'status':'not_measured',
               'reason':'Picture bounds are not reliable decorative ink coverage'},
            'fails':fails,'warns':warns,'pass':not fails}
