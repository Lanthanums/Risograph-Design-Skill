#!/usr/bin/env python3
"""place_decor.py — the geometric placement engine (anti-clutter rules A–F).

This module replaces "find the gaps and fill them" with a strict geometric
protocol. Decoration is placed only AFTER all copy (including chrome text)
has been typeset and measured with real font metrics, and every piece must
earn its place:

  rule C  the page is a 0.5in grid; copy ink inflated by 0.35in and the
          chrome zones are occupied. A decoration may only be:
            a. flush to an edge or corner (it may bleed off the page), or
            b. bound to a text block (under it, off its corner, pointing
               at it), one protection gap away, or
            c. the single large protagonist element of a T0 page.
          Nothing floats alone in the middle of nowhere.
  rule A  one protagonist per page. When the typography is the protagonist,
          no second large element appears; secondary focus at most one, at
          least 3:1 smaller; everything else at most 1/6 of the protagonist.
  rule B  budgets are CEILINGS that shrink as the copy load grows (tiers
          T0–T3). There is no floor: an empty-handed page is a pass.
  rule D  decoration travels in groups: 2–4 elements of one dialect on a
          shared alignment axis, in one ink, with at least 2.5:1 size
          contrast, rotation within ±6° (one member may break the angle).
  rule E  chrome zones are forbidden ground, and chrome counts into the
          decoration budget.
  rule F  all elements on a page come from the primary dialect; at most one
          from the secondary.

Every committed element carries a function tag — anchor / emphasis / rhythm /
metaphor / component — and the quiet-zone invariant is re-checked after each
placement: T0/T1 pages keep a largest empty rectangle of at least 18% of the
page, T2/T3 at least 10%.
"""
import sys
sys.dont_write_bytecode = True
import math

import elements as E
import layout as lay
from canvas import DECK_CANVAS

PAGE_AREA = lay.PAGE_W * lay.PAGE_H

# Rule B — decoration ceilings by copy load (words; CJK chars count /1.6).
#   tier, max words, area cap, group cap, micro cap, quiet floor
TEXT_TIERS = {
    "T0": {"hi": 12, "area": 0.30, "groups": 2, "micro": 3, "quiet": 0.18},
    "T1": {"hi": 35, "area": 0.22, "groups": 2, "micro": 3, "quiet": 0.18},
    "T2": {"hi": 70, "area": 0.14, "groups": 1, "micro": 2, "quiet": 0.10},
    "T3": {"hi": 10 ** 9, "area": 0.08, "groups": 1, "micro": 1,
           "quiet": 0.10},
}

GRID = 36.0               # 0.5in grid
TEXT_PAD = 25.2           # copy ink + 0.35in is occupied ground
ATTACH_GAP = (11.0, 16.0)
ATTACH_FRAME = DECK_CANVAS.attach_frame
CHROME_BANDS = DECK_CANVAS.bands

FUNCTIONS = ("anchor", "emphasis", "rhythm", "metaphor", "component")


def tier_of(words):
    for name in ("T0", "T1", "T2", "T3"):
        if words <= TEXT_TIERS[name]["hi"]:
            return name
    return "T3"


def word_count(text):
    import re
    latin = len(re.findall(r"[A-Za-z0-9]+(?:[’'\-][A-Za-z0-9]+)*", text or ""))
    cjk = sum(1 for ch in (text or "") if ord(ch) > 0x2E80)
    return latin + cjk / 1.6


def _rot_bbox(rect, deg):
    x0, y0, x1, y1 = rect
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    w, h = (x1 - x0) / 2.0, (y1 - y0) / 2.0
    t = math.radians(abs(deg))
    c, s = abs(math.cos(t)), abs(math.sin(t))
    return (cx - (w * c + h * s), cy - (w * s + h * c),
            cx + (w * c + h * s), cy + (w * s + h * c))


def _occupied_cells(occupied, canvas=None):
    """Boolean grid over the page: True = free."""
    canvas = canvas or DECK_CANVAS
    cols = max(1, int(canvas.width // GRID))
    rows = max(1, int(canvas.height // GRID))
    grid = [[True] * cols for _ in range(rows)]
    for r in occupied:
        x0, y0, x1, y1 = r
        c0 = max(0, int(x0 // GRID))
        c1 = min(cols - 1, int(max(x0, x1 - 1e-6) // GRID))
        r0 = max(0, int(y0 // GRID))
        r1 = min(rows - 1, int(max(y0, y1 - 1e-6) // GRID))
        for rr in range(r0, r1 + 1):
            for cc in range(c0, c1 + 1):
                grid[rr][cc] = False
    return grid


def largest_quiet(occupied, canvas=None):
    """Largest empty rectangle (page share) given occupied rects."""
    canvas = canvas or DECK_CANVAS
    grid = _occupied_cells(occupied, canvas)
    rows, cols = len(grid), len(grid[0])
    heights = [0] * cols
    best = (0, None)
    for rr in range(rows):
        for cc in range(cols):
            heights[cc] = heights[cc] + 1 if grid[rr][cc] else 0
        stack = []
        for cc in range(cols + 1):
            h = heights[cc] if cc < cols else 0
            start = cc
            while stack and stack[-1][1] > h:
                idx, hh = stack.pop()
                start = idx
                area = hh * (cc - idx)
                if area > best[0]:
                    best = (area, (idx * GRID, (rr - hh + 1) * GRID,
                                   cc * GRID, (rr + 1) * GRID))
            stack.append((start, h))
    return best[0] * GRID * GRID / canvas.area, best[1]


class Placer:
    """One page's placement session. Construct with the measured copy and the
    chrome zones; ask for attached pieces, one group, or a T0 hero."""

    def __init__(self, text_items, scenario, primary, secondary, rnd,
                 tier=None, words=None, area_cap_extra=0.0, taken_area=0.0,
                 mood=False, canvas=None):
        """text_items: [{"rect": (x0,y0,x1,y1), "text": str, "size": pt}]."""
        self.rnd = rnd
        self.canvas = canvas or DECK_CANVAS
        self.page_area = self.canvas.area
        self.mood = mood
        if words is None:
            words = sum(word_count(it.get("text", "")) for it in text_items)
        self.tier = tier or tier_of(words)
        caps = TEXT_TIERS[self.tier]
        self.area_cap = max(0.0, caps["area"] - area_cap_extra)
        self.group_cap = caps["groups"]
        self.micro_cap = caps["micro"]
        self.quiet_min = caps["quiet"]
        self.words = words
        self.items = [dict(it) for it in text_items]
        self.rects = [it["rect"] for it in self.items]
        # occupied ground has two resolutions: copy ink + 0.35in marks the
        # grid off-limits for INDEPENDENT placement (rule C2); pieces bound
        # to a text block (rule C-b) live closer — they respect the ink plus
        # a small protection gap, which is what "attached" means
        self.base_occupied = [lay.inflate(r, TEXT_PAD) for r in self.rects]
        self.ink_occupied = [lay.inflate(r, lay.TEXT_PROTECTION)
                             for r in self.rects]
        self.placed = []
        self.used_names = {}
        self.taken_area = taken_area
        self.precise = False            # caller may set for calm rotations
        self._scenario = scenario
        self._pools = self._split_pools(primary, secondary)

    # ---------------------------------------------------------------- pools
    @staticmethod
    def _split_pools(primary, secondary):
        """Rule F: primary pool and a strictly rationed secondary pool."""
        import compose
        full = compose.element_pool(primary, secondary)
        prim_names = {n for _r, n in compose.element_pool(primary, primary)}
        main = [(r, n) for r, n in full if n in prim_names]
        side = [(r, n) for r, n in full if n not in prim_names]
        return {"main": main, "side": side}

    # ------------------------------------------------------------ primitives
    def _occupied(self, extra=None, tight=False):
        occ = list(self.ink_occupied if tight else self.base_occupied)
        occ += [_rot_bbox(o["rect"], abs(o.get("rot", 0)) + 0.5)
                for o in self.placed]
        if extra:
            occ += extra
        return occ

    def quiet_now(self, extra=None):
        return largest_quiet(self._occupied(extra), self.canvas)[0]

    def _legal(self, rect, rot, bleed=False, tight=False):
        b = self.canvas.bleed if bleed or self.canvas.artifact == "poster" else 6
        frame = (-b, -b, self.canvas.width + b, self.canvas.height + b)
        if not lay.inside(rect, frame):
            return False
        rb = _rot_bbox(rect, max(1.0, abs(rot) + 0.5))
        if any(lay.intersection(rb, o) for o in self._occupied(tight=tight)):
            return False
        return True

    def _rot(self, calm=False):
        span = 3.0 if calm else 7.0
        return self.rnd.uniform(-span, span) * (0.4 if self.precise else 1.0)

    def _pick(self, roles, pool="main", exclude=()):
        cands = [n for r, n in self._pools[pool]
                 if r in roles and n not in exclude]
        if not cands:
            cands = [n for _r, n in self._pools["main"] if n not in exclude]
        if not cands:                   # pool exhausted: repeats allowed
            cands = [n for r, n in self._pools[pool] if r in roles] or \
                    [n for _r, n in self._pools["main"]]
        if not cands:
            return None
        for _ in range(16):
            name = cands[self.rnd.randrange(len(cands))]
            if self.used_names.get(name, 0) < 2 and name in E.REGISTRY:
                return name
        return None

    def _size(self, name, scale, element_scale=1.0):
        lo_w, hi_w, lo_h, hi_h = E.REGISTRY[name]["size"]
        s = element_scale * scale
        return (self.rnd.uniform(lo_w, hi_w) * s,
                self.rnd.uniform(lo_h, hi_h) * s)

    def commit(self, name, role, rect, rot, placement, function, group=None,
               ink="A", tight=False):
        """Every element MUST carry a function tag; untagged pieces are
        refused here, which is what keeps meaningless blocks off the page."""
        if function not in FUNCTIONS:
            return False
        if not self._legal(rect, rot, tight=tight):
            return False
        # quiet-zone invariant: placing this piece must not eat the quiet
        if self.quiet_now(extra=[_rot_bbox(rect, abs(rot) + 0.5)]) \
                < self.quiet_min - 1e-9 and (placement != "hero" or
                                            self.canvas.artifact == "poster"):
            return False
        budget = self.area_cap * self.page_area - self.taken_area
        used = sum(lay.area(o["rect"]) for o in self.placed)
        if used + lay.area(rect) > budget:
            return False
        item = {"name": name, "role": role, "rect": rect, "rot": rot,
                "w": rect[2] - rect[0], "h": rect[3] - rect[1],
                "placement": placement, "function": function, "ink": ink}
        if group:
            item["group"] = group
        self.placed.append(item)
        self.used_names[name] = self.used_names.get(name, 0) + 1
        return True

    # ---------------------------------------------------------------- anchors
    def anchors(self):
        """The pieces of copy a decoration may bind to, biggest first."""
        out, seen = [], set()
        typed = sorted((it for it in self.items if it.get("size")),
                       key=lambda it: -it["size"])
        for it in typed:
            x0, y0, x1, y1 = it["rect"]
            cy = (y0 + y1) / 2.0
            if self.canvas.artifact == "deck" and (cy < 50 or cy > 478):
                continue
            key = (round(x0 / 8), round(y0 / 8))
            if key in seen:
                continue
            seen.add(key)
            out.append({"rect": it["rect"], "text": (it.get("text") or "")[:24],
                        "size": it["size"],
                        "kind": ("monument" if it["size"] >= 80 else
                                 "title" if it["size"] >= 22 else "label")})
            if len(out) >= 3:
                break
        return out

    # ------------------------------------------------------------- passes
    def place_composition(self, region, preferred=None):
        """Place one substantial graphic and a related accent in a planned band.

        It remains subordinate to display type, uses the same legal/quiet/area
        gates as every other element, and never shrinks into a token speck.
        """
        pool=[n for role,n in self._pools['main'] if role=='hero']
        if preferred:
            if preferred not in {n for _,n in self._pools['main']}:
                raise ValueError('graphic_element must belong to the allowed primary dialect pool')
            pool=[preferred]
        names=list(dict.fromkeys(pool))
        self.rnd.shuffle(names)
        x0,y0,x1,y1=region
        rw,rh=x1-x0,y1-y0
        for name in names[:8]:
            lw,hw,lh,hh=E.REGISTRY[name]['size']
            aspect=(lw+hw)/max(lh+hh,1)
            target=min(self.page_area*.065,self.area_cap*self.page_area*.55,rw*rh*.65)
            w=math.sqrt(target*aspect);h=w/aspect
            factor=min(1,rw*.72/w,rh*.88/h)
            w*=factor;h*=factor
            if w*h<self.page_area*.015:
                continue
            # Align with a content edge; a supporting shape shares the baseline.
            for x in (x0+4,x1-w-4):
                y=y0+(rh-h)/2
                if self.commit(name,'support',(x,y,x+w,y+h),0,'grouped','rhythm',group='composition'):
                    small=self._pick(('support','micro'),exclude=(name,))
                    if small:
                        sw,sh=self._size(small,.55)
                        k=min(1,math.sqrt((w*h/3)/max(sw*sh,1)),rh*.45/sh)
                        sw*=k;sh*=k
                        sx=x+w+18 if x<x0+rw/2 else x-18-sw
                        sr=(sx,y+h-sh,sx+sw,y+h)
                        if lay.inside(sr,region):
                            self.commit(small,'micro',sr,0,'grouped','rhythm',group='composition')
                    return 1
        if preferred:
            raise ValueError('graphic_element cannot fit its measured band under geometry limits')
        return 0

    def attach(self, max_count=2, element_scale=1.0):
        """Pass 1: bind small pieces to anchors — under a title, off a big
        number's corner. Function: emphasis (band-like) or anchor (corner)."""
        placed = 0
        used = set()
        for anchor in self.anchors()[:max_count]:
            # one element per name per page: twin pieces with identical
            # wording read as a printing glitch, not as misregistration
            name = self._pick(("support", "micro"), exclude=used)
            if not name:
                break
            used.add(name)
            w, h = self._size(name, 0.62, element_scale)
            ax0, ay0, ax1, ay1 = anchor["rect"]
            gap = self.rnd.uniform(*ATTACH_GAP)
            band = h / max(w, 1e-6) <= 0.45
            if band:
                w = min(w, (ax1 - ax0) * 1.05 + 24)
                cands = [(ax0, ay1 + gap), (ax0, ay0 - gap - h),
                         (ax1 + gap, (ay0 + ay1 - h) / 2.0)]
                func = "emphasis"
            else:
                cands = [(ax1 + gap * 0.7, ay0 - gap * 0.7 - h),
                         (ax1 + gap, (ay0 + ay1 - h) / 2.0),
                         (ax0 - gap - w, (ay0 + ay1 - h) / 2.0),
                         (ax0, ay1 + gap)]
                func = "anchor"
            rot = self._rot(calm=True)
            for x, y in cands:
                rect = (x, y, x + w, y + h)
                if not lay.inside(rect, self.canvas.attach_frame):
                    continue
                if self.commit(name, "support", rect, rot, "attached", func,
                               tight=True):
                    self.placed[-1]["anchor"] = anchor["text"]
                    placed += 1
                    break
        return placed

    def place_group(self, element_scale=1.0):
        """Pass 2: ONE group of 2–4 same-dialect elements on a shared axis,
        in one ink, ≥2.5:1 size contrast — placed as a unit on an edge or in
        the largest gap. This is the fig-B logic: grouped, aligned, small,
        tucked into quiet space. Elements are not hardcoded; the dialect pool
        decides."""
        if len([o for o in self.placed if o.get("group")]) >= self.group_cap:
            return 0
        big = self._pick(("support",), exclude=tuple(self.used_names))
        small = self._pick(("micro",),
                           exclude=tuple(self.used_names) + (big,))
        if not big:
            return 0
        bw, bh = self._size(big, 0.55, element_scale)
        members = [(big, bw, bh, "support")]
        if small and small != big:
            sw, sh = self._size(small, 0.5, element_scale)
            # rule D: at least 2.5:1 between the group's largest and smallest
            # (built with margin so floating point never straddles the line)
            k = max(1.0, math.sqrt((sw * sh) / max(bw * bh / 2.6, 1e-6)))
            members.append((small, sw / k, sh / k, "micro"))
        rot = self._rot(calm=True)      # one shared angle, within ±6°
        gap = self.rnd.uniform(10.0, 18.0)
        total_w = sum(m[1] for m in members) + gap * (len(members) - 1)
        max_h = max(m[2] for m in members)

        # candidate homes: corners of the largest free rectangles, preferring
        # spots flush with a page edge (rule C-a)
        boxes = self._free_boxes()
        gid = f"g{len(self.placed)}"
        ink = "A"
        for box in boxes[:8]:
            bw_box, bh_box = box[2] - box[0], box[3] - box[1]
            if total_w > bw_box or max_h > bh_box:
                continue
            # bottom-align the members on a shared axis, hug the corner of the
            # box that is nearest a page corner
            corners = [(box[0], box[3] - max_h), (box[2] - total_w, box[3] - max_h),
                       (box[0], box[1]), (box[2] - total_w, box[1])]
            x, y = min(corners, key=lambda c: min(c[0], self.canvas.width - c[0] - total_w,
                                                  c[1], self.canvas.height - c[1] - max_h))
            cx = x
            trial = []
            ok = True
            for name, w, h, role in members:
                rect = (cx, y + (max_h - h), cx + w, y + max_h)
                if not self._legal(rect, rot):
                    ok = False
                    break
                trial.append((name, role, rect))
                cx += w + gap
            if not ok:
                continue
            # the whole group must leave the quiet zone standing
            extra = [_rot_bbox(t[2], abs(rot) + 0.5) for t in trial]
            if self.quiet_now(extra=extra) < self.quiet_min - 1e-9:
                continue
            for name, role, rect in trial:
                if self.commit(name, role, rect, rot, "grouped", "rhythm",
                               group=gid, ink=ink):
                    pass
            return len(trial)
        return 0

    def place_hero(self, element_scale=1.0, min_room=0.12, room_clip=0.62):
        """Pass 3: the single large protagonist element — T0 pages only, and
        only when a genuinely large quiet room exists. Function: metaphor."""
        if self.tier != "T0":
            return 0                    # typography is the protagonist (rule A)
        if any(a["kind"] == "monument" for a in self.anchors()):
            return 0                    # monumental type already leads the page
        share, room = self.quiet_now(), None
        _share, room = largest_quiet(self._occupied(), self.canvas)
        if _share < min_room * (0.55 if self.mood else 1.0):
            return 0
        name = self._pick(("hero",))
        if not name:
            return 0
        lo_w, hi_w, lo_h, hi_h = E.REGISTRY[name]["size"]
        ar = ((lo_h + hi_h) / 2.0) / max(1e-6, (lo_w + hi_w) / 2.0)
        budget_left = (self.area_cap * self.page_area - self.taken_area
                       - sum(lay.area(o["rect"]) for o in self.placed)
                       - 0.05 * self.page_area)
        sizes = (0.18, 0.28) if self.canvas.artifact == "poster" else (0.10, 0.18)
        target = min(self.rnd.uniform(*sizes) * self.page_area, budget_left)
        if target < 0.04 * self.page_area:
            return 0
        w = math.sqrt(max(900.0, target / max(ar, 1e-3)))
        h = w * ar
        rw, rh = room[2] - room[0], room[3] - room[1]
        k = min(1.0, rw / max(w, 1e-6), rh / max(h, 1e-6))
        w, h = w * k, h * k
        cap = math.sqrt(room_clip * rw * rh / max(w * h, 1e-6))
        if cap < 1.0:
            w, h = w * cap, h * cap
        rot = self._rot()
        for attempt in range(24):
            kk = 0.92 ** (attempt // 3)
            ww, hh = w * kk, h * kk
            if ww < 40 or hh < 32:
                break
            x = self.rnd.uniform(room[0], max(room[0], room[2] - ww))
            y = self.rnd.uniform(room[1], max(room[1], room[3] - hh))
            rect = (x, y, x + ww, y + hh)
            if self.commit(name, "hero", rect, rot, "hero", "metaphor"):
                return 1
        return 0

    def _free_boxes(self):
        import compose
        extra = [o["rect"] for o in self.placed]
        return compose.free_rects(self.rects + extra, TEXT_PAD, canvas=self.canvas)
