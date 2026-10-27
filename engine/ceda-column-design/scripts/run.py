"""CEDA column design – main driver.

usage:  python3 -I run.py config.json OUTDIR
config: see SKILL.md (project, seismic, materials, detailing, slender, lap_table, inputs ...).
Writes OUTDIR/results.json, OUTDIR/<job>_Column_Decision.xlsx and returns quickly; drawings/calcs are made by
make_outputs.py from results.json.
"""
import sys, os, json, math, pickle, collections
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import etabs_io as E
import layout as LY
import design as DS

FC_STD = [210, 240, 280, 320, 400, 450, 500, 560, 600, 700]


def load_inputs(cfg, base):
    rep = {}
    inp = cfg['inputs']
    gn = cfg.get('gravity_cases')
    if 'forces_json' in inp:                                   # normalised rows (tests / adapters)
        data = json.load(open(os.path.join(base, inp['forces_json'])))
        return data['rows'], data.get('geometry', {}), data.get('stories'), {}, None
    rd = lambda k: dict(zip(('tables', 'units'), E.read_tables(os.path.join(base, inp[k])))) if inp.get(k) else None
    S, FR, FU = rd('seismic'), rd('full_reduced'), rd('full_unreduced')
    rows, rep = E.assemble(S, FR, FU, gn, cfg.get('story_order'))
    excl = set(cfg.get('exclude_combos', []))
    rows = [q for q in rows if q['combo'] not in excl]
    geo = E.geometry(FR['tables'], FR['units'])
    # sway check (ACI 6.6.4.3) from the seismic model story tables, if exported
    gS = E.geometry(S['tables'], S['units'])
    sh = {}
    for (lab, st), g in gS.items():
        if 'L' in g:
            sh.setdefault(st, []).append(g['L'])
    sh = {k: sorted(v)[len(v) // 2] for k, v in sh.items()}
    facS, kindS = E.combo_factors(S['tables'], gn)
    rep['sway'] = E.sway_Q(S['tables'], S['units'], kindS, sh)
    secs = E.sections(FR['tables'], FR['units'])
    for k, g in geo.items():
        s = g.get('section')
        if s:
            why = E.non_rc(s, secs)                   # v1.5.1: steel truss / brace members are not designed as RC columns
            if why:
                g['non_rc'] = why
            else:
                g['dims'] = secs.get(s) or E.section_from_name(s)
    return rows, {f'{k[0]}|{k[1]}': v for k, v in geo.items()}, rep['stories_full'], rep, FR


def story_rank(s):
    """natural order of story names when ETABS connectivity is missing: B6 < … < B1 < GF/0.00 < 1st < 2F … < Roof."""
    import re as _re
    t = str(s).strip().upper()
    m = _re.match(r'^B(\d+)', t)
    if m:
        return -int(m.group(1))
    if t.startswith(('ROOF', 'RF', 'TOP')):
        return 10000
    m = _re.match(r'^(\d+(?:\.\d+)?)', t)
    if m:
        return float(m.group(1))
    if t in ('GF', 'G', 'GROUND'):
        return 0
    return 5000


def dwg_level(stories, s):
    i = stories.index(s)
    return (stories[i - 1] if i > 0 else 'FDN', s)


def main(cfg_path, outdir):
    cfg = json.load(open(cfg_path))
    base = os.path.dirname(os.path.abspath(cfg_path))
    os.makedirs(outdir, exist_ok=True)
    mat, det, sl = cfg['materials'], cfg.get('detailing', {}), cfg.get('slender', {})
    fy = mat.get('fy', 5000)
    cover = det.get('cover_mm', 40); tie_db = det.get('tie_db', 12)
    sizes = det.get('bar_sizes', [12, 16, 20, 25, 28, 32]); kmax = det.get('kmax', 4)
    cc = tuple(det.get('cc', [125, 150]))
    small = tuple(tuple(x) for x in det.get('small_face', LY.SMALL_FACE))
    rho_max, rho_ask = min(det.get('rho_max', 0.06), 0.06), min(det.get('rho_ask', 0.07), 0.08)     # v1.5.0: approval limit ≤ 8 % (ACI 318-19 §10.6.1.1)
    approved = set(tuple(x) for x in cfg.get('approved_rho_over_6', []))
    frame = cfg.get('seismic', {}).get('frame', 'gravity')
    if str(frame).upper() == 'SMF' or 'SPECIAL MOMENT' in str(cfg.get('seismic', {}).get('system', '')).upper():
        rho_max = rho_ask = 0.06; approved = set()                  # ACI 318-19 §18.7.4.1 – no approval above 6 %
    det = dict(det, rho_max=rho_max, rho_ask=rho_ask)
    rows, geo, stories, rep_in, FR = load_inputs(cfg, base)
    notes = []
    non_rc = {tuple(k.split('|', 1)): g for k, g in geo.items() if g.get('non_rc')}
    if non_rc:                                        # v1.5.1: excluded before anything is designed, listed for the designer
        rows = [r for r in rows if (r['label'], r['story']) not in non_rc]
        bysec = collections.Counter(g.get('section') for g in non_rc.values())
        notes.append(f"EXCLUDED – not RC columns ({len(non_rc)} column objects, design them separately): "
                     + '; '.join(f'{s_} ×{n}' for s_, n in bysec.most_common(6)) + ' – ' + next(iter(non_rc.values()))['non_rc'])
        stories = [s_ for s_ in stories if any(r['story'] == s_ for r in rows)] if stories else stories
    for c in rep_in.get('combo_check_seismic', []) + rep_in.get('combo_check_full', []):
        if not c['ok'] and c['combo'] not in cfg.get('exclude_combos', []):
            notes.append(f"combo {c['combo']} ({c['kind']}) factors {c['factors']} do not match {c['expected']} – confirm or exclude")
    sw = [q for q in rep_in.get('sway', []) if q['sway']]
    if sw:
        notes.append(f"SWAY: Q > 0.05 at {sorted(set(q['story'] for q in sw))} – δs (ACI 6.6.4.6) not automated: STOP and ask")
    elif FR is not None and not rep_in.get('sway'):
        if str(cfg.get('slender', {}).get('sway', '')).lower().startswith('non'):
            notes.append('sway (ACI 6.6.4.3): non-sway assumed by the engineer – Engineering judgment (Story Forces / Drifts not exported, Q not checked)')
        else:
            notes.append('sway check not done – export Story Forces + Story Drifts (seismic model)')
    if rep_in.get('basement_stories'):
        notes.append(f"basement stories assembled by the CEDA method: {rep_in['basement_stories']}")
    if frame == 'SMF':
        notes.append('SMF: ACI 18.7 detailing (Ash, s <= 6db, hx, strong column-weak beam) is NOT automated – design forces only.')
    # ---------------------------------------------------------------- group rows per column-story
    grp = collections.defaultdict(list)
    for r in rows:
        grp[(r['label'], r['story'])].append(r)
    if not stories:                                   # no connectivity exported: designer's story_order, else natural order
        so = cfg.get('story_order') or []
        stories = sorted(set(k[1] for k in grp), key=lambda s: (so.index(s), 0) if s in so else (len(so), story_rank(s)))
        notes.append('story order not from ETABS connectivity – ' + ('designer story_order used' if so else
                     'natural order of the story names used (ASSUMPTION – confirm)'))
    secs_cfg = cfg.get('sections', {})
    # v1.5.0: enlarged sections from the fix board – {(label, story): dims}; option 2 ranges relax the monotonic rule
    ov_sec, mono_ex = {}, set()
    for o in cfg.get('section_overrides', []):
        if o.get('story_from') not in stories or o.get('story_to') not in stories:
            notes.append(f"enlarge {o.get('label')}: stories {o.get('story_from')}–{o.get('story_to')} not found – ignored"); continue
        i0, i1 = sorted((stories.index(o['story_from']), stories.index(o['story_to'])))
        b_, h_ = float(o['b_mm']) / 10, float(o.get('h_mm') or o['b_mm']) / 10
        for s_ in stories[i0:i1 + 1]:
            if not o.get('in_etabs'):                  # round 2+: the size is in the ETABS export – only the option-2 rule stays
                ov_sec[(o['label'], s_)] = dict(shape=o.get('shape', 'rect'), b=b_, h=b_ if o.get('shape') == 'circ' else h_)
            if int(o.get('option', 2)) == 2:
                mono_ex.add((o['label'], s_))
        if o.get('in_etabs'):
            continue
        notes.append(f"ENLARGED {o['label']} {stories[i0]}–{stories[i1]}: {o.get('shape', 'rect')} {o['b_mm']:.0f}"
                     + ('' if o.get('shape') == 'circ' else f"×{float(o.get('h_mm') or o['b_mm']):.0f}")
                     + ' mm (fix board) – forces from the ETABS export with the old section until ETABS is re-run: PROVISIONAL')
    cols, grids, steps, jmin = {}, {}, {}, {}
    for (lab, st), rr in grp.items():
        g = geo.get(f'{lab}|{st}', {})
        d = ov_sec.get((lab, st)) or secs_cfg.get(lab) or g.get('dims')
        if d is None:
            notes.append(f'{lab} {st}: no section – skipped'); continue
        if d.get('assumed'):
            notes.append(f'{lab} {st}: section dims from name "{g.get("section")}" (ASSUMPTION: first number = t3)')
        shape = d.get('shape', 'rect')
        b, h = (d['b'], d['h']) if 'b' in d else (d['t2'], d['t3'])          # b = t2 (M2), h = t3 (M3)
        Lu = g.get('L')
        Hst = g.get('L')                                  # story height (column length) before Lu overrides
        k = sl.get('k', 1.0)
        for ov in sl.get('overrides', []):
            if st in ov.get('stories', []) and (not ov.get('labels') or lab in ov['labels']):
                Lu = ov.get('Lu_m', Lu / 100 if Lu else None) * 100 if ov.get('Lu_m') else Lu
                k = ov.get('k', k)
        if Lu is None:
            Lu = sl.get('Lu_default_m', 3.0) * 100
            notes.append(f'{lab} {st}: Lu not found – {Lu/100:.2f} m used')
        bd = sl.get('beta_d')
        if bd is None and FR is not None:
            bd = E.beta_d(FR, lab, st, cfg.get('gravity_cases'))
        if bd is None:
            bd = 0.6; notes.append(f'{lab} {st}: βd not available – 0.6 used (ASSUMPTION)')
        gkey = (shape, b, h)
        if gkey not in grids:
            dmin = DS.min_bar_size(shape, b * 10, h * 10)
            sz = [d for d in sizes if d >= dmin] or [max(sizes)]
            grids[gkey] = LY.Grid(b * 10, h * 10, cover, tie_db, max(sz), cc, shape, small)
            steps[gkey] = LY.ladder(grids[gkey], sz, kmax)
            Ag = math.pi * b ** 2 / 4 if shape == 'circ' else b * h
            jmin[gkey] = DS.pattern_step(steps[gkey], Ag, det.get('rho_min', 0.01))
        arr = {key: np.array([q.get(key, 0.0) for q in rr], float) for key in ('P', 'M2', 'M3', 'V2', 'V3')}
        cols[(lab, st)] = dict(label=lab, story=st, shape=shape, b=b, h=h, Lu=Lu, k=k, betad=bd, gkey=gkey, rows=arr, H=Hst or Lu,
                              meta=[dict(combo=q['combo'], step=q.get('step', ''), model=q.get('model', ''), station=q.get('station', 0)) for q in rr],
                              seis=np.array([q.get('kind') in ('seismic', 'wind') for q in rr]))
    stories = [s for s in stories if any(k[1] == s for k in cols)]
    cache = DS.Cache()
    # ---------------------------------------------------------------- f'c
    if 'fc_by_story' in mat:
        fc_of = {s: mat['fc_by_story'].get(s, mat['fc_typical']) for s in stories}
        fcinfo = dict(fixed=True)
    else:
        # v1.5.0 (CEDA 27 Oct 2026): case table A/B per f'c of the development table, rho <= 6 % for all (no approvals);
        # without a designer choice the recommended case of the first limit is used (the app always asks the designer)
        import fc_study as FS
        fc_typ = mat['fc_typical']
        fcs = sorted({f for f in mat.get('fc_list', FC_STD) if f >= fc_typ})
        bsm = set(rep_in.get('basement_stories') or cfg.get('basement_stories', []))
        gr = FS.Grids(det)
        M = FS.fc_matrix(cache, gr, cols, fcs, fy, rho_max, rho_ask, set(), bsm)
        rule = dict(cfg.get('fc_rule15') or {}, rho_max=rho_max, rho_ask=rho_ask)
        fst = FS.cases(M, cols, stories, fc_typ, [f for f in fcs if f > fc_typ], rule, cfg.get('prices'), cache, gr, fy)
        json.dump(_jsonable(fst), open(os.path.join(outdir, 'fc_cases.json'), 'w'), ensure_ascii=False, indent=1)
        if fst['recommended'] is None:
            fc_of = {s: fc_typ for s in stories}
            fcinfo = dict(fixed=False, case=None, never=fst['never'])
            notes.append("f'c study v1.5: no case – typical f'c used everywhere; enlarge sections")
        else:
            rec = fst['cases'][fst['recommended']]
            fc_of = dict(rec['fc_of'])
            fcinfo = dict(fixed=False, case=rec['id'], type=rec['type'], fc_bottom=rec['fc_bottom'], fc_typical=fc_typ,
                          reduce_at=rec['reduce_at'], n_fail=rec['n_fail'], never=fst['never'])
            notes.append(f"f'c study v1.5: case " + (f"typical {rec['fc_bottom']} ksc in every story (T)" if rec['type'] == 'T' else
                         f"{rec['fc_bottom']} / {rec['reduce_at']} ({rec['type']})") + f" used – {rec['n_fail']} failing "
                         f"column-stories go to the fix board; choose the case on the case table (fc_cases.json)")
    fcs = mat.get('fc_slab')
    if fcs:
        hi = [s for s in stories if fc_of[s] > 1.4 * fcs]          # story order (v1.3.3: was sorted by name)
        if hi:
            notes.append(f"ACI 15.5: column f'c > 1.4 × slab f'c ({fcs}) at {hi[0]}…{hi[-1]} – check joint (puddle / 15.5.2)")
    # ---------------------------------------------------------------- required step per label-story (CEDA v1.1)
    # 1 % pattern (positions from c/c 125-150, smallest bar by the long side) is the floor of every story;
    # bottom story: size up to DB32, then symmetric bundles at tie corners; going up: bundles first, then size.
    labels = sorted(set(k[0] for k in cols), key=lambda s: (len(s), s))
    # CEDA Oct 2026: singles / 2-bar bundles on the c/c 125-150 grid; 3-4-bar bundles may use a wider grid, c/c up to 160 mm
    cc_w = tuple(det.get('cc_bundle34', [125, 160]))

    def wide_key(gk):
        return tuple(gk[:3]) + ('W',)

    def make_grid(gk):
        if gk in grids:
            return gk
        shape_, b_, h_ = gk[:3]
        wide, inner = 'W' in gk[3:], 'I' in gk[3:]
        dmin = DS.min_bar_size(shape_, b_ * 10, h_ * 10)
        sz = [d for d in sizes if d >= dmin] or [max(sizes)]
        grids[gk] = LY.Grid(b_ * 10, h_ * 10, cover, tie_db, max(sz), cc_w if wide else cc, shape_, small)
        st_ = LY.ladder(grids[gk], sz, kmax)               # perimeter ladder (interior flag still off)
        if wide:
            st_ = [x for x in st_ if max(x[1]) >= 3]     # the wider grid only for arrangements with 3-4-bar bundles
            grids[gk].notes = [f'{shape_} {b_*10:.0f}×{h_*10:.0f} grid W: c/c up to {cc_w[1]:.0f} mm, used only with 3-4-bar bundles (CEDA Oct 2026)']
        if inner:                                        # v1.3.2: full perimeter + one bar at every inner-hoop crossing
            g_ = grids[gk]; g_.interior = True
            nin = len(g_.inner(st_[-1][0])) if st_ and shape_ != 'circ' else 0
            st_ = [(st_[-1][0], tuple(st_[-1][1]) + (1,) * nin, 3)] if nin else []
            g_.notes = [f'{shape_} {b_*10:.0f}×{h_*10:.0f} grid {"W" if wide else ""}I: {nin} inner bars at the tie crossings '
                        f'(CEDA pattern 20 Oct 2026 – last resort, basement compression / approved ρ only)']
        steps[gk] = st_
        Ag_ = math.pi * b_ ** 2 / 4 if shape_ == 'circ' else b_ * h_
        jmin[gk] = 0 if (wide or inner) else DS.pattern_step(st_, Ag_, det.get('rho_min', 0.01))
        return gk
    RANK = {'OK': 0, 'ACCEPTED': 0, 'ASK_RHO': 1, 'REVISE': 2}
    # engineer-accepted overload (v1.3.3): [[label, story, D/C max]] – Engineering judgment, reported
    ovl = {(str(a), str(b)): float(c) for a, b, c in cfg.get('accept_overload', [])}
    tgt = float((cfg.get('fix') or {}).get('target_dc', 0.90))
    # v1.5.0: an enlarged section (forces of the old ETABS model) is designed to D/C <= target (0.90) – margin for the force
    # the larger section attracts; an accepted overload keeps its own limit
    lim = lambda lab, s: ovl.get((lab, s), tgt if (lab, s) in ov_sec else 1.0)
    req, status = {}, {}
    for lab in labels:
        p = {}
        for s in stories:
            if (lab, s) not in cols:
                continue
            c = cols[(lab, s)]
            r = DS.choose_step(cache, grids[c['gkey']], steps[c['gkey']], c, fc_of[s], fy,
                               rho_ask if (lab, s) in approved else rho_max, rho_ask, start=jmin[c['gkey']], dc_lim=lim(lab, s))
            p[s] = r['step']; status[(lab, s)] = r['status']
        ss = [s for s in stories if s in p]
        for i in range(len(ss) - 2, -1, -1):          # a story never carries less than the story above (same section, same f'c;
            # CEDA Oct 2026: at the f'c reduction the lower, stronger-concrete story may carry less steel than the story above)
            if (lab, ss[i]) in mono_ex and (lab, ss[i + 1]) in mono_ex:
                continue                                # v1.5.0: enlarged range (option 2) – a lower story may carry less
            if status[(lab, ss[i + 1])] == 'REVISE':
                continue                                # v1.5.0: a failing story's best effort is not a requirement for the stories below
            if cols[(lab, ss[i])]['gkey'] == cols[(lab, ss[i + 1])]['gkey'] and fc_of[ss[i]] == fc_of[ss[i + 1]]:
                p[ss[i]] = max(p[ss[i]], p[ss[i + 1]])
        req[lab] = p
    # ---------------------------------------------------------------- common story ranges (rows of the Table of Column)
    srcfg = cfg.get('story_ranges', {})
    basement = set(rep_in.get('basement_stories') or cfg.get('basement_stories', []))
    hs = collections.defaultdict(list)
    for (lab, s), c in cols.items():
        if c.get('H'):
            hs[s].append(c['H'] / 100)
    height_m = {s: sorted(v)[len(v) // 2] for s, v in hs.items()}
    laps = [float(v) for t in cfg.get('lap_table', {}).values() for v in t.values()]
    if srcfg.get('lst_m'):
        lst_m = float(srcfg['lst_m'])
    elif laps:
        lst_m = max(laps) / 1000
    else:
        lst_m = 2.0
        notes.append('story ranges: no lap table – Lst 2.0 m assumed for the 12 m bar check (ASSUMPTION)')
    lab_steps = {lab: {s: steps[cols[(lab, s)]['gkey']] for s in stories if (lab, s) in cols} for lab in labels}
    ranges = DS.story_ranges(stories, basement, height_m, fc_of, req, lab_steps, lst_m, srcfg.get('stock_m', 12.0),
                             srcfg.get('max_group', 3), srcfg.get('mode', 'auto'), srcfg.get('groups'))
    # each label: one step per range (governing story of the range), monotonic from the top down
    picks = {}
    for lab in labels:
        pr = {}
        for (s0, s1) in ranges:
            ss = [s for s in stories[stories.index(s0):stories.index(s1) + 1] if s in req[lab]]
            if ss:
                pr[(s0, s1)] = max(req[lab][s] for s in ss)
                worst = max(RANK.get(status[(lab, s)], 2) for s in ss)
                g0 = cols[(lab, ss[0])]['gkey']
                if worst and len(g0) == 3 and all(cols[(lab, s)]['gkey'] == g0 for s in ss):
                    # CEDA order (Oct 2026): 125-150 grid -> wider grid with 3-4-bar bundles -> inner bars at the tie crossings
                    # (last resort, only basement stories (compression) or label-stories approved for ρ > 6 %)
                    tries = [wide_key(g0)]
                    if g0[0] != 'circ' and all(s in basement or (lab, s) in approved for s in ss):
                        tries += [tuple(g0[:3]) + ('I',), tuple(g0[:3]) + ('W', 'I')]
                    for gk_try in tries:
                        gw = make_grid(gk_try)
                        if not steps[gw]:
                            continue
                        rs = {s: DS.choose_step(cache, grids[gw], steps[gw], cols[(lab, s)], fc_of[s], fy,
                                                rho_ask if (lab, s) in approved else rho_max, rho_ask, start=0, dc_lim=lim(lab, s)) for s in ss}
                        if max(RANK[r['status']] for r in rs.values()) < worst:
                            for s in ss:
                                cols[(lab, s)]['gkey'] = gw; req[lab][s] = rs[s]['step']; status[(lab, s)] = rs[s]['status']
                            pr[(s0, s1)] = max(rs[s]['step'] for s in ss)
                            stp = steps[gw][pr[(s0, s1)]]
                            if 'I' in gw[3:]:
                                ev = rs[max(ss, key=lambda q: rs[q]['ev']['dcmax'])]['ev']; gi = ev['gov']; cg = cols[(lab, ss[0])]
                                P_ = max(float(cols[(lab, ss[0])]['rows']['P'][gi]), 1.0)
                                eh = max(abs(float(ev['mg']['x']['Md'][gi])) / (P_ * cg['h']), abs(float(ev['mg']['y']['Md'][gi])) / (P_ * cg['b']))
                                notes.append(f"{lab} {s0}-{s1}: {sum(stp[1])}-DB{stp[0]} incl. {len(grids[gw].inner(stp[0]))} inner bars at the tie crossings "
                                             f"(CEDA pattern, last resort) – governing e/h = {eh:.2f}: confirm compression-dominated")
                            else:
                                notes.append(f"{lab} {s0}-{s1}: {sum(stp[1])}-DB{stp[0]} with {max(stp[1])}-bar bundles on the wider grid "
                                             f"(c/c ≤ {cc_w[1]:.0f} mm, CEDA Oct 2026) – the 125-150 grid could not carry the load")
                            worst = max(RANK[r['status']] for r in rs.values())
                            if worst == 0:
                                break
        keys = [r for r in ranges if r in pr]
        for i in range(len(keys) - 2, -1, -1):
            a_, b_ = keys[i], keys[i + 1]
            ga = next(cols[(lab, s)]['gkey'] for s in stories[stories.index(a_[0]):stories.index(a_[1]) + 1] if (lab, s) in cols)
            gb = next(cols[(lab, s)]['gkey'] for s in stories[stories.index(b_[0]):stories.index(b_[1]) + 1] if (lab, s) in cols)
            in_ex = all((lab, s) in mono_ex for s in stories[stories.index(a_[0]):stories.index(b_[1]) + 1] if (lab, s) in cols)
            if any(status.get((lab, s)) == 'REVISE' for s in stories[stories.index(b_[0]):stories.index(b_[1]) + 1] if (lab, s) in cols):
                continue                                # v1.5.0: no carry-down from a failing range
            if ga == gb and fc_of[a_[0]] == fc_of[b_[0]] and in_ex:
                if pr[a_] < pr[b_]:
                    sa, sb = steps[ga][pr[a_]], steps[gb][pr[b_]]
                    notes.append(f"{lab}: enlarged range – {a_[0]}-{a_[1]} carries less than {b_[0]}-{b_[1]} ({sum(sa[1])}-DB{sa[0]} / "
                                 f"{sum(sb[1])}-DB{sb[0]}); the extra bars of the upper story run Lst below the floor, then stop (v1.5.0 exception, logged)")
            elif ga == gb and fc_of[a_[0]] == fc_of[b_[0]]:
                pr[a_] = max(pr[a_], pr[b_])
            elif ga == gb:
                if pr[a_] < pr[b_]:
                    sa, sb = steps[ga][pr[a_]], steps[gb][pr[b_]]
                    notes.append(f"{lab}: less steel below the f'c change at {b_[0]} ({sum(sa[1])}-DB{sa[0]} below / {sum(sb[1])}-DB{sb[0]} above, "
                                 f"same grid) – bars change at {b_[0]}: splice there with Lst of the upper bars")
            elif tuple(ga[:3]) == tuple(gb[:3]):              # same section, grid W (3-4-bar bundles) on one side
                ss_a = [s for s in stories[stories.index(a_[0]):stories.index(a_[1]) + 1] if (lab, s) in cols]
                need = DS._as(steps[gb][pr[b_]])
                if fc_of[a_[0]] == fc_of[b_[0]] and DS._as(steps[ga][pr[a_]]) < need - 1e-9:
                    if DS._as(steps[ga][-1]) < need - 1e-9 and len(gb) > 3:   # lower range moves to the upper arrangement
                        rs = {s: DS.choose_step(cache, grids[gb], steps[gb], cols[(lab, s)], fc_of[s], fy,
                                                rho_ask if (lab, s) in approved else rho_max, rho_ask, start=0, dc_lim=lim(lab, s)) for s in ss_a}
                        j = max(r['step'] for r in rs.values())
                        while j < len(steps[gb]) - 1 and DS._as(steps[gb][j]) < need - 1e-9:
                            j += 1
                        for s in ss_a:
                            cols[(lab, s)]['gkey'] = gb; status[(lab, s)] = rs[s]['status']
                        pr[a_] = j
                    else:
                        j = pr[a_]
                        while j < len(steps[ga]) - 1 and DS._as(steps[ga][j]) < need - 1e-9:
                            j += 1
                        pr[a_] = j
                notes.append(f"{lab}: bar arrangement changes at {b_[0]} (125-150 grid / wider grid for 3-4-bar bundles / inner bars) – bars offset at the splice, detail by the engineer")
            else:
                notes.append(f"{lab}: section changes {ga[1]*10:.0f}×{ga[2]*10:.0f} → {gb[1]*10:.0f}×{gb[2]*10:.0f} at {b_[0]} – "
                             f"bar continuity / offset bars at the splice to be detailed by the engineer")
        picks[lab] = pr
    bnds = list(ranges)        # CEDA: every story range stays a row (no merging); a mark that runs on with the same
    if False:                  # bars is shown as merged cells (no dividing line) in the drawing
        newp = {}
        for lab in labels:
            newp[lab] = {}
            for (s0, s1) in bnds:
                i0, i1 = stories.index(s0), stories.index(s1)
                v = [j for (a_, b_), j in picks[lab].items() if i0 <= stories.index(a_) and stories.index(b_) <= i1]
                if v:
                    newp[lab][(s0, s1)] = max(v)
        picks = newp
    # 12 m stock: laps only where bundles <= 2 – flag a 3/4-bar bundle run longer than one bar can cover
    for lab in labels:
        run_h, run = 0.0, []
        for rg in bnds + [None]:
            j = picks[lab].get(rg) if rg else None
            if j is not None:                         # v1.3.1: steps of the section of this range (section may change along the height)
                gk = next(cols[(lab, s)]['gkey'] for s in stories[stories.index(rg[0]):stories.index(rg[1]) + 1] if (lab, s) in cols)
            big = j is not None and max(steps[gk][j][1]) > 2
            if big:
                s0, s1 = rg
                run_h += sum(height_m.get(s, 3.0) for s in stories[stories.index(s0):stories.index(s1) + 1]); run.append(s0)
            else:
                if run and run_h + lst_m > srcfg.get('stock_m', 12.0):
                    notes.append(f'{lab}: 3/4-bar bundles over {run_h:.1f} m ({run[0]}…) – splice inside the bundle zone with couplers (CEDA); '
                                 f'a lap would need ACI 25.6.1.5 ×1.2/×1.33 on Lst')
                run_h, run = 0.0, []
    # ---------------------------------------------------------------- final evaluation per label-band
    so0, s0 = det.get('so_mm', 150), det.get('s_mm', 300)
    Ef = cfg.get('seismic', {}).get('imf_E_factor', 2.0)

    def final_eval(lab, pk, forced=None):
        """results of one label for the step picks pk {band: step}; forced {band: dict(so, s, extra)} = ties fixed by the mark."""
        out_l = []
        for (s0_, s1_) in bnds:
            ss = stories[stories.index(s0_):stories.index(s1_) + 1]
            have = [s for s in ss if (lab, s) in cols]
            if not have:
                continue
            j = pk[(s0_, s1_)]
            c0 = cols[(lab, have[0])]
            g = grids[c0['gkey']]
            db, counts = steps[c0['gkey']][j][0], steps[c0['gkey']][j][1]
            phase = steps[c0['gkey']][j][2] if len(steps[c0['gkey']][j]) > 2 else 0
            T = LY.ties(g, db)
            evs = [(cols[(lab, s)], DS.evaluate(cache, grids[cols[(lab, s)]['gkey']], cols[(lab, s)], fc_of[s], fy, db, counts), fc_of[s])
                   for s in have]
            fz = (forced or {}).get((s0_, s1_))
            if fz:
                res_ = [DS.shear_check(c, ev, T, fcs, tie_db, mat.get('fyt', 4000), fz['so'] / 10, fz['s'] / 10, frame, cover / 10, Ef,
                                       fz['extra']) for c, ev, fcs in evs]
                okk = all(max(r[k]['lo']['dc'], r[k]['mid']['dc']) <= 1.0 and r[k]['lo']['avmin_ok'] and r[k]['mid']['avmin_ok']
                          for r in res_ for k in ('V2', 'V3'))
                SH = dict(so=fz['so'], s=fz['s'], extra=fz['extra'], res=res_, ok=okk, note=fz.get('note', ''))
            else:
                SH = DS.design_shear(evs, T, tie_db, mat.get('fyt', 4000), so0, s0, frame, cover / 10, Ef)
            per = []
            for (c, ev, fcs), sh, s in zip(evs, SH['res'], have):
                it = DS.imf_ties(c, db, tie_db, SH['so'])
                gi = ev['gov']
                per.append(dict(story=s, dwg=dwg_level(stories, s), fc=fc_of[s], dc=ev['dcmax'], rho=ev['rho'], Lu=c['Lu'], k=c['k'],
                                betad=c['betad'], slr_x=ev['mg']['x']['slr'], slr_y=ev['mg']['y']['slr'],
                                dmax_x=float(np.max(ev['mg']['x']['delta'])), dmax_y=float(np.max(ev['mg']['y']['delta'])),
                                n_delta_14=int(np.sum((ev['mg']['x']['delta'] > 1.4) | (ev['mg']['y']['delta'] > 1.4))),
                                gov=dict(c['meta'][gi], P=float(c['rows']['P'][gi]), Mx=float(ev['mg']['x']['Md'][gi]),
                                         My=float(ev['mg']['y']['Md'][gi])),
                                shear={k_: dict(dc_lo=v['lo']['dc'], dc_mid=v['mid']['dc'], Ve=v['Ve'], legs=v['lo']['legs'],
                                               avmin_ok=v['lo']['avmin_ok'] and v['mid']['avmin_ok']) for k_, v in sh.items()},
                                ties=it, status=_status(status.get((lab, s), 'OK'), ev['dcmax'], lim(lab, s))))
            kmax_used = max(counts)
            out_l.append(dict(label=lab, band=(s0_, s1_), stories=have, shape=c0['shape'], b=c0['b'], h=c0['h'], db=db,
                              counts=list(counts), nbar=sum(counts), phase=phase, fc=fc_of[have[0]], step=j, gkey=list(c0['gkey']),
                              As=sum(counts) * math.pi * db ** 2 / 400, nset=T['nset'], ncross=T['ncross'] + sum(SH['extra'].values()),
                              tie_db=tie_db, so=SH['so'], s=SH['s'], extra_legs=SH['extra'], shear_note=SH['note'], shear_ok=SH['ok'],
                              lap=_lap(cfg, fc_of[have[0]], db, kmax_used, lab, have), splice=splice_of(lab, have),
                              enlarged=any((lab, s_) in ov_sec for s_ in have),
                              per=per, grid_notes=g.notes))
        return out_l

    sp_def = det.get('splice', 'Lap – staggered')

    def splice_of(lab, have):
        for o in cfg.get('splice_by', []):
            if o['label'] != lab:
                continue
            if not o.get('story_from'):
                return o['method']
            i0, i1 = stories.index(o['story_from']), stories.index(o.get('story_to') or o['story_from'])
            if any(i0 <= stories.index(s_) <= i1 for s_ in have):
                return o['method']
        return sp_def

    def _lap(cfg_, fc, db, k, lab, have):
        m = splice_of(lab, have).lower()
        L = DS.lap_length(cfg_.get('lap_table', {}), fc, db, k)
        if 'coupler' in m:
            return None                                   # mechanical splice ≥ 1.25 fy (ACI 318-19 §25.5.7)
        if L is not None and k >= 3 and 'stagger' in m:
            return round(L * (1.2 if k == 3 else 1.33))   # ACI 318-19 §25.6.1.5 – laps of the bars of a bundle staggered
        return L
    res_of = {lab: final_eval(lab, picks[lab]) for lab in labels}
    for lab in labels:
        for r in res_of[lab]:
            m_ = r['splice'].lower()
            if 'one level' in m_ and max(r['counts']) >= 3:
                notes.append(f"{lab} {r['band'][0]}-{r['band'][1]}: lap at one level not allowed with {max(r['counts'])}-bar bundles "
                             f"(ACI 318-19 §25.6.1.7) – use staggered laps or couplers")
            if any(q['rho'] > 0.06 + 1e-9 for q in r['per']):
                notes.append(f"{lab} {r['band'][0]}-{r['band'][1]}: ρ above 6 % approved – splice: {r['splice']}"
                             + (', couplers ≥ 1.25 fy (ACI 318-19 §25.5.7)' if 'coupler' in r['splice'].lower()
                                else (f", Lst {r['lap']:.0f} mm" if r['lap'] else ', Lst not in the lap table')))
    # ---------------------------------------------------------------- marks (CEDA, Oct 2026)
    # same label = same mark in every story; labels with the same section (a 90° rotation counts as the same section),
    # same rows and same bars + ties share a mark; with mark_envelope on, a label may join a heavier mark when the
    # envelope differs from it in <= max_rows rows by <= max_step ladder steps and adds <= max_weight longitudinal steel.
    # CEDA 20 Oct 2026 (v1.3.3): criterion A – same section in every row; each label may take <= max_weight (25 %) extra
    # longitudinal steel; the whole project <= project_max_weight (10 %); no limit on rows / ladder steps unless set.
    mcfg = dict(dict(envelope=True, max_rows=None, max_step=None, max_weight=0.25, project_max_weight=0.10), **cfg.get('mark_envelope', {}))

    def canon_key(gk):
        return (gk[0], min(gk[1], gk[2]), max(gk[1], gk[2])) + tuple(gk[3:])

    def is_rot(gk):
        return gk[0] == 'rect' and gk[1] > gk[2]

    def canon_grid(gk):
        return make_grid(canon_key(gk))

    def bar_sig(gk, j):
        g = grids[gk]; db, counts = steps[gk][j][0], steps[gk][j][1]
        P, _ = g.positions(db)
        rot = is_rot(gk)
        return (db, tuple(sorted((round(p['y'] if rot else p['x'], 1), round(p['x'] if rot else p['y'], 1), c) for p, c in zip(P, counts))))

    sig_cache = {}

    def to_canon(gk, j):
        if not is_rot(gk):
            return j
        if (gk, j) not in sig_cache:
            ck = canon_grid(gk)
            target = bar_sig(gk, j)
            sig_cache[(gk, j)] = next((i for i in range(len(steps[ck])) if bar_sig(ck, i) == target), None)
        return sig_cache[(gk, j)]

    def from_canon(gk, i):
        if not is_rot(gk):
            return i
        ck = canon_grid(gk)
        target = bar_sig(ck, i)
        return next((j for j in range(len(steps[gk])) if bar_sig(gk, j) == target), None)

    def swap(e, rot):
        return {('Vx' if k == 'Vy' else 'Vy') if rot else k: v for k, v in e.items()}

    info = {}
    for lab in labels:
        R = res_of[lab]
        gk0 = tuple(R[0]['gkey'])
        rot = is_rot(gk0)
        V = {tuple(r['band']): to_canon(tuple(r['gkey']), r['step']) for r in R}
        ties_c = {tuple(r['band']): (r['so'], r['s'], tuple(sorted(swap(r['extra_legs'], rot).items()))) for r in R}
        H = {tuple(r['band']): sum(height_m.get(s, 3.0) for s in r['stories']) for r in R}
        gkey_rows = tuple((tuple(r['band']), canon_key(tuple(r['gkey']))) for r in R)
        info[lab] = dict(V=V, ties=ties_c, H=H, rot=rot, gk=gk0, group=gkey_rows, ok=all(v is not None for v in V.values()))

    def weight(lab, V):
        out_w = 0.0
        for bd, i in V.items():
            ck = canon_key(tuple(next(r['gkey'] for r in res_of[lab] if tuple(r['band']) == bd)))
            canon_grid(ck)
            out_w += DS._as(steps[ck][i]) * info[lab]['H'][bd]
        return out_w

    groups_m = collections.defaultdict(list)
    for lab in labels:
        groups_m[info[lab]['group']].append(lab)
    base_total = sum(weight(l, info[l]['V']) for l in labels if info[l]['ok'])
    extra_used = 0.0

    def rho_ok(x, env):
        """the envelope may not push a label above ρ max (6 %) unless that label-story is approved."""
        for r in res_of[x]:
            bd = tuple(r['band']); ck = canon_key(tuple(r['gkey'])); canon_grid(ck)
            if env[bd] == info[x]['V'][bd]:
                continue
            Ag = math.pi * ck[1] ** 2 / 4 if ck[0] == 'circ' else ck[1] * ck[2]
            if DS._as(steps[ck][env[bd]]) / Ag > rho_max + 1e-9 and not all((x, s_) in approved for s_ in r['stories']):
                return False
        return True
    mark_list = []                    # dict(members, V, ties)
    for gkey_rows, labs in groups_m.items():
        labs = sorted(labs, key=lambda l: (-weight(l, info[l]['V']) if info[l]['ok'] else 0, len(l), l))
        local = []
        for lab in labs:
            I = info[lab]
            placed = False
            for m in local:
                if not I['ok'] or not all(info[x]['ok'] for x in m['members']):
                    continue
                if not mcfg['envelope']:
                    if m['V'] == I['V'] and m['ties'] == I['ties']:
                        m['members'].append(lab); placed = True; break
                    continue
                env = {bd: max(m['V'][bd], I['V'][bd]) for bd in m['V']}
                good = True
                for x in m['members'] + [lab]:
                    Vx = info[x]['V']
                    diff = [bd for bd in env if env[bd] != Vx[bd]]
                    if (mcfg.get('max_rows') is not None and len(diff) > mcfg['max_rows']) or \
                            (mcfg.get('max_step') is not None and any(env[bd] - Vx[bd] > mcfg['max_step'] for bd in diff)):
                        good = False; break
                    if weight(x, env) > (1 + mcfg['max_weight']) * weight(x, Vx) + 1e-9 or not rho_ok(x, env):
                        good = False; break
                if good:
                    new_extra = sum(weight(x, env) - weight(x, info[x]['V']) for x in m['members'] + [lab])
                    delta = new_extra - m['extra']
                    if mcfg.get('project_max_weight') is not None and extra_used + delta > mcfg['project_max_weight'] * base_total + 1e-9:
                        good = False
                if good:
                    m['V'] = env; m['extra'] = new_extra; extra_used += delta
                    m['members'].append(lab); placed = True; break
            if not placed:
                local.append(dict(members=[lab], V=dict(I['V']), ties=dict(I['ties']), extra=0.0))
        mark_list += local
    # ties of a mark: critical of its members (smallest so, s; most added legs) per row
    for m in mark_list:
        tz = {}
        for bd in m['V']:
            so_ = min(info[x]['ties'][bd][0] for x in m['members'])
            s_ = min(info[x]['ties'][bd][1] for x in m['members'])
            ex = {}
            for x in m['members']:
                for k_, v in info[x]['ties'][bd][2]:
                    ex[k_] = max(ex.get(k_, 0), v)
            tz[bd] = (so_, s_, ex)
        m['tz'] = tz
    # re-evaluate members whose bars or ties changed
    for m in mark_list:
        for lab in m['members']:
            I = info[lab]
            changed_b = any(m['V'][bd] != I['V'][bd] for bd in m['V'])
            changed_t = any((m['tz'][bd][0], m['tz'][bd][1], tuple(sorted(m['tz'][bd][2].items()))) != I['ties'][bd] for bd in m['V'])
            if not (changed_b or changed_t):
                continue
            pk = {}
            for r in res_of[lab]:
                bd = tuple(r['band'])
                j = from_canon(tuple(r['gkey']), m['V'][bd])
                pk[bd] = j if j is not None else r['step']
            forced = {bd: dict(so=m['tz'][bd][0], s=m['tz'][bd][1], extra=swap(m['tz'][bd][2], I['rot']),
                               note='ties = critical of the mark') for bd in m['V']}
            res_of[lab] = final_eval(lab, pk, forced)
            if changed_b:
                add = weight(lab, m['V']) / weight(lab, I['V']) - 1
                rows_ = [f'{bd[0]}-{bd[1]}' for bd in m['V'] if m['V'][bd] != I['V'][bd]]
                notes.append(f"mark envelope: {lab} takes the bars of {m['members'][0]} at {', '.join(rows_)} (+{add*100:.0f} % steel)")
    for a, b, c in cfg.get('accept_delta', []):
        notes.append(f"{a} {b}: moment magnifier δ up to {float(c):.2f} accepted by the engineer (Engineering judgment – ACI 6.2.5.3 limit 1.4)")
    for (a, b), c in ovl.items():
        notes.append(f"{a} {b}: overload accepted by the engineer up to D/C {c:.2f} (Engineering judgment – ACI 318 requires φSn ≥ U)")
    if base_total > 0:
        notes.append(f"marks: {len(mark_list)} marks for {len(labels)} labels; envelope adds {extra_used / base_total * 100:.1f} % longitudinal "
                     f"steel to the project (limit {(mcfg.get('project_max_weight') or 0) * 100:.0f} %, per label ≤ {mcfg['max_weight'] * 100:.0f} %)")
    # numbering C1, C2 … by section size (largest first); v1.5.0: names locked after the f'c case (mark_names) unless renumber
    def area(m):
        return max(r['b'] * r['h'] for x in m['members'] for r in res_of[x])
    mark_list.sort(key=lambda m: (-area(m), m['members'][0]))
    locked = cfg.get('mark_names') or {}
    use_lock = bool(locked) and not cfg.get('mark_renumber_now')
    names, taken = [], set()
    if use_lock:
        nxt = max([int(''.join(c for c in v if c.isdigit()) or 0) for v in locked.values()] + [0]) + 1
        for m in mark_list:
            cand = collections.Counter(locked[x] for x in m['members'] if x in locked)
            nm = next((n for n, _ in cand.most_common() if n not in taken), None)
            if nm is None:
                nm = f'C{nxt}'; nxt += 1
                notes.append(f"marks locked: new mark {nm} for {', '.join(m['members'])}")
            changed = [x for x in m['members'] if locked.get(x) not in (None, nm)]
            if changed:
                notes.append(f"marks locked: {', '.join(changed)} now in {nm} (was {', '.join(sorted(set(locked[x] for x in changed)))})")
            taken.add(nm); names.append(nm)
    else:
        names = [f'C{i}' for i in range(1, len(mark_list) + 1)]
    marks = {}
    results = []
    for nm, m in zip(names, mark_list):
        ref = m['members'][0]
        for lab in m['members']:
            marks[lab] = nm
            for r in res_of[lab]:
                r['mark'] = nm
                r['ref'] = lab == ref
                r['rotated'] = info[lab]['rot'] != info[ref]['rot']
                results.append(r)
        rots = [x for x in m['members'] if info[x]['rot'] != info[ref]['rot']]
        if rots:
            notes.append(f"{nm}: {', '.join(rots)} rotated 90° relative to {ref} – same mark, orientation to be shown on plan")
    out = dict(config=cfg, stories=stories, bands=bnds, ranges_before_merge=ranges, story_height_m=height_m, lst_m=lst_m, fc_of=fc_of, fcinfo=fcinfo, results=results, marks=marks,
               notes=list(dict.fromkeys(notes + sum((g.notes for g in grids.values()), []))), input_report=_jsonable(rep_in),
               grids={f'{k}': dict(shape=k[0], b=k[1], h=k[2]) for k in grids})
    json.dump(_jsonable(out), open(os.path.join(outdir, 'results.json'), 'w'), ensure_ascii=False, indent=1)
    pickle.dump(dict(cols=cols, grids=grids, steps=steps, fc_of=fc_of, stories=stories, cfg=dict(cfg, detailing=det), basement=sorted(basement)),
                open(os.path.join(outdir, 'state.pkl'), 'wb'))
    import outputs_table
    outputs_table.decision_table(out, os.path.join(outdir, f'{cfg["project"].get("job", "job")}_Column_Decision.xlsx'))
    return out


def _status(st0, dc, dc_lim):
    """final status of a column-story: OK (D/C <= 1), ACCEPTED (1 < D/C <= the overload the engineer accepted), else REVISE;
    ASK_RHO / REVISE from the bar choice are kept."""
    if dc <= 1.0:
        return 'OK' if st0 == 'ACCEPTED' else st0
    if dc <= dc_lim + 1e-9:
        return 'ACCEPTED' if st0 in ('OK', 'ACCEPTED') else st0
    return 'REVISE' if st0 in ('OK', 'ACCEPTED') else st0


def _jsonable(o):
    if isinstance(o, dict):
        return {str(k) if not isinstance(k, str) else k: _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, float) and not math.isfinite(o):
        return 'inf'
    return o


if __name__ == '__main__':
    o = main(sys.argv[1], sys.argv[2])
    print('labels', len(o['marks']), 'marks', len(set(o['marks'].values())), 'story ranges', o['bands'])
    for n in o['notes']:
        print('NOTE', n)
