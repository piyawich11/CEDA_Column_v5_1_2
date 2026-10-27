"""Read ETABS table exports (Excel) and assemble CEDA column design forces.

Normalised force row (dict):  label, story, combo, kind ('gravity'|'seismic'|'wind'|'other'), model, station (cm),
  P (kg, +compression), M2, M3 (kg-m, ETABS signs), V2, V3 (kg), src ('etabs'|'basement').

Agreed CEDA load method (Rev.1):
  * gravity part : gravity combos of the FULL model, reduced AND unreduced stiffness (both kept).
  * seismic part (above ground) : EQ combos of the SEISMIC model (gravity combos of the seismic model are dropped).
  * basement (stories not in the seismic model) for every EQ combo:
        P = P at the base of the lowest above-ground column (seismic model, same combo)
            + Σ factor_i · [P_i(bottom of this basement column) − P_i(bottom of lowest above-ground column)]
              (i = DL / SDL / LL load cases, full model with reduced stiffness; factors from the combo definition)
        M, V = the larger of (value carried down from the lowest above-ground column bottom, pinned base)
               and Σ factor_i · (DL/SDL/LL value of the basement column)
  * keep the sign of P (tension checked as tension); combos identified from Load Combination Definitions
    (not from their names); Step Type Max/Min kept as separate rows.
"""
import re, math
import openpyxl

FORCE = {'tonf': 1000.0, 'tf': 1000.0, 'kgf': 1.0, 'kg': 1.0, 'kn': 101.9716, 'n': 0.1019716, 'kip': 453.5924, 'lb': 0.4535924,
         'mn': 101971.6}
LEN = {'m': 100.0, 'cm': 1.0, 'mm': 0.1, 'in': 2.54, 'ft': 30.48}


def _norm(s):
    return re.sub(r'[^a-z0-9]', '', str(s or '').lower())


def unit_factor(u, kind):
    """factor to kg (force), cm (length) or kg-m (moment)."""
    u = str(u or '').strip().lower().replace(' ', '')
    if not u:
        return 1.0
    if kind == 'length':
        return LEN.get(u, 1.0)
    if kind == 'force':
        return FORCE.get(u, 1.0)
    if kind == 'moment':
        if '-' in u:
            f, l = u.split('-', 1)
            return FORCE.get(f, 1.0) * LEN.get(l, 100.0) / 100.0
    return 1.0


def read_tables(path):
    """all ETABS tables in a workbook -> {table name: list of dict rows (raw)}, units per table."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    out, units = {}, {}
    KNOWN = ('Point Object Connectivity', 'Column Object Connectivity', 'Frame Assignments - Section Properties',
             'Load Combination Definitions', 'Element Forces - Columns', 'Grid Definitions - Grid Lines', 'Story Forces', 'Story Drifts')
    for ws in wb.worksheets:
        rows = list(ws.iter_rows(values_only=True))
        # v1.3.3: a sheet pasted without its 'TABLE:' title row – header in row 1, units in row 2; the table name is taken
        # from the sheet name (e.g. sheet 'Point Object Connectivity' with UniqueName / X / Y / Z)
        if rows and not any(r and r[0] is not None and str(r[0]).upper().startswith('TABLE:') for r in rows[:5]):
            nm = next((k for k in KNOWN if _norm(k) == _norm(ws.title) or _norm(ws.title) in _norm(k)), None)
            if nm and rows[0] and all(isinstance(v, str) or v is None for v in rows[0]):
                rows = [('TABLE: ' + nm,)] + rows
        i = 0
        while i < len(rows):
            r = rows[i]
            c0 = str(r[0]) if r and r[0] is not None else ''
            if c0.upper().startswith('TABLE:'):
                name = c0.split(':', 1)[1].strip()
                hdr = [str(h).strip() if h is not None else '' for h in rows[i + 1]]
                urow = rows[i + 2] if i + 2 < len(rows) else []
                u = {hdr[j]: (urow[j] if j < len(urow) else '') for j in range(len(hdr)) if hdr[j]}
                data = []
                j = i + 3
                while j < len(rows):
                    rr = rows[j]
                    if rr and rr[0] is not None and str(rr[0]).upper().startswith('TABLE:'):
                        break
                    if rr and any(v is not None and v != '' for v in rr[:len(hdr)]):
                        data.append({hdr[k]: rr[k] for k in range(min(len(hdr), len(rr))) if hdr[k]})
                    j += 1
                out.setdefault(name, []).extend(data)
                units[name] = u
                i = j
            else:
                i += 1
    return out, units


def col(row, *names):
    """tolerant column lookup."""
    keys = {_norm(k): k for k in row}
    for n in names:
        k = keys.get(_norm(n))
        if k is not None:
            return row[k]
    return None


def find_table(tables, *names):
    nt = {_norm(k): k for k in tables}
    for n in names:
        if _norm(n) in nt:
            return tables[nt[_norm(n)]], nt[_norm(n)]
    for n in names:                                   # partial match
        for k in nt:
            if _norm(n) in k:
                return tables[nt[k]], nt[k]
    return None, None


# ------------------------------------------------------------------------------------------------ combos
GRAV_DEFAULT = {'DL': ['DL', 'D', 'DEAD', 'SW', 'SELFWEIGHT'], 'SDL': ['SDL', 'SIDL', 'SUPERDEAD'], 'LL': ['LL', 'L', 'LIVE', 'LR', 'LLR']}


def combo_factors(tables, gravity_names=None):
    """{combo: {load case: factor}} resolved through nested combos, plus combo kind."""
    t, _ = find_table(tables, 'Load Combination Definitions')
    if not t:
        return {}, {}
    raw = {}
    cur = None
    for r in t:
        name = col(r, 'Name', 'Combo') or cur
        cur = name
        ld = col(r, 'Load Name', 'Case/Combo Name', 'LoadName')
        sf = col(r, 'SF', 'Scale Factor')
        if ld is None or sf is None:
            continue
        raw.setdefault(name, []).append((str(ld), float(sf)))

    def resolve(name, depth=0):
        out = {}
        for ld, sf in raw.get(name, []):
            if ld in raw and depth < 10:
                for k, v in resolve(ld, depth + 1).items():
                    out[k] = out.get(k, 0.0) + sf * v
            else:
                out[ld] = out.get(ld, 0.0) + sf
        return out
    gn = gravity_names or GRAV_DEFAULT
    allg = {_norm(x): g for g, xs in gn.items() for x in xs}
    fac, kind = {}, {}
    for c in raw:
        f = resolve(c)
        fac[c] = f
        cats = set(allg.get(_norm(k), 'other') for k in f)
        if cats <= {'DL', 'SDL', 'LL'}:
            kind[c] = 'gravity'
        elif any(re.search(r'(^|[^a-z])(w|wx|wy|wind)', k.lower()) for k in f if allg.get(_norm(k)) is None):
            kind[c] = 'wind'
        else:
            kind[c] = 'seismic'
    return fac, kind


def check_combos(fac, kind, gravity_names=None, tol=0.002):
    """compare combo factors with กฎกระทรวง พ.ศ. 2566 ข้อ 7 (SDL counted as dead load)."""
    gn = gravity_names or GRAV_DEFAULT
    allg = {_norm(x): g for g, xs in gn.items() for x in xs}
    rep = []
    for c, f in fac.items():
        D = [v for k, v in f.items() if allg.get(_norm(k)) in ('DL', 'SDL')]
        L = [v for k, v in f.items() if allg.get(_norm(k)) == 'LL']
        E = [v for k, v in f.items() if allg.get(_norm(k)) is None]
        d = D[0] if D and max(D) - min(D) < tol else (D or [0])
        l = L[0] if L else 0.0
        ok = False
        if kind[c] == 'gravity':
            ok = isinstance(d, float) and abs(d - 1.4) < tol and abs(l - 1.7) < tol
            exp = '1.4D + 1.7L (ข้อ 7(1))'
        elif kind[c] == 'seismic':
            okE = all(abs(abs(e) - 1.0) < tol for e in E)
            ok = isinstance(d, float) and okE and ((abs(d - 1.05) < tol and abs(l - 1.275) < tol) or (abs(d - 0.9) < tol and abs(l) < tol))
            exp = '0.75(1.4D + 1.7L) + 1.0E or 0.9D + 1.0E (ข้อ 7(3))'
        else:
            okW = all(abs(abs(e) - 1.6) < tol for e in E)
            ok = isinstance(d, float) and okW and ((abs(d - 1.05) < tol and abs(l - 1.275) < tol) or (abs(d - 0.9) < tol and abs(l) < tol))
            exp = '0.75(1.4D + 1.7L) + 1.6W or 0.9D + 1.6W (ข้อ 7(2))'
        rep.append(dict(combo=c, kind=kind[c], factors=f, ok=ok, expected=exp))
    return rep


# ------------------------------------------------------------------------------------------------ geometry
def geometry(tables, units):
    """column label/story -> dict(x, y, zb, zt, L (cm), uname, section)."""
    pts_t, pn = find_table(tables, 'Point Object Connectivity')
    col_t, cn = find_table(tables, 'Column Object Connectivity')
    sec_t, sn = find_table(tables, 'Frame Assignments - Section Properties', 'Frame Assignments - Summary')
    geo = {}
    if pts_t:
        uL = unit_factor(units[pn].get('X', 'm'), 'length')
        P = {str(col(r, 'Unique Name', 'UniqueName')): (float(col(r, 'X')) * uL, float(col(r, 'Y')) * uL, float(col(r, 'Z')) * uL)
             for r in pts_t if col(r, 'X') is not None}
    else:
        P = {}
    if col_t:
        uL = unit_factor(units[cn].get('Length', 'm'), 'length')
        for r in col_t:
            lab = str(col(r, 'Column Bay', 'ColumnBay', 'Label', 'Column'))
            st = str(col(r, 'Story'))
            pi, pj = str(col(r, 'UniquePtI', 'Unique Pt I', 'Point I')), str(col(r, 'UniquePtJ', 'Unique Pt J', 'Point J'))
            Lr = col(r, 'Length')
            g = dict(uname=str(col(r, 'Unique Name', 'UniqueName')))
            if pi in P and pj in P:
                (x1, y1, z1), (x2, y2, z2) = P[pi], P[pj]
                g.update(x=(x1 + x2) / 2, y=(y1 + y2) / 2, zb=min(z1, z2), zt=max(z1, z2), L=abs(z2 - z1))
                hz = math.hypot(x2 - x1, y2 - y1)                       # v1.5.1: inclination from vertical (braces)
                g['tilt'] = round(math.degrees(math.atan2(hz, abs(z2 - z1))), 1) if (hz or z2 != z1) else 0.0
            if Lr is not None:
                g['L'] = float(Lr) * uL
            geo[(lab, st)] = g
    if sec_t:
        for r in sec_t:
            lab = str(col(r, 'Label', 'Column Bay')); st = str(col(r, 'Story'))
            s = col(r, 'Section Property', 'Analysis Section', 'Design Section', 'Section')
            if (lab, st) in geo and s is not None:
                geo[(lab, st)]['section'] = str(s)
    return geo


def sections(tables, units):
    """section name -> dict(shape, t3, t2) in cm (t3 = depth along local 2, t2 = width)."""
    out = {}
    t, n = find_table(tables, 'Frame Section Property Definitions - Concrete Rectangular', 'Frame Props 02 - Concrete Rectangular')
    if t:
        uL = unit_factor(units[n].get('Depth', 'm'), 'length')
        for r in t:
            out[str(col(r, 'Name'))] = dict(shape='rect', t3=float(col(r, 'Depth', 't3')) * uL, t2=float(col(r, 'Width', 't2')) * uL)
    t, n = find_table(tables, 'Frame Section Property Definitions - Concrete Circle', 'Frame Props 03 - Concrete Circle')
    if t:
        uL = unit_factor(units[n].get('Diameter', 'm'), 'length')
        for r in t:
            d = float(col(r, 'Diameter', 't3')) * uL
            out[str(col(r, 'Name'))] = dict(shape='circ', t3=d, t2=d)
    return out


STEEL_RE = re.compile(r'(^|[\s\-_(])(H|W|I|UB|UC|HSS|SHS|RHS|CHS|PIPE|TUBE|BOX|L|C|IPE|HEA|HEB)\s*\d+\s*[xX×]\s*\d+\s*[xX×]\s*\d+|'
                      r'\d+\s*[xX×]\s*\d+\s*[xX×]\s*\d+\s*[xX×]\s*\d+|^\s*(W|IPE|HE[ABM]|UB|UC)\s*\d+\s*[xX×]\s*\d+|\b(steel|truss|brace|pipe|tube|hss)\b', re.I)


def non_rc(name, secs):
    """v1.5.1: why a frame section is NOT a reinforced-concrete column (steel truss, brace, pipe …), else None.
    Only a section that is missing from the concrete section tables AND has a steel name is excluded (a concrete section whose
    table was not exported, e.g. a circle, still falls back to its name as before)."""
    if not name or str(name) in (secs or {}):
        return None
    if STEEL_RE.search(str(name)):
        return 'steel section (name, not in the concrete section tables)'
    return None


def section_from_name(name):
    """fallback: 'C 2000x450' -> t3 = 200, t2 = 45 cm (ASSUMPTION: first number = t3); 'CC 800' -> circle."""
    m = re.search(r'(\d+)\s*[xX×]\s*(\d+)', str(name))
    if m:
        return dict(shape='rect', t3=float(m.group(1)) / 10, t2=float(m.group(2)) / 10, assumed=True)
    m = re.search(r'(\d{3,4})', str(name))
    if m:
        return dict(shape='circ', t3=float(m.group(1)) / 10, t2=float(m.group(1)) / 10, assumed=True)
    return None


# ------------------------------------------------------------------------------------------------ forces
def column_forces(tables, units, model):
    t, n = find_table(tables, 'Element Forces - Columns')
    if not t:
        return []
    u = units[n]
    fP = unit_factor(u.get('P', 'tonf'), 'force')
    fV = unit_factor(u.get('V2', 'tonf'), 'force')
    fM = unit_factor(u.get('M2', 'tonf-m'), 'moment')
    fS = unit_factor(u.get('Station', 'm'), 'length')
    out = []
    for r in t:
        P = col(r, 'P')
        if P is None:
            continue
        out.append(dict(label=str(col(r, 'Column', 'Label')), story=str(col(r, 'Story')), uname=str(col(r, 'Unique Name')),
                        combo=str(col(r, 'Output Case')), ctype=str(col(r, 'Case Type') or ''), step=str(col(r, 'Step Type', 'StepType') or ''),
                        station=float(col(r, 'Station') or 0) * fS, P=-float(P) * fP,
                        V2=float(col(r, 'V2') or 0) * fV, V3=float(col(r, 'V3') or 0) * fV,
                        M2=float(col(r, 'M2') or 0) * fM, M3=float(col(r, 'M3') or 0) * fM, model=model, src='etabs'))
    return out


def story_order(geo):
    """stories sorted bottom -> top. v1.5.1: by the story top (median column top = the ETABS story elevation), then the lowest
    column bottom – stories that share a bottom level (partial-height stories, e.g. MDB +2.80 / Mezzanine +3.50 / 2 FL +6.95 all
    from +0.65) come out in elevation order instead of an arbitrary one."""
    zb, zt = {}, {}
    for (lab, st), g in geo.items():
        if 'zb' in g:
            zb[st] = min(zb.get(st, 1e18), g['zb'])
            zt.setdefault(st, []).append(g['zt'])
    top = {s: sorted(v)[len(v) // 2] for s, v in zt.items()}
    return sorted(zb, key=lambda s: (top[s], zb[s]))


def match_labels(geo_a, geo_b, tol=5.0):
    """map (label, story) of model b to model a by label and XY (cm). Unique names may differ."""
    m = {}
    for k, gb in geo_b.items():
        if k in geo_a and ('x' not in gb or math.hypot(geo_a[k].get('x', 0) - gb.get('x', 0), geo_a[k].get('y', 0) - gb.get('y', 0)) < tol):
            m[k] = k
            continue
        for ka, ga in geo_a.items():
            if ka[1] == k[1] and 'x' in ga and 'x' in gb and math.hypot(ga['x'] - gb['x'], ga['y'] - gb['y']) < tol:
                m[k] = ka
                break
    return m


def assemble(seis, full_red, full_unred, gravity_names=None, designer_order=None):
    """seis/full_red/full_unred: dicts with keys tables, units. Returns rows, report dict."""
    rep = {}
    story_order_in = designer_order
    gn = gravity_names or GRAV_DEFAULT
    allg = {_norm(x): g for g, xs in gn.items() for x in xs}
    out = []
    # combos
    facS, kindS = combo_factors(seis['tables'], gn)
    facF, kindF = combo_factors(full_red['tables'], gn)
    rep['combo_check_seismic'] = check_combos(facS, kindS, gn)
    rep['combo_check_full'] = check_combos(facF, kindF, gn)
    geoS = geometry(seis['tables'], seis['units'])
    geoF = geometry(full_red['tables'], full_red['units'])
    rep['stories_full'] = story_order(geoF)
    rep['stories_seismic'] = story_order(geoS)
    if story_order_in and (not rep['stories_full'] or not rep['stories_seismic']):
        # v1.3.1: no Z (Point Object Connectivity not exported) -> designer story order, so the basement is still assembled
        rep['stories_full'] = [s for s in story_order_in if any(k[1] == s for k in geoF)]
        rep['stories_seismic'] = [s for s in story_order_in if any(k[1] == s for k in geoS)]
        rep['story_order_source'] = 'designer story_order (no Z in the export)'
    mapS = match_labels(geoF, geoS)
    # gravity part (full models)
    for mdl, tag in ((full_red, 'full-reduced'), (full_unred, 'full-unreduced')):
        if mdl is None:
            continue
        fac, kind = combo_factors(mdl['tables'], gn)
        for r in column_forces(mdl['tables'], mdl['units'], tag):
            if kind.get(r['combo']) == 'gravity':
                r['kind'] = 'gravity'; out.append(r)
    # seismic part (seismic model, EQ combos only)
    seisrows = []
    for r in column_forces(seis['tables'], seis['units'], 'seismic'):
        k = kindS.get(r['combo'])
        if k in ('seismic', 'wind'):
            key = mapS.get((r['label'], r['story']), (r['label'], r['story']))
            r['label'], r['story'] = key
            r['kind'] = k
            seisrows.append(r)
    out += seisrows
    # basement
    sf, ss = rep['stories_full'], set(rep['stories_seismic'])
    above = [s for s in sf if s in ss]
    base = [s for s in sf if s not in ss and (not above or sf.index(s) < sf.index(above[0]))]
    rep['basement_stories'] = base
    if base and above:
        low = above[0]
        # load-case forces of the full reduced model
        cases = {}
        for r in column_forces(full_red['tables'], full_red['units'], 'full-reduced'):
            g = allg.get(_norm(r['combo']))
            if g:
                cases.setdefault((r['label'], r['story'], r['combo']), []).append(r)

        def bottom(rows):
            return min(rows, key=lambda q: q['station']) if rows else None

        def case_val(lab, st, case, key, at_bottom=True):
            rows = cases.get((lab, st, case))
            if not rows:
                return 0.0
            if key == 'P':
                return bottom(rows)['P']
            return max((q[key] for q in rows), key=abs)
        # seismic rows at the base of the lowest above-ground story, per label/combo/step
        top_rows = {}
        for r in seisrows:
            if r['story'] == low:
                k = (r['label'], r['combo'], r['step'])
                if k not in top_rows or r['station'] < top_rows[k]['station']:
                    top_rows[k] = r
        for (lab, combo, step), rt in top_rows.items():
            f = facS.get(combo, {})
            for st in base:
                if (lab, st) not in geoF:
                    continue
                P = rt['P']
                vals = {}
                for case, fc in f.items():
                    if allg.get(_norm(case)) is None:
                        continue
                    P += fc * (case_val(lab, st, case, 'P') - case_val(lab, low, case, 'P'))
                for key in ('M2', 'M3', 'V2', 'V3'):
                    grav = sum(fc * case_val(lab, st, case, key) for case, fc in f.items() if allg.get(_norm(case)))
                    vals[key] = rt[key] if abs(rt[key]) >= abs(grav) else grav
                out.append(dict(label=lab, story=st, uname='', combo=combo, ctype='Combination', step=step, station=0.0,
                                P=P, model='basement', src='basement', kind='seismic', **vals))
    rep['n_rows'] = len(out)
    return out, rep


_BD_CACHE = {}


def beta_d(full_red, label, story, gravity_names=None):
    """βd = [1.4(DL+SDL) + 0.25·1.7 LL] / [1.4(DL+SDL) + 1.7 LL] (Rev.1, conservative) from load-case P at the column bottom."""
    gn = gravity_names or GRAV_DEFAULT
    allg = {_norm(x): g for g, xs in gn.items() for x in xs}
    s = {'DL': 0.0, 'SDL': 0.0, 'LL': 0.0}
    key = id(full_red['tables'])
    if key not in _BD_CACHE:                          # v1.3.1: index the forces once (was re-read per column-story)
        idx = {}
        for r in column_forces(full_red['tables'], full_red['units'], 'full-reduced'):
            idx.setdefault((r['label'], r['story']), []).append(r)
        _BD_CACHE.clear(); _BD_CACHE[key] = idx
    rows = [r for r in _BD_CACHE[key].get((label, story), []) if allg.get(_norm(r['combo']))]
    if not rows:
        return None
    for case in set(r['combo'] for r in rows):
        rr = [r for r in rows if r['combo'] == case]
        s[allg[_norm(case)]] += min(rr, key=lambda q: q['station'])['P']
    D, L = s['DL'] + s['SDL'], s['LL']
    den = 1.4 * D + 1.7 * L
    return (1.4 * D + 0.425 * L) / den if den > 0 else None


def sway_Q(tables, units, kind, story_h):
    """stability index Q = ΣPu·Δo / (Vus·lc) per story/direction for EQ/wind combos (ACI 6.6.4.4.1).
    story_h: {story: height cm}. Returns list of dicts."""
    tf, nf = find_table(tables, 'Story Forces')
    td, nd = find_table(tables, 'Story Drifts')
    if not tf or not td:
        return []
    fF = unit_factor(units[nf].get('P', 'tonf'), 'force')
    F = {}
    for r in tf:
        if str(col(r, 'Location') or '').lower().startswith('bot'):
            F[(str(col(r, 'Story')), str(col(r, 'Output Case')), str(col(r, 'Step Type') or ''))] = (
                abs(float(col(r, 'P') or 0)) * fF, abs(float(col(r, 'VX') or 0)) * fF, abs(float(col(r, 'VY') or 0)) * fF)
    out = []
    for r in td:
        c = str(col(r, 'Output Case'))
        if kind.get(c) not in ('seismic', 'wind'):
            continue
        st = str(col(r, 'Story')); step = str(col(r, 'Step Type') or '')
        k = (st, c, step)
        if k not in F or st not in story_h:
            continue
        drift = abs(float(col(r, 'Drift') or 0))
        d = str(col(r, 'Direction') or '').upper()
        P, VX, VY = F[k]
        V = VX if d.startswith('X') else VY
        if V <= 0:
            continue
        lc = story_h[st]
        Q = P * drift * lc / (V * lc)
        out.append(dict(story=st, combo=c, step=step, dir=d, Q=Q, sway=Q > 0.05))
    return out
