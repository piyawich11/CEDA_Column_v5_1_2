"""f'c study – v1.5.0 case table `cases()` (CEDA 27 Oct 2026, used by run.py and the app) + v1.4.0 scenarios `study()` (kept).

v1.4.0 (CEDA 23 Oct 2026) – project-level f'c scenarios with outliers, utilisation floor and cost.

usage:  python3 -I fc_study.py OUTDIR [prices.json]   -> OUTDIR/fc_study.json   (OUTDIR = run.py output with state.pkl)
also imported by run.py (f'c mode auto) and by the app.

Rule (designer, 23 Oct 2026) – f'c is decided for the whole project (one reduction), never per column:
  * a scenario = bottom f'c fb (>= typical) used below the reduction story r, typical f'c from r up;
  * a column-story FAILS when no bar arrangement passes with ρ <= 6 % (<= 8 % when approved) on the 125-150 grid, the wider
    grid (3-4-bar bundles) or inner bars (basement / approved only) – the same order as the design;
  * column-stories failing with every f'c (section too small) are listed separately and not counted (v1.3.3);
  * the reduction story needs >= 50 % of its columns at ρ <= 1.5 % with the typical f'c (CEDA practice);
  * S0  = old rule: no failing column at any story;
  * S10 = lowest fb, then lowest r, with failing columns <= 10 % of every story;
  * D/C floor: a passing column with D/C < 0.75 is UNDER-USED, except a column at the typical f'c with minimum steel
    (ρ <= 1.5 %, or the 1 % pattern of its section when that is above 1.5 %) – it cannot be made lighter;
  * S25 = when S10 leaves under-used columns: the scenario with failing columns <= 25 % of every story that has the fewest
    under-used columns (then fewest failing, then lower fb / r);
  * recommended = S25 if it has fewer under-used columns than S10, else S10. The designer chooses from the what-if table
    (quantities and cost per scenario); failing columns go to the fix board (enlarge section, approve ρ up to 8 %, overload).
Quantities: concrete m³ per f'c (Ag × column length) and longitudinal steel kg per bar size (As × column length, 7,850 kg/m³)
of the lowest passing arrangement per column-story – before story ranges and mark envelopes, ties / laps / couplers not
included. Cost = quantities × unit prices (concrete by f'c, steel by bar size) when prices are given.
"""
import os, sys, json, math, pickle
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import layout as LY      # noqa: E402
import design as DS      # noqa: E402

RULE = dict(outlier=0.10, outlier_max=0.25, dc_min=0.75, exempt_rho=0.015, share_low=0.50, rho_low=0.015)
STEEL = 7.85e-3          # kg per cm³


def grid_steps(gk, det):
    """grid + ladder + 1 % pattern index for a grid key (shape, b, h[, 'W'][, 'I']) – same construction as run.py."""
    shape, b, h = gk[:3]
    wide, inner = 'W' in gk[3:], 'I' in gk[3:]
    sizes = det.get('bar_sizes', [12, 16, 20, 25, 28, 32]); kmax = det.get('kmax', 4)
    cc = tuple(det.get('cc', [125, 150])); cc_w = tuple(det.get('cc_bundle34', [125, 160]))
    small = tuple(tuple(x) for x in det.get('small_face', LY.SMALL_FACE))
    dmin = DS.min_bar_size(shape, b * 10, h * 10)
    sz = [d for d in sizes if d >= dmin] or [max(sizes)]
    g = LY.Grid(b * 10, h * 10, det.get('cover_mm', 40), det.get('tie_db', 12), max(sz), cc_w if wide else cc, shape, small)
    st = LY.ladder(g, sz, kmax)
    if wide:
        st = [x for x in st if max(x[1]) >= 3]
    if inner:
        g.interior = True
        nin = len(g.inner(st[-1][0])) if st and shape != 'circ' else 0
        st = [(st[-1][0], tuple(st[-1][1]) + (1,) * nin, 3)] if nin else []
    Ag = math.pi * b ** 2 / 4 if shape == 'circ' else b * h
    j0 = 0 if (wide or inner) else DS.pattern_step(st, Ag, det.get('rho_min', 0.01))
    return g, st, j0


class Grids:
    def __init__(self, det):
        self.det, self.G = det, {}

    def get(self, gk):
        gk = tuple(gk)
        if gk not in self.G:
            self.G[gk] = grid_steps(gk, self.det)
        return self.G[gk]


def try_column(cache, grids, col, fc, fy, rho_lim, inner_ok, dc_lim=1.0):
    """CEDA order: 125-150 grid -> wider grid (3-4-bar bundles) -> inner bars (basement / approved ρ only).
    -> dict(ok, status, dc, rho, db, nbar, As, gk, step, ev)"""
    base = tuple(col['gkey'][:3])
    keys = [base, base + ('W',)] + ([base + ('I',), base + ('W', 'I')] if inner_ok and base[0] != 'circ' else [])
    last = None
    for gk in keys:
        g, st, j0 = grids.get(gk)
        if not st:
            continue
        r = DS.choose_step(cache, g, st, col, fc, fy, rho_lim, rho_lim, start=j0, dc_lim=dc_lim)
        s = st[r['step']]
        out = dict(ok=r['status'] in ('OK', 'ACCEPTED'), status=r['status'], dc=float(r['ev']['dcmax']), rho=float(r['ev']['rho']),
                   at_min=(gk == base and r['step'] == j0),          # minimum arrangement of the section (1 % pattern)
                   db=int(s[0]), nbar=int(sum(s[1])), As=DS._as(s), gk=list(gk), step=r['step'], ev=r['ev'],
                   counts=list(s[1]), phase=s[2] if len(s) > 2 else 0)
        if out['ok']:
            return out
        if last is None or out['dc'] < last['dc']:      # not passing: keep the arrangement with the lowest D/C (most that fits)
            last = out
    return last


def fc_matrix(cache, grids, cols, fcs, fy, rho_max, rho_ask, approved, basement, log=None):
    """{(label, story): {fc: result}} for every column-story and every candidate f'c."""
    M = {}
    for i, ((lab, s), c) in enumerate(sorted(cols.items())):
        lim = rho_ask if (lab, s) in approved else rho_max
        inner_ok = s in basement or (lab, s) in approved
        M[(lab, s)] = {}
        for fc in fcs:
            r = try_column(cache, grids, c, fc, fy, lim, inner_ok)
            r.pop('ev', None)
            M[(lab, s)][fc] = r
        if log and i % 200 == 0:
            log(f'f\'c study {i}/{len(cols)}')
    return M


def _qty(c, r):
    H = c.get('H') or c.get('Lu') or 0.0
    Ag = math.pi * c['b'] ** 2 / 4 if c['shape'] == 'circ' else c['b'] * c['h']
    return Ag * H / 1e6, r['As'] * H * STEEL


def scenario(M, cols, stories, fb, r, fc_typ, rule, hopeless):
    """statistics of one scenario: fb below story r, typical from r up (r None = typical everywhere)."""
    ri = stories.index(r) if r else 0
    fc_of = {s: (fb if i < ri else fc_typ) for i, s in enumerate(stories)}
    per = {}
    conc, steel, fails, under = {}, {}, [], []
    for (lab, s), c in cols.items():
        fc = fc_of[s]
        x = M[(lab, s)][fc]
        n = per.setdefault(s, dict(n=0, fail=0, under=0, low=0))
        n['n'] += 1
        v, kg = _qty(c, x)
        conc[fc] = conc.get(fc, 0.0) + v
        steel[x['db']] = steel.get(x['db'], 0.0) + kg
        if (lab, s) in hopeless:
            continue
        if not x['ok']:
            n['fail'] += 1; fails.append(f'{lab} {s}')
        elif x['dc'] < rule['dc_min'] and not (fc == fc_typ and (x['rho'] <= rule['exempt_rho'] + 1e-9 or x.get('at_min'))):
            n['under'] += 1; under.append(f'{lab} {s}')
        if fc == fc_typ and x['ok'] and x['rho'] <= rule['rho_low'] + 1e-9:
            n['low'] += 1
    max_fail = max((p['fail'] / p['n'] for p in per.values() if p['n']), default=0.0)
    share_r = (per[r]['low'] / per[r]['n']) if r and per.get(r, {}).get('n') else None
    rule_ok = r is None or (share_r is not None and share_r >= rule['share_low'] - 1e-9)
    return dict(fc_bottom=fb, reduce_at=r, fc_of=fc_of, max_fail_share=max_fail, n_fail=len(fails), n_under=len(under),
                fails=sorted(fails), under=sorted(under), share_low_at_reduction=share_r, reduction_rule_ok=rule_ok,
                concrete_m3={str(k): round(v, 3) for k, v in sorted(conc.items())},
                steel_kg={str(k): round(v, 1) for k, v in sorted(steel.items())},
                per_story={s: per[s] for s in stories if s in per})


def cost(sc, prices):
    """THB: concrete by f'c, steel by bar size; None where a price is missing (listed)."""
    if not prices:
        return None, []
    pc, ps = prices.get('concrete', {}), prices.get('steel', {})
    tot, miss = 0.0, []
    for fc, v in sc['concrete_m3'].items():
        p = pc.get(str(int(float(fc))))
        if p is None:
            miss.append(f"concrete {int(float(fc))} ksc")
        else:
            tot += v * float(p)
    for db, kg in sc['steel_kg'].items():
        p = ps.get(str(int(float(db))))
        if p is None:
            miss.append(f'steel DB{int(float(db))}')
        else:
            tot += kg * float(p)
    return round(tot, 0), miss


def study(M, cols, stories, fc_typ, fc_hi, rule=None, prices=None):
    """all scenarios + S0 / S10 / S25 / recommended (see module doc)."""
    rule = dict(RULE, **(rule or {}))
    hopeless = {k for k, v in M.items() if not any(x['ok'] for x in v.values())}
    scs = [scenario(M, cols, stories, fc_typ, None, fc_typ, rule, hopeless)]
    for fb in sorted(fc_hi):
        for r in stories[1:]:
            scs.append(scenario(M, cols, stories, fb, r, fc_typ, rule, hopeless))
    for i, sc in enumerate(scs):
        sc['id'] = i
        sc['cost_thb'], sc['cost_missing'] = cost(sc, prices)
    order = lambda sc: (sc['fc_bottom'], stories.index(sc['reduce_at']) if sc['reduce_at'] else -1)
    valid = [sc for sc in scs if sc['reduction_rule_ok']]

    def lowest(lim):
        c = [sc for sc in valid if sc['max_fail_share'] <= lim + 1e-9]
        return min(c, key=order) if c else None
    s0, s10 = lowest(0.0), lowest(rule['outlier'])
    c25 = [sc for sc in valid if sc['max_fail_share'] <= rule['outlier_max'] + 1e-9]
    s25 = min(c25, key=lambda sc: (sc['n_under'], sc['n_fail']) + order(sc)) if c25 else None
    rec = s10
    if s10 is None:
        rec = s25 or s0
    elif s10['n_under'] and s25 and s25['n_under'] < s10['n_under']:
        rec = s25
    fallback = None
    if rec is None:                      # no scenario within the limits: fewest failing (highest f'c first), designer must decide
        fallback = min(valid or scs, key=lambda sc: (sc['max_fail_share'], sc['n_fail'], -sc['fc_bottom']) + order(sc)[1:])
        rec = fallback
    tags = {}
    if fallback:
        tags.setdefault(fallback['id'], []).append('FALLBACK – no scenario within the failing limit, enlarge sections')
    for name, sc in (('S0 no failing column', s0), ('S10 ≤ 10 % failing', s10), ('S25 ≤ 25 % failing, fewest under-used', s25)):
        if sc:
            tags.setdefault(sc['id'], []).append(name)
    if rec:
        tags.setdefault(rec['id'], []).append('RECOMMENDED')
    for sc in scs:
        sc['tags'] = tags.get(sc['id'], [])
    # what-if list: tagged scenarios + every valid scenario within the 25 % limit (cheapest first when priced)
    if not c25:
        c25 = sorted(valid, key=lambda sc: (sc['max_fail_share'],) + order(sc))[:20]
    wi = [sc for sc in scs if sc['tags']] + sorted([sc for sc in c25 if not tags.get(sc['id'])],
                                                    key=lambda sc: (sc['cost_thb'] if sc['cost_thb'] is not None else 0,) + order(sc))
    return dict(rule=rule, hopeless=sorted(f'{a} {b}' for a, b in hopeless), scenarios=scs, whatif=[sc['id'] for sc in wi],
                s0=s0 and s0['id'], s10=s10 and s10['id'], s25=s25 and s25['id'], recommended=rec and rec['id'])


def from_state(outdir, prices=None, rule=None, log=None):
    """run the study on a finished run (state.pkl) – also for a run with fixed f'c (information / what-if)."""
    st = pickle.load(open(os.path.join(outdir, 'state.pkl'), 'rb'))
    res = json.load(open(os.path.join(outdir, 'results.json')))
    cfg = st['cfg']
    mat, det = cfg['materials'], cfg.get('detailing', {})
    fc_typ = mat['fc_typical']
    fcs = sorted({f for f in mat.get('fc_list', [210, 240, 280, 320, 400, 450, 500, 560, 600, 700]) if f >= fc_typ})
    approved = set(tuple(x) for x in cfg.get('approved_rho_over_6', []))
    basement = set(st.get('basement') or res.get('input_report', {}).get('basement_stories') or cfg.get('basement_stories', []))
    cache = DS.Cache()
    M = fc_matrix(cache, Grids(det), st['cols'], fcs, mat.get('fy', 5000), det.get('rho_max', 0.06), det.get('rho_ask', 0.08),
                  approved, basement, log)
    out = study(M, st['cols'], st['stories'], fc_typ, [f for f in fcs if f > fc_typ], dict(cfg.get('fc_rule') or {}, **(rule or {})),
                prices if prices is not None else cfg.get('prices'))
    out['current_fc_of'] = res['fc_of']
    json.dump(out, open(os.path.join(outdir, 'fc_study.json'), 'w'), ensure_ascii=False, indent=1)
    return out


def boq(outdir):
    """quantities of the final design (results.json + state.pkl): concrete m³ per f'c, longitudinal steel kg per bar size."""
    st = pickle.load(open(os.path.join(outdir, 'state.pkl'), 'rb'))
    res = json.load(open(os.path.join(outdir, 'results.json')))
    conc, steel = {}, {}
    for r in res['results']:
        As = r['nbar'] and DS._as((r['db'], tuple(r['counts'])))
        for q in r['per']:
            c = st['cols'].get((r['label'], q['story']))
            if not c:
                continue
            v, kg = _qty(c, dict(As=As))
            conc[q['fc']] = conc.get(q['fc'], 0.0) + v
            steel[r['db']] = steel.get(r['db'], 0.0) + kg
    return dict(concrete_m3={str(k): round(v, 3) for k, v in sorted(conc.items())},
                steel_kg={str(k): round(v, 1) for k, v in sorted(steel.items())})



# ======================================================================================== v1.5.0 (CEDA 27 Oct 2026)
RULE15 = dict(limits=[0.10, 0.15, 0.20, 0.25], fc_max=700, share_low=0.50, rho_low=0.015, dc_min=0.75, dc_low=0.50,
              exempt_rho=0.015, rho_max=0.06, rho_ask=0.07)


def cases(M, cols, stories, fc_typ, fc_hi, rule=None, prices=None, cache=None, grids=None, fy=5000.0):
    """v1.5.0 case table (designer rule 27 Oct 2026); v1.5.1: first row 'T' = typical f'c in every story. f'c candidates = development-table values above the typical f'c up to
    fc_max; every column-story at ρ <= 6 % (no approvals in the study). For each candidate fb:
      case A = lowest reduction story where every story has failing <= max(limit × columns, 1) for the largest limit;
               its `lim` = the smallest limit it satisfies;
      case B = lowest reduction story with no failing column above the reduction (typical-f'c stories);
    the reduction story needs >= share_low of its columns at ρ <= rho_low with the typical f'c. Stop when B has 0 failing or
    fb = fc_max. Failing split: 'rho' (passes with ρ <= rho_ask, approval) / 'enlarge' / 'never' (fails at fc_max even with
    rho_ask). Under-use (information): f'c-overstrength = high-f'c column-story with D/C < dc_min that passes with
    D/C >= dc_min at the typical f'c (count + % of the high-f'c concrete volume); low D/C = % of the checked column-stories
    (all except typical f'c with ρ <= exempt_rho) with D/C < dc_low and dc_low–dc_min. Quantities as `scenario`."""
    rule = dict(RULE15, **(rule or {}))
    fcs = [f for f in sorted(fc_hi) if f <= rule['fc_max'] + 1e-9]
    AP = {}

    def r_ap(lab, s, fc):
        k = (lab, s, fc)
        if k not in AP:
            x = try_column(cache, grids, cols[(lab, s)], fc, fy, rule['rho_ask'], True) if cache is not None else dict(ok=False, dc=9, nbar=0, db=0, rho=0)
            AP[k] = dict(ok=x['ok'], dc=round(float(x['dc']), 3), bars=f"{x['nbar']}-DB{x['db']}", rho=round(float(x['rho']) * 100, 2))
        return AP[k]
    fmax = fcs[-1] if fcs else fc_typ
    never = {k for k, v in M.items() if not v[fmax]['ok'] and not r_ap(k[0], k[1], fmax)['ok']}
    n_of, low_of = {}, {}
    for (lab, s), c in cols.items():
        n_of[s] = n_of.get(s, 0) + 1
        x = M[(lab, s)][fc_typ]
        if x['ok'] and x['rho'] <= rule['rho_low'] + 1e-9:
            low_of[s] = low_of.get(s, 0) + 1
    okr = [r for r in stories[1:] if n_of.get(r) and low_of.get(r, 0) / n_of[r] >= rule['share_low'] - 1e-9]

    def one(fb, r):
        ri = stories.index(r)
        fc_of = {s: (fb if i < ri else fc_typ) for i, s in enumerate(stories)}
        per = {s: 0 for s in n_of}
        conc, steel = {}, {}
        fails, n = [], dict(rho=0, enlarge=0, never=0)
        fcov, fcov_v, hi_v, chk, low50, low75, lows = [], 0.0, 0.0, 0, 0, 0, []
        for (lab, s), c in cols.items():
            fc = fc_of[s]; x = M[(lab, s)][fc]
            v, kg = _qty(c, x)
            conc[fc] = conc.get(fc, 0.0) + v
            steel[x['db']] = steel.get(x['db'], 0.0) + kg
            if fc > fc_typ:
                hi_v += v
            if not x['ok']:
                per[s] += 1
                kind = 'never' if (lab, s) in never else ('rho' if r_ap(lab, s, fc)['ok'] else 'enlarge')
                n[kind] += 1
                fails.append(dict(label=lab, story=s, fc=fc, kind=kind, dc=round(float(x['dc']), 3), rho=round(float(x['rho']) * 100, 2),
                                  bars=f"{x.get('nbar', '?')}-DB{x.get('db', '?')}", ap=r_ap(lab, s, fc)))
                continue
            if fc == fc_typ and x['rho'] <= rule['exempt_rho'] + 1e-9:
                continue
            chk += 1
            if x['dc'] < rule['dc_min']:
                if x['dc'] < rule['dc_low']:
                    low50 += 1
                else:
                    low75 += 1
                lows.append(dict(label=lab, story=s, fc=fc, dc=round(float(x['dc']), 3), rho=round(float(x['rho']) * 100, 2)))
                if fc > fc_typ:
                    t = M[(lab, s)][fc_typ]
                    if (not t['ok']) or t['dc'] >= rule['dc_min']:
                        fcov.append(f'{lab} {s}'); fcov_v += v
        chk += 0
        above = sum(per[s] for s in stories[ri:] if s in per)
        ms = max((per[s] / n_of[s] for s in n_of if n_of[s]), default=0.0)
        lim = next((L for L in rule['limits'] if all(per[s] <= max(L * n_of[s], 1) + 1e-9 for s in n_of)), None)
        sc = dict(fc_bottom=fb, reduce_at=r, fc_of=fc_of, n_fail=len(fails), n_rho=n['rho'], n_enlarge=n['enlarge'], n_never=n['never'],
                  fails=sorted(fails, key=lambda f: (stories.index(f['story']), f['label'])), above=above, max_fail_share=ms, lim=lim,
                  fcov_n=len(fcov), fcov_pct=(fcov_v / hi_v * 100) if hi_v else 0.0, fcov=sorted(fcov),
                  checked=chk + len(fails), low50_pct=(low50 / (chk + len(fails)) * 100) if chk else 0.0,
                  low75_pct=(low75 / (chk + len(fails)) * 100) if chk else 0.0, lows=lows,
                  concrete_m3={str(k): round(v, 3) for k, v in sorted(conc.items())},
                  steel_kg={str(k): round(v, 1) for k, v in sorted(steel.items())},
                  hi_m3=round(hi_v, 1), typ_m3=round(sum(v for k, v in conc.items() if k <= fc_typ), 1),
                  share_low_at_reduction=low_of.get(r, 0) / n_of[r] if n_of.get(r) else None)
        sc['steel_t'] = round(sum(sc['steel_kg'].values()) / 1000, 1)
        sc['cost_thb'], sc['cost_missing'] = cost(sc, prices)
        return sc
    out = []
    # v1.5.1 (CEDA 28 Oct 2026): first row = the typical f'c in every story ('T') – ALWAYS in the table, also when its failing
    # exceed every limit (lim = None, shown for comparison; CEDA rule 28 Oct 2026). When raising f'c does not cut the failing
    # columns (e.g. small columns that fail with any f'c), this row is the recommended one and the failing go to the fix board.
    T = one(fc_typ, stories[0])
    T.update(type='T', reduce_at=None, share_low_at_reduction=None, above=T['n_fail'])
    out.append(T)
    for fb in (fcs if T['n_fail'] else []):
        rows = [one(fb, r) for r in okr]
        a = [c for c in rows if c['lim'] is not None]
        A = min(a, key=lambda c: stories.index(c['reduce_at'])) if a else None
        B = next((c for c in rows if c['above'] == 0), None)
        if A and B and A['reduce_at'] == B['reduce_at']:
            A['type'] = 'A=B'; out.append(A)
        else:
            if A:
                A['type'] = 'A'; out.append(A)
            if B:
                B['type'] = 'B'; out.append(B)
        if B and B['n_fail'] == 0:
            break
    for i, c in enumerate(out):
        c['id'] = i
    rec = {}
    for L in rule['limits']:
        c = next((c for c in out if c['type'] in ('T', 'A', 'A=B') and c['lim'] is not None and c['lim'] <= L + 1e-9), None)
        if c is not None:
            rec[str(int(round(L * 100)))] = c['id']
    recommended = rec.get(str(int(round(rule['limits'][0] * 100)))) if rec else None
    if recommended is None and rec:
        recommended = list(rec.values())[0]
    if recommended is None and out:                       # nothing within the limits: fewest failing
        recommended = min(out, key=lambda c: (c['n_fail'], c['fc_bottom']))['id']
    return dict(version='1.5.1', rule=rule, never=sorted(f'{a} {b}' for a, b in never), reduction_ok=okr, cases=out, rec=rec,
                recommended=recommended, fc_typical=fc_typ)


def cases_from_state(outdir, prices=None, rule=None, log=None):
    """v1.5.0 case table on a finished run (state.pkl) – no workbook approvals, ρ <= 6 % for all."""
    st = pickle.load(open(os.path.join(outdir, 'state.pkl'), 'rb'))
    res = json.load(open(os.path.join(outdir, 'results.json')))
    cfg = st['cfg']
    mat, det = cfg['materials'], cfg.get('detailing', {})
    fc_typ = mat['fc_typical']
    rule = dict(cfg.get('fc_rule15') or {}, **(rule or {}))
    rule.setdefault('rho_ask', det.get('rho_ask', 0.07))
    fcs = sorted({f for f in mat.get('fc_list', [210, 240, 280, 320, 400, 450, 500, 560, 600, 700]) if f >= fc_typ})
    basement = set(st.get('basement') or res.get('input_report', {}).get('basement_stories') or cfg.get('basement_stories', []))
    cache, grids = DS.Cache(), Grids(det)
    M = fc_matrix(cache, grids, st['cols'], fcs, mat.get('fy', 5000), det.get('rho_max', 0.06), det.get('rho_ask', 0.07),
                  set(), basement, log)
    out = cases(M, st['cols'], st['stories'], fc_typ, [f for f in fcs if f > fc_typ], rule,
                prices if prices is not None else cfg.get('prices'), cache, grids, mat.get('fy', 5000))
    out['current_fc_of'] = res['fc_of']
    json.dump(out, open(os.path.join(outdir, 'fc_cases.json'), 'w'), ensure_ascii=False, indent=1)
    return out

if __name__ == '__main__':
    pr = json.load(open(sys.argv[2])) if len(sys.argv) > 2 else None
    o = from_state(sys.argv[1], pr, log=print)
    for i in o['whatif'][:12]:
        sc = o['scenarios'][i]
        print(f"{sc['fc_bottom']:>4} / {sc['reduce_at'] or '-':>5}  fail {sc['n_fail']:>3} (max {sc['max_fail_share']:.0%})  "
              f"under-used {sc['n_under']:>4}  cost {sc['cost_thb']}  {', '.join(sc['tags'])}")
