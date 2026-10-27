"""Bar grid, bundles and tie layout for CEDA columns (units: mm inside this module, bars returned in cm).

Rules (agreed with the CEDA designer, Rev.1 + Oct 2026):
  * One bar grid for the whole column (same positions in every story band); c/c 125-150 mm (CEDA practice).
    A face where no count gives 125-150 uses the count closest to the range with clear <= 150 mm (ACI 25.7.2.3)
    and clear >= code minimum (ACI 25.2.3) – reported as a note.
  * Bar build-up ladder: singles of increasing size, then bundles of the largest size added only at tie corners,
    group by group: column corners first, then hoop corners from the outside inward; 1->2 for every group, then ->3,
    then ->4 (ACI 25.6.1.1 max 4). A step is skipped if it breaks the clear spacing (ACI 25.2.3 / 25.6.1.6).
    Going up the building the order is reversed: remove bundles first, then reduce the bar size.
  * Ties (ACI 25.7.2.3): every corner and alternate bar supported, no unsupported bar more than 150 mm clear from a
    supported bar.  Symmetric pattern from the centre outward (CEDA sketch): even count -> centre pair in one hoop,
    then every second bar to the corners; odd count -> every second bar from the corners.  Supported intermediate
    positions are paired into closed hoops outside-in; a leftover single gets a crosstie.
  * Bundles: 2 bars stacked inward (width along face = db); 3 bars L/triangle and 4 bars square (width = 2 db).
"""
import math

DAGG = 25.0          # mm, assumed maximum aggregate size (4/3 dagg = 33 mm) – state in report


def clear_req(db, k):
    deq = db * math.sqrt(k)                          # ACI 25.6.1.6
    return max(1.5 * deq, 40.0, 4.0 / 3.0 * DAGG)    # ACI 25.2.3


def bw(k, db):
    return db if k <= 2 else 2 * db


# ------------------------------------------------------------------------------------------------ grid
SMALL_FACE = ((200.0, 2), (540.0, 3), (660.0, 4))   # CEDA (19 Oct 2026): face <= 200 mm 2 bars, <= 540 3 bars, <= 660 4 bars


def face_count(span, db, cc_min=125.0, cc_max=150.0, face_dim=None, small=SMALL_FACE):
    """number of positions (incl. both corners) on a face whose corner-to-corner span is `span` (mm).
    CEDA small-face rule first (face dimension <= 660 mm: fixed count by the table above), otherwise c/c 125-150."""
    if face_dim is not None:
        for lim, n in small:
            if face_dim <= lim + 1e-6:
                return n, (span / (n - 1) if n > 1 else 0.0), ''
    if span <= 0:
        return 2, 0.0, ''
    best = None
    for n in range(2, 200):
        sp = span / (n - 1)
        if cc_min - 1e-6 <= sp <= cc_max + 1e-6:
            return n, sp, ''                         # fewest bars inside the range
    # no count inside the range -> closest count with clear <= 150 and >= code minimum
    for n in range(2, 200):
        sp = span / (n - 1)
        clr = sp - db
        if clr <= 150.0 + 1e-6 and clr >= clear_req(db, 1) - 1e-6:
            dev = min(abs(sp - cc_min), abs(sp - cc_max))
            if best is None or dev < best[2]:
                best = (n, sp, dev)
    if best:
        return best[0], best[1], f'c/c {best[1]:.0f} mm outside 125-150 (no count fits); clear {best[1]-db:.0f} mm <= 150'
    return 2, span, 'face too short for intermediate bars'


class Grid:
    """Rectangular grid. Section axes: x along b, y along h (mm, origin at the lower-left corner)."""

    def __init__(self, b, h, cover=40.0, tie=12.0, db_ref=32.0, cc=(125.0, 150.0), shape='rect', small=SMALL_FACE):
        self.b, self.h, self.cover, self.tie, self.db_ref, self.shape = b, h, cover, tie, db_ref, shape
        self.notes = []
        self.interior = False      # v1.3.2: inner bars at the crossings of the inner hoops (CEDA pattern, last resort)
        e = cover + tie + db_ref / 2
        if shape == 'circ':
            R = b / 2 - e
            circ = 2 * math.pi * R
            n = max(6, math.ceil(circ / cc[1]))
            if circ / n < cc[0]:
                self.notes.append(f'circular: c/c {circ/n:.0f} mm < 125')
            self.n = n
            return
        self.nh, self.sp_h, nt1 = face_count(h - 2 * e, db_ref, *cc, face_dim=h, small=small)   # positions along y on the x-faces
        self.nb, self.sp_b, nt2 = face_count(b - 2 * e, db_ref, *cc, face_dim=b, small=small)   # positions along x on the y-faces
        for nt, f in ((nt1, f'faces parallel to h ({h:.0f})'), (nt2, f'faces parallel to b ({b:.0f})')):
            if nt:
                self.notes.append(f'{f}: {nt}')

    # positions for a given bar size (e depends on db) -------------------------------------------------
    def positions(self, db):
        P, e = self._perim(db)
        if self.interior and self.shape != 'circ':
            P = P + self.inner(db)
        return P, e

    def inner(self, db):
        """CEDA pattern (paattern.dxf, 20 Oct 2026): one bar at every crossing of the legs of the inner hoops
        (vertical hoops x hoop legs of the horizontal hoops), perimeter excluded."""
        T = ties(self, db)
        P0, e = self._perim(db)
        xs = sorted(set(round(x, 3) for pr in T['hoops_b'] for x in pr))
        ys = sorted(set(round(y, 3) for pr in T['hoops_h'] for y in pr))
        out = []
        for i, x in enumerate(xs):
            for j, y in enumerate(ys):
                if min(abs(x - e), abs(x - (self.b - e)), abs(y - e), abs(y - (self.h - e))) < 1e-6:
                    continue
                out.append(dict(x=x, y=y, face='in', idx=len(out), n=(0.0, 0.0), t=(1.0, 0.0), corner=False))
        return out

    def _perim(self, db):
        e = self.cover + self.tie + db / 2
        P = []
        if self.shape == 'circ':
            R = self.b / 2 - e
            for i in range(self.n):
                t = 2 * math.pi * i / self.n
                ux, uy = math.cos(t), math.sin(t)
                P.append(dict(x=self.b / 2 + R * ux, y=self.b / 2 + R * uy, face='c', idx=i, n=(-ux, -uy), t=(-uy, ux), grp=0))
            return P, e
        b, h = self.b, self.h
        sh = (h - 2 * e) / (self.nh - 1)
        sb = (b - 2 * e) / (self.nb - 1)
        for side, x, nx in (('L', e, 1), ('R', b - e, -1)):
            for j in range(self.nh):
                y = e + j * sh
                corner = j in (0, self.nh - 1)
                if corner:
                    ny = 1 if j == 0 else -1
                    n = (nx / math.sqrt(2), ny / math.sqrt(2))
                else:
                    n = (nx, 0.0)
                P.append(dict(x=x, y=y, face='h' + side, idx=j, n=n, t=(-n[1], n[0]), corner=corner))
        for side, y, ny in (('B', e, 1), ('T', h - e, -1)):
            for i in range(1, self.nb - 1):
                P.append(dict(x=e + i * sb, y=y, face='b' + side, idx=i, n=(0.0, ny), t=(-ny, 0.0), corner=False))
        return P, e


# ------------------------------------------------------------------------------------------------ ties
def _support_pattern(m):
    """indices supported along a face of m positions (0 and m-1 are corners)."""
    if m <= 2:
        return [0, m - 1][:m]
    if m % 2 == 1:
        return list(range(0, m, 2))                   # every second bar from the corners (symmetric)
    c0, c1 = m // 2 - 1, m // 2                       # centre pair, then every second bar outward
    left = list(range(c0, 0, -2))
    sup = {0, m - 1, *left, *[m - 1 - i for i in left], c1}
    # fill a gap of two unsupported bars next to a corner
    for i in range(1, m - 1):
        if i not in sup and (i + 1) not in sup and i + 1 <= m - 1:
            sup.add(i)
    return sorted(sup)


def _pairs(m, sup):
    """pair supported interior positions into closed hoops, symmetric and outside-in.
    4+ left: pair the outer two at each end; 3 left: one hoop over the outer two + crosstie at the middle;
    2 left: one hoop; 1 left: crosstie."""
    rem = [i for i in sup if 0 < i < m - 1]
    hoops, cross = [], []
    while len(rem) >= 4:
        hoops.append((rem[0], rem[1])); hoops.append((rem[-2], rem[-1]))
        rem = rem[2:-2]
    if len(rem) == 3:
        hoops.append((rem[0], rem[2])); cross.append(rem[1])
    elif len(rem) == 2:
        hoops.append((rem[0], rem[1]))
    elif len(rem) == 1:
        cross.append(rem[0])
    return hoops, cross


def check_support(coords, sup, db, limit=150.0):
    """True if every unsupported bar is next to supported bars and within `limit` clear (ACI 25.7.2.3)."""
    m = len(coords)
    for i in range(1, m - 1):
        if i in sup:
            continue
        if (i - 1) not in sup or (i + 1) not in sup:
            return False
        if min(coords[i] - coords[i - 1], coords[i + 1] - coords[i]) - db > limit + 1e-6:
            return False
    return True


def ties(grid, db):
    """closed hoops and crossties for the rectangular grid (independent of bundles)."""
    if grid.shape == 'circ':
        return dict(hoops_h=[], hoops_b=[], cross_h=[], cross_b=[], nset=1, ncross=0, sup_h=[], sup_b=[], ok=True)
    P, e = grid._perim(db)
    ys = sorted(set(round(p['y'], 3) for p in P if p['face'] == 'hL'))
    xs = [e] + sorted(set(round(p['x'], 3) for p in P if p['face'] == 'bB')) + [grid.b - e]
    out = {}
    ok = True
    for key, coords in (('h', ys), ('b', xs)):
        m = len(coords)
        sup = _support_pattern(m)
        if not check_support(coords, set(sup), db):
            sup = list(range(m))                       # wide spacing: support every bar
        hp, cr = _pairs(m, sup)
        out['sup_' + key] = sup
        out['hoops_' + key] = [(coords[a], coords[b]) for a, b in hp]
        out['cross_' + key] = [coords[i] for i in cr]
        ok = ok and check_support(coords, set(sup), db)
    out['nset'] = 1 + len(out['hoops_h']) + len(out['hoops_b'])
    out['ncross'] = len(out['cross_h']) + len(out['cross_b'])
    out['ok'] = ok
    return out


def shear_legs(T):
    """legs that run the full depth, per shear direction (CEDA: only full-depth legs count).
    V along y (parallel to h): legs parallel to y spanning full h = 2 (outer) + 2 per b-face hoop + b-face crossties.
    V along x (parallel to b): 2 (outer) + 2 per h-face hoop + h-face crossties."""
    return dict(Vy=2 + 2 * len(T['hoops_b']) + len(T['cross_b']), Vx=2 + 2 * len(T['hoops_h']) + len(T['cross_h']))


# ------------------------------------------------------------------------------------------------ bundles
def tie_corner_groups(grid, db):
    """symmetric groups of tie-corner positions, ordered column corners first then outside -> inside."""
    if grid.shape == 'circ':
        return [list(range(grid.n))]
    T = ties(grid, db)
    P, e = grid._perim(db)
    sup_h, sup_b = set(T['sup_h']), set(T['sup_b'])
    cx, cy = grid.b / 2, grid.h / 2
    key = {}
    for k, p in enumerate(P):
        if p['face'][0] == 'h' and p['idx'] in sup_h:
            j = p['idx']; g = ('h', min(j, grid.nh - 1 - j))
        elif p['face'][0] == 'b' and p['idx'] in sup_b:
            i = p['idx']; g = ('b', min(i, grid.nb - 1 - i))
        else:
            continue
        key.setdefault(g, []).append(k)
    def order(g):
        ks = key[g]
        p = P[ks[0]]
        corner = p.get('corner', False)
        return (0 if corner else 1, -math.hypot((p['x'] - cx) / grid.b, (p['y'] - cy) / grid.h))
    return [key[g] for g in sorted(key, key=order)]


def spacing_check(grid, P, counts, db):
    """clear spacing between neighbouring positions on each face with bundle widths; returns (ok, min_clear, notes)."""
    faces = {}
    for k, p in enumerate(P):
        f = p['face']
        if f in ('bB', 'bT'):
            continue
        faces.setdefault(f, []).append(k)
    seqs = []
    if grid.shape == 'circ':
        ks = list(range(len(P))); seqs.append(ks + [ks[0]])
    else:
        e = grid.cover + grid.tie + db / 2
        for side in ('L', 'R'):
            seqs.append(sorted(faces['h' + side], key=lambda k: P[k]['y']))
        # b faces: corners from h faces + intermediates
        for side, yv in (('B', e), ('T', grid.h - e)):
            ks = [k for k, p in enumerate(P) if abs(p['y'] - yv) < 1e-6 and (p['face'] == 'b' + side or p.get('corner'))]
            seqs.append(sorted(ks, key=lambda k: P[k]['x']))
    mn = 1e9
    for s in seqs:
        for a, b_ in zip(s, s[1:]):
            d = math.hypot(P[a]['x'] - P[b_]['x'], P[a]['y'] - P[b_]['y'])
            clr = d - (bw(counts[a], db) + bw(counts[b_], db)) / 2
            mn = min(mn, clr)
            if clr < clear_req(db, max(counts[a], counts[b_])) - 1e-6:
                return False, clr
    return True, mn


def ladder(grid, sizes=(20, 25, 28, 32), kmax=4):
    """list of steps [(db, counts tuple, phase)] in build-up order (weakest first).
    phase 1 = bundles at tie corners only, phase 2 = bundles also at other positions (allowed, CEDA 20 Oct 2026)."""
    sizes = sorted(sizes)
    # singles: a size that breaks the clear spacing (ACI 25.2.3) on the grid is dropped (small faces, e.g. 3 bars on 250 mm)
    ok_sizes = []
    for d in sizes:
        Pd, _ = grid.positions(d)
        if spacing_check(grid, Pd, [1] * len(Pd), d)[0]:
            ok_sizes.append(d)
    if not ok_sizes:
        ok_sizes = sizes[:1]
        grid.notes.append(f'clear spacing not met even with DB{sizes[0]} singles (ACI 25.2.3) – revise section or bar count')
    elif ok_sizes != sizes:
        grid.notes.append(f'DB{max(ok_sizes)} is the largest bar that keeps clear spacing (ACI 25.2.3) – larger sizes and bundles skipped')
    sizes = ok_sizes
    P0, _ = grid.positions(sizes[-1])
    N = len(P0)
    steps = [(d, tuple([1] * N), 0) for d in sizes]
    dbm = sizes[-1]
    groups = tie_corner_groups(grid, dbm)
    cur = [1] * N
    # CEDA rule (20 Oct 2026): bundles may go at any position, but the build-up starts at the tie corners and a bundle size
    # is completed over the whole section before any position takes the next size: 2-bar bundles at the tie corners
    # (column corners first, outside -> inside), then 2-bar bundles at the other positions, then 3-bar bundles in the same
    # order, then 4-bar bundles. phase 1 = only tie corners carry bundles, phase 2 = other positions too.
    rest_groups = []
    if grid.shape != 'circ':
        incorner = set(p for g in groups for p in g)
        rest = {}
        cx, cy = grid.b / 2, grid.h / 2
        for k_, p in enumerate(P0):
            if k_ in incorner:
                continue
            key = (p['face'][0], min(p['idx'], (grid.nh if p['face'][0] == 'h' else grid.nb) - 1 - p['idx']))
            rest.setdefault(key, []).append(k_)
        order = sorted(rest, key=lambda g: -math.hypot((P0[rest[g][0]]['x'] - cx) / grid.b, (P0[rest[g][0]]['y'] - cy) / grid.h))
        rest_groups = [rest[g] for g in order]
    corner_set = set(p for g in groups for p in g)
    for k in range(2, kmax + 1):
        for g in groups + rest_groups:
            trial = cur[:]
            for p in g:
                trial[p] = k
            ok, _ = spacing_check(grid, P0, trial, dbm)
            if ok:
                cur = trial
                ph = 1 if all(cur[q] == 1 for q in range(N) if q not in corner_set) else 2
                steps.append((dbm, tuple(cur), ph))
    return steps          # (db, counts, phase) phase 0 singles, 1 tie corners, 2 other positions


def bars_cm(grid, db, counts):
    """true bar positions (cm, origin lower-left corner) including bundle offsets; returns list of (x, y, A)."""
    P, e = grid.positions(db)
    a1 = math.pi * db ** 2 / 4 / 100
    rr = db / 2
    out = []
    for p, k in zip(P, counts):
        nx, ny = p['n']; tx, ty = p['t']
        if k == 1:
            offs = [(0, 0)]
        elif k == 2:
            offs = [(0, 0), (db * nx, db * ny)]
        elif k == 3:
            offs = [(-rr * tx, -rr * ty), (rr * tx, rr * ty), (1.732 * rr * nx, 1.732 * rr * ny)]
        else:
            offs = [(-rr * tx, -rr * ty), (rr * tx, rr * ty),
                    (-rr * tx + db * nx, -rr * ty + db * ny), (rr * tx + db * nx, rr * ty + db * ny)]
        for ox, oy in offs:
            out.append(((p['x'] + ox) / 10, (p['y'] + oy) / 10, a1))
    return out


def describe(counts, phase=1):
    ks = sorted(set(counts))
    inner = ' + INNER BARS AT TIE CROSSINGS' if phase == 3 else ''
    if ks == [1]:
        return inner.strip(' +')
    return 'BUNDLE ' + '/'.join(str(k) for k in ks if k > 1) + (' @ TIE CORNERS' if phase in (0, 1, 3) else ' @ TIE CORNERS + OTHER POSITIONS') + inner
