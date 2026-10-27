"""CEDA column design: slenderness, bar selection, shear, ties, f'c reduction, story ranges and marks.

Units: kg, cm, kg-m (forces), mm for bar/layout data.
Code basis (tags used in reports):
  [Code] กฎกระทรวงกำหนดการออกแบบโครงสร้างอาคาร … พ.ศ. 2566 ข้อ 7 (combos), ข้อ 8 วรรคสอง (φ, quality-controlled column)
  [Code] ACI 318-19: 6.2.5 / 6.6.4 slenderness, 21.2.2 φ transition, 22.4.2.1 Pn,max, 22.5 shear, 25.x detailing, 10.6.1.1 ρ
  [Code] ประกาศ มท. 2564 ข้อ 26 / มยผ. 1301/1302-61 5.2.7 IMF minimum ties
  [Practice] CEDA: grid c/c 125-150, 1 % pattern + min bar by long side, bottom-up bundles at tie corners,
            reduce bundles then size going up, common story ranges, ρ <= 6 %, Cm = 1, βd with 25 % LL
"""
import math
import numpy as np
from colsurf import Section
import layout as LY

PHI = dict(tied=0.70, spiral=0.75, flex=0.90, shear=0.85, bearing=0.70)          # ข้อ 8 วรรคสอง (QC column)
ALPHA = dict(tied=0.80, spiral=0.85)                                             # ACI 22.4.2.1


# ------------------------------------------------------------------------------------------------ section cache
class Cache:
    def __init__(self):
        self.S = {}

    def section(self, shape, b, h, fc, fy, db, counts, grid, spiral=False):
        key = (shape, b, h, fc, fy, db, counts, spiral, getattr(grid, 'nh', 0), getattr(grid, 'nb', 0), getattr(grid, 'n', 0), getattr(grid, 'interior', False))
        if key not in self.S:
            bars = LY.bars_cm(grid, db, counts)
            tie = 'spiral' if spiral else 'tied'
            S = Section(b, h, bars, fc, fy, phi_c=PHI[tie], alpha=ALPHA[tie], phi_t=PHI['flex'], shape=shape)
            S.surface()
            S.Isex = float((S.bA * S.by ** 2).sum())
            S.Isey = float((S.bA * S.bx ** 2).sum())
            S.nbar = len(bars)
            self.S[key] = S
        return self.S[key]


def dc_many(S, P, Mx, My):
    v = np.vstack([P, Mx, My]).T / S._scale()
    n, d = S.hull.equations[:, :3], S.hull.equations[:, 3]
    nv = v @ n.T
    with np.errstate(divide='ignore', invalid='ignore'):
        t = np.where(nv > 1e-12, -d[None, :] / nv, np.inf)
    tm = t.min(axis=1)
    out = np.where(np.isfinite(tm), 1.0 / tm, 0.0)
    out[~np.any(v != 0, axis=1)] = 0.0
    return out


# ------------------------------------------------------------------------------------------------ slenderness
def magnified(S, rows, b, h, fc, Lu, k, betad, Cm=1.0, lim=22.0):
    """moment magnifier (non-sway). rows: arrays P, M3 (-> Mx), M2 (-> My). Returns dict with Mx_d, My_d, dx, dy."""
    Ec = 15100 * math.sqrt(fc)
    Es = 2.04e6
    P = rows['P']
    out = {}
    for ax, M, dim, Ig, Ise in (('x', rows['M3'], h, b * h ** 3 / 12, S.Isex), ('y', rows['M2'], b, h * b ** 3 / 12, S.Isey)):
        if S.shape == 'circ':
            Ig = math.pi * b ** 4 / 64
            r = 0.25 * b                                       # ACI 6.2.5.2
        else:
            r = 0.3 * dim
        slr = k * Lu / r
        slender = slr > lim
        EI = (0.2 * Ec * Ig + Es * Ise) / (1 + betad)        # ACI 6.6.4.4.4(a)
        Pc = math.pi ** 2 * EI / (k * Lu) ** 2                  # no φ (agreed D3)
        if slender:
            with np.errstate(divide='ignore'):
                dl = np.where(P >= 0.75 * Pc, np.inf, np.maximum(Cm / (1 - np.maximum(P, 0) / (0.75 * Pc)), 1.0))
            M2min = np.maximum(P, 0) * (1.5 + 0.03 * dim) / 100       # kg-m, ACI 6.6.4.5.4
            Md = np.where(M == 0, 1.0, np.sign(M)) * np.maximum(np.abs(M), M2min) * dl
        else:
            dl = np.ones_like(P)
            Md = M.copy()
        out[ax] = dict(r=r, slr=slr, slender=slender, EI=EI, Pc=Pc, delta=dl, Md=Md)
    return out


# ------------------------------------------------------------------------------------------------ one column-story
def evaluate(cache, grid, col, fc, fy, db, counts, spiral=False):
    """col: dict(shape, b, h (cm), Lu (cm), k, betad, rows (dict of numpy arrays P, M2, M3, V2, V3, combo, story...))."""
    S = cache.section(col['shape'], col['b'], col['h'], fc, fy, db, counts, grid, spiral)
    mg = magnified(S, col['rows'], col['b'], col['h'], fc, col['Lu'], col['k'], col['betad'])
    dx, dy = mg['x']['delta'], mg['y']['delta']
    bad = ~np.isfinite(dx) | ~np.isfinite(dy)
    dc = dc_many(S, col['rows']['P'], np.where(bad, 0, mg['x']['Md']), np.where(bad, 0, mg['y']['Md']))
    dc[bad] = np.inf
    i = int(np.argmax(dc))
    return dict(S=S, mg=mg, dc=dc, dcmax=float(dc[i]), gov=i, rho=S.As / S.Ag, nbar=S.nbar)


def choose_step(cache, grid, steps, col, fc, fy, rho_max=0.06, rho_ask=0.08, spiral=False, start=0, dc_lim=1.0):
    """lowest step >= start with D/C <= 1 and ρ <= rho_max; also report the first step that would pass with ρ <= rho_ask."""
    last_ok = None
    ask = None
    for j in range(start, len(steps)):
        db, counts = steps[j][0], steps[j][1]
        ev = evaluate(cache, grid, col, fc, fy, db, counts, spiral)
        if ev['rho'] <= rho_max + 1e-9:
            last_ok = (j, ev)
            if ev['dcmax'] <= dc_lim:          # dc_lim > 1 only for label-stories whose overload the engineer accepted (v1.3.3)
                return dict(step=j, ev=ev, status='OK' if ev['dcmax'] <= 1.0 else 'ACCEPTED')
        elif ev['rho'] <= rho_ask + 1e-9 and ev['dcmax'] <= dc_lim and ask is None:
            ask = (j, ev)
            break
    if ask:
        return dict(step=ask[0], ev=ask[1], status='ASK_RHO')          # needs engineer approval (6-8 %)
    if last_ok:
        return dict(step=last_ok[0], ev=last_ok[1], status='REVISE')    # no step passes -> revise section/f'c
    db, counts = steps[start][0], steps[start][1]
    return dict(step=start, ev=evaluate(cache, grid, col, fc, fy, db, counts, spiral), status='REVISE')


# ------------------------------------------------------------------------------------------------ shear & ties
def tie_fyt(tie_db, fyt_input):
    """CEDA: DB12 -> 4000 ksc; DB16-32 -> limited to 4200 ksc for shear (Ash uses actual fyt)."""
    return 4000.0 if tie_db <= 12 else min(fyt_input, 4200.0)


def shear_check(col, ev, T, fc, tie_db, fyt, so_cm, s_cm, frame='gravity', cover=4.0, imf_E_factor=2.0, extra=None):
    """per direction: V2 (parallel to h, bw = b) and V3 (parallel to b, bw = h). φ = 0.85 (ข้อ 8)."""
    S = ev['S']
    rows = col['rows']
    legs = LY.shear_legs(T)
    if extra:
        legs = {k: legs[k] + extra.get(k, 0) for k in legs}
    At = math.pi * tie_db ** 2 / 4 / 100
    fyv = tie_fyt(tie_db, fyt)
    res = {}
    for key, V, bw, D, nl in (('V2', rows['V2'], col['b'], col['h'], legs['Vy']), ('V3', rows['V3'], col['h'], col['b'], legs['Vx'])):
        d = D - cover - tie_db / 10 - 1.6
        Nu = rows['P']
        fac = np.where(Nu < 0, np.maximum(1 + Nu / (35 * S.Ag), 0.0), 1.0)    # tension reduces Vc; no compression benefit
        Vc = 0.53 * fac * math.sqrt(fc) * bw * d
        Vu = np.abs(V)
        Ve = 0.0
        if frame == 'IMF':
            # ACI 18.4.3.1 / มยผ. 5.2.7.2: lesser of (a) shear from Mn at both ends (Pu giving max Mn) and
            # (b) design shear with E amplified (CEDA: x2 on the seismic combos, upper bound incl. gravity part)
            Ps = np.linspace(max(Nu.min(), 0), Nu.max(), 5)
            axis = 'x' if key == 'V2' else 'y'
            Mn = max(S.nominal_M(p, axis) for p in Ps)
            Va = 2 * Mn * 100 / col['Lu']                                      # kg
            seis = col.get('seis')
            Vb = imf_E_factor * float(np.max(np.abs(V[seis]))) if seis is not None and np.any(seis) else Va
            Ve = min(Va, Vb)
        Vd = np.maximum(Vu, Ve)
        Av = nl * At
        out = {}
        for zone, s in (('lo', so_cm), ('mid', s_cm)):
            Vs = min(Av * fyv * d / s, 2.1 * math.sqrt(fc) * bw * d)
            phiVn = PHI['shear'] * (Vc + Vs)
            ratio = Vd / phiVn
            i = int(np.argmax(ratio))
            avmin = max(0.2 * math.sqrt(fc), 3.5) * bw * s / fyv
            need_min = bool(np.any(Vd > 0.5 * PHI['shear'] * Vc))
            out[zone] = dict(s=s, Vu=float(Vd[i]), phiVn=float(phiVn[i]), dc=float(ratio[i]), Av=Av, Avmin=avmin,
                             avmin_ok=(Av >= avmin) or not need_min, legs=nl, gov=i)
        res[key] = dict(d=d, bw=bw, Ve=Ve, fyt=fyv, **out)
    return res


def imf_ties(col, db_min_mm, tie_db, so_mm):
    """IMF minimum (ประกาศ มท. 2564 ข้อ 26(1) = มยผ. 5.2.7.4)."""
    smin = min(col['b'], col['h']) * 10
    so_max = min(8 * db_min_mm, 24 * tie_db, smin / 2, 300)
    lo = max(col['Lu'] * 10 / 6, max(col['b'], col['h']) * 10, 500)
    return dict(so_max=so_max, lo=lo, ok=so_mm <= so_max + 1e-6, s_max=2 * so_max, first=so_mm / 2)


def spiral_check(col, fc, fyt, pitch_mm, sp_db, cover_mm):
    """ρs >= 0.45(Ag/Ach − 1)f'c/fyt; clear pitch 25-75 mm (ACI 25.7.3)."""
    D = col['b'] * 10
    Dc = D - 2 * cover_mm
    Ag, Ach = math.pi * D ** 2 / 4, math.pi * Dc ** 2 / 4
    As = math.pi * sp_db ** 2 / 4
    rho_s = 4 * As / (Dc * pitch_mm)
    req = 0.45 * (Ag / Ach - 1) * fc / fyt
    clear = pitch_mm - sp_db
    return dict(rho_s=rho_s, req=req, ok=rho_s >= req and 25 <= clear <= 75, clear=clear)


# ------------------------------------------------------------------------------------------------ project level
def required_rho(cache, grids, steps, cols, fc, fy, rho_max, jmin=None):
    """ρ of the lowest passing step (>= 1 % pattern) per (label, story) for a given f'c (None if nothing passes)."""
    out = {}
    for key, col in cols.items():
        g = grids[col['gkey']]
        r = choose_step(cache, g, steps[col['gkey']], col, fc, fy, rho_max, rho_max, start=(jmin or {}).get(col['gkey'], 0))
        out[key] = r['ev']['rho'] if r['status'] == 'OK' else None
    return out


def choose_fc(cache, grids, steps, cols, stories, fc_list, fc_typ, fy, rho_max=0.06, share=0.5, rho_low=0.015, jmin=None):
    """bottom f'c = lowest standard value (>= typical) giving ρ <= 6 % for every column of the lowest story;
    reduction story = lowest story s where (a) every column at >= s works with f'c typical (ρ <= 6 %) and
    (b) >= `share` of the columns at s need ρ <= 1.5 % with f'c typical. One reduction for the whole project."""
    low = stories[0]
    fc_bot = None
    # v1.3.3: column-stories that fail even with the highest f'c need a larger section – they are left out of the study
    rtop = required_rho(cache, grids, steps, cols, max(fc_list), fy, rho_max, jmin)
    hopeless = {k for k, v in rtop.items() if v is None}
    for fc in sorted(f for f in fc_list if f >= fc_typ):
        sub = {k: c for k, c in cols.items() if k[1] == low and k not in hopeless}
        rr = required_rho(cache, grids, steps, sub, fc, fy, rho_max, jmin)
        if all(v is not None for v in rr.values()):
            fc_bot = fc
            break
    if fc_bot is None:
        fc_bot = max(fc_list)
    rtyp = required_rho(cache, grids, steps, cols, fc_typ, fy, rho_max, jmin)
    table = []
    red = None
    for i, s in enumerate(stories):
        at = [k for k in cols if k[1] == s]
        if not at:
            continue
        feas_above = all(rtyp[k] is not None for k in cols if stories.index(k[1]) >= i and k not in hopeless)
        sh = sum(1 for k in at if rtyp[k] is not None and rtyp[k] <= rho_low) / len(at)
        table.append(dict(story=s, share_low_rho=sh, feasible_above=feas_above))
        if red is None and feas_above and sh >= share:
            red = s
    if fc_bot == fc_typ:
        red = stories[0]
    return dict(fc_bottom=fc_bot, fc_typical=fc_typ, reduce_at=red, table=table,
                excluded=sorted(f'{a} {b}' for a, b in hopeless))   # fail at every f'c -> enlarge the section


def min_bar_size(shape, b_mm, h_mm):
    """CEDA (Oct 2026): smallest longitudinal bar by the LONG side: <= 200 mm DB12, > 200 DB16, > 500 DB20."""
    L = b_mm if shape == 'circ' else max(b_mm, h_mm)
    return 12 if L <= 200 + 1e-6 else (16 if L <= 500 + 1e-6 else 20)


def pattern_step(steps, Ag_cm2, rho_min=0.01):
    """index of the 1 % pattern: first step (singles, smallest size first) with As >= rho_min*Ag [ACI 10.6.1.1].
    The positions are fixed by the c/c 125-150 grid, so a pattern below 1 % is fixed by a larger size, not more bars."""
    for j, st in enumerate(steps):
        db, counts = st[0], st[1]
        if sum(counts) * math.pi * db ** 2 / 400 >= rho_min * Ag_cm2 - 1e-9:
            return j
    return len(steps) - 1


def _as(step):
    return sum(step[1]) * math.pi * step[0] ** 2 / 400


def story_ranges(stories, basement, height_m, fc_of, req, steps_of, lst_m, stock_m=12.0, max_group=3, mode='auto', groups=None):
    """Common story ranges for the whole project (= rows of the Table of Column), bottom -> top.
    CEDA rule (Oct 2026):
      * basement: a break at every story (reduction allowed at every basement level – construction method);
      * above ground: guidance 2-3 stories per range so that one 12 m bar + Lst covers the range; NOT a fixed limit:
        a range is closed earlier when any label could remove its bundles or halve its steel at the next story;
      * a change of f'c is always a break.
    req: {label: {story: required step (monotonic)}}, steps_of: {label: steps list}.
    mode 'each' = every story is a break (input stories already grouped); groups = explicit [[first, last], ...]."""
    n = len(stories)
    if groups:
        idx = {s: i for i, s in enumerate(stories)}
        return [(g[0], g[1]) for g in sorted(groups, key=lambda g: idx[g[0]])]
    if mode == 'each':
        return [(s, s) for s in stories]
    out, i = [], 0
    while i < n:
        s = stories[i]
        if s in basement:
            out.append((s, s)); i += 1; continue
        j = i
        H = height_m.get(s, 3.0)
        while j + 1 < n:
            nx = stories[j + 1]
            if nx in basement or fc_of[nx] != fc_of[stories[i]]:
                break
            if j + 1 - i + 1 > max_group or H + height_m.get(nx, 3.0) + lst_m > stock_m + 1e-9:
                break
            sig = False
            for lab, r in req.items():
                have = [stories[q] for q in range(i, j + 1) if stories[q] in r]
                if not have or nx not in r:
                    continue
                st = steps_of[lab]
                sg = (lambda x: st[x]) if isinstance(st, dict) else (lambda x: st)   # v1.3.1: steps per story (section changes)
                xg = max(have, key=lambda x: r[x])
                gov = sg(xg)[r[xg]]
                nxt = sg(nx)[r[nx]]
                if (max(gov[1]) > 1 and max(nxt[1]) == 1) or _as(nxt) <= 0.5 * _as(gov) + 1e-9:
                    sig = True; break
            if sig:
                break
            H += height_m.get(nx, 3.0); j += 1
        out.append((stories[i], stories[j])); i = j + 1
    return out


def merge_unused(ranges, stories, picks, fc_of):
    """drop a break that no label uses (same step for every label and same f'c on both sides)."""
    out = [list(ranges[0])]
    for r in ranges[1:]:
        lo, hi = out[-1], r
        same = fc_of[lo[0]] == fc_of[hi[0]]
        if same:
            for lab, p in picks.items():
                a = p.get(tuple(lo)); b = p.get(tuple(hi))
                if a is not None and b is not None and a != b:
                    same = False; break
                if (a is None) != (b is None):
                    same = False; break
        if same:
            out[-1][1] = hi[1]
        else:
            out.append(list(hi))
    return [tuple(x) for x in out]


def lap_length(lap_table, fc, db, k=1):
    """Lst = Class B tension lap from the project table (S-00-04-04).
    CEDA: 12 m stock -> laps are placed where bundles are <= 2 bars, so no bundle factor is applied; the bar that stops
    when a bundle is reduced extends Lst above the floor. If a lap inside a 3/4-bar bundle cannot be avoided,
    ACI 25.6.1.5 requires x1.2 / x1.33 (reported separately)."""
    t = lap_table.get(str(int(fc))) or lap_table.get(int(fc)) or {}
    L = t.get(str(int(db))) or t.get(int(db))
    return float(L) if L is not None else None


def design_shear(items, T, tie_db, fyt, so0_mm, s0_mm, frame, cover_cm, Ef):
    """CEDA order when shear governs: reduce s (outside lo) down to 150, then add full-depth crossties, then s down to
    100 mm (ACI minimum practical), otherwise report 'use DB16 ties'. items: list of (col, ev, fc).
    Returns dict(so, s, extra, results per item, ok, note)."""
    def run(so, s, extra):
        out = [shear_check(c, ev, T, fc, tie_db, fyt, so / 10, s / 10, frame, cover_cm, Ef, extra) for c, ev, fc in items]
        ok = all(max(r[k]['lo']['dc'], r[k]['mid']['dc']) <= 1.0 and r[k]['lo']['avmin_ok'] and r[k]['mid']['avmin_ok']
                 for r in out for k in ('V2', 'V3'))
        return ok, out
    tried = []
    for s in [x for x in (s0_mm, 250, 200, 150) if x <= s0_mm]:
        so = min(so0_mm, s)
        ok, out = run(so, s, {})
        if ok:
            return dict(so=so, s=s, extra={}, res=out, ok=True, note='' if s == s0_mm else f'shear: s reduced to {s} mm')
    for n in range(1, 5):
        for dirn in ({'Vy': n}, {'Vx': n}, {'Vy': n, 'Vx': n}):
            ok, out = run(min(so0_mm, 150), 150, dirn)
            if ok:
                return dict(so=min(so0_mm, 150), s=150, extra=dirn, res=out, ok=True,
                            note=f'shear: s 150 mm + full-depth crossties {dirn}')
    for n in range(0, 5):
        ok, out = run(100, 100, {'Vy': n, 'Vx': n})
        if ok:
            return dict(so=100, s=100, extra={'Vy': n, 'Vx': n}, res=out, ok=True, note=f'shear: s 100 mm + {n} crossties each way')
    ok, out = run(100, 100, {'Vy': 4, 'Vx': 4})
    return dict(so=100, s=100, extra={'Vy': 4, 'Vx': 4}, res=out, ok=False, note='shear NOT O.K. – use DB16 ties or revise section')
