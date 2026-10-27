"""Single interpolated policy for source-driven composition. No dependencies."""
import math

# e, word low/high, L2 low/high, words/module, text fraction, evidence bounds
# low/high, density. Continuous values are retained until a discrete decision.
TABLE = (
    (0., 140, 320, 1, 6, 100, 1., 0., .12, 0.),
    (.25, 120, 260, 2, 6, 80, .9, .02, .22, .25),
    (.5, 100, 210, 2, 6, 64, .7, .08, .32, .5),
    (.75, 90, 170, 3, 6, 48, .5, .14, .42, .75),
    (1., 90, 140, 3, 5, 36, 1/3, .20, .50, 1.),
)

def scale(level, dialect='swiss'):
    e=float(level)
    if not math.isfinite(e) or not 0<=e<=1:raise ValueError('evidence level must be finite in [0,1]')
    lo,hi=next(((a,b) for a,b in zip(TABLE,TABLE[1:]) if a[0]<=e<=b[0]),(TABLE[-2],TABLE[-1]))
    t=(e-lo[0])/(hi[0]-lo[0]);v=[a+(b-a)*t for a,b in zip(lo,hi)]
    return dict(level=e,word_budget=v[1:3],l2_range=[math.floor(v[3]),math.ceil(v[4])],
                module_words=math.ceil(v[5]),text_fraction=v[6],presence_target=v[7:9],
                element_density_score=v[9],element_density=('sparse','normal','rich')[min(2,int(v[9]*3))],
                thesis_words=round(28-13*e),body_min=18,body_max=28,
                # Same edge threshold as the v3.7 declared but unused constraint.
                edge_limit=.14,vertical_gap_cap=32,hero_numeric_requires_evidence=True)
