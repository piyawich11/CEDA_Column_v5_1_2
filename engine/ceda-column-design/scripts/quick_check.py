"""Quick re-check of ONE column-story with a designer change (v1.4.0) – preview for the fix board, no full run.

    import quick_check as QC
    QC.check(outdir, 'C75', 'B2', b_mm=1000, h_mm=1100)            # enlarged section (forces of the current ETABS model)
    QC.check(outdir, 'C72', 'GM', rho_max=0.08)                     # ρ up to 8 % approved
    QC.check(outdir, 'C142', 'GM', dc_lim=1.10)                     # overload accepted up to D/C 1.10
Same bar order as the design (125-150 grid -> wider grid with 3-4-bar bundles -> inner bars for basement / approved ρ), same
section, slenderness (δ non-sway, Cm = 1, βd of the column) and 3D φ-surface. It does NOT redo story ranges, the monotonic rule
or marks – the result is a preview; Apply + run gives the final design. A changed section keeps the ETABS forces of the old
one (stiffness not updated) – say so and update ETABS.
"""
import os, sys, copy, pickle, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import design as DS      # noqa: E402
import fc_study as FS    # noqa: E402

_ST = {}


def _state(outdir):
    p = os.path.join(outdir, 'state.pkl')
    key = (p, os.path.getmtime(p))
    if key not in _ST:
        st = pickle.load(open(p, 'rb'))
        if not st.get('basement'):
            try:
                st['basement'] = json.load(open(os.path.join(outdir, 'results.json')))['input_report'].get('basement_stories') or []
            except Exception:
                st['basement'] = []
        _ST.clear()
        _ST[key] = dict(st=st, cache=DS.Cache(), grids=FS.Grids(st['cfg'].get('detailing', {})))
    return _ST[key]


def check(outdir, label, story, shape=None, b_mm=None, h_mm=None, rho_max=None, dc_lim=1.0, fc=None):
    S = _state(outdir)
    st, cfg = S['st'], S['st']['cfg']
    det = cfg.get('detailing', {})
    c0 = st['cols'].get((label, story))
    if c0 is None:
        return dict(ok=False, status='NOT FOUND', note=f'{label} {story} not in the run')
    c = copy.copy(c0)
    changed = False
    if b_mm or h_mm or shape:
        sh = shape or c['shape']
        b = (b_mm or c['b'] * 10) / 10.0
        h = b if sh == 'circ' else (h_mm or c['h'] * 10) / 10.0
        changed = (sh, round(b, 3), round(h, 3)) != (c['shape'], round(c['b'], 3), round(c['h'], 3))
        c.update(shape=sh, b=b, h=h, gkey=(sh, b, h))
    approved = (label, story) in set(tuple(x) for x in cfg.get('approved_rho_over_6', []))
    lim = rho_max or (det.get('rho_ask', 0.07) if approved else det.get('rho_max', 0.06))
    lim = min(lim, det.get('rho_ask', 0.07))                     # never above the approval limit (≤ 8 %)
    inner_ok = story in set(st.get('basement') or cfg.get('basement_stories', [])) or lim > det.get('rho_max', 0.06)
    fc = fc or st['fc_of'][story]
    r = FS.try_column(S['cache'], S['grids'], c, fc, cfg['materials'].get('fy', 5000), lim, inner_ok, dc_lim)
    mg = r['ev']['mg']
    d = [float(x) for x in np.concatenate([mg['x']['delta'], mg['y']['delta']]) if np.isfinite(x)]
    dc = r['dc']
    status = 'OK' if dc <= 1.0 and r['ok'] else ('ACCEPTED' if r['ok'] else 'REVISE')
    hint = ''
    if not r['ok'] and lim < det.get('rho_ask', 0.07):
        r8 = FS.try_column(S['cache'], S['grids'], c, fc, cfg['materials'].get('fy', 5000), det.get('rho_ask', 0.07), True, dc_lim)
        if r8['ok']:
            hint = f"passes with ρ {r8['rho'] * 100:.2f} % ({r8['nbar']}-DB{r8['db']}) if ρ up to the approval limit is approved"
    grid = ''.join(r['gk'][3:]) or '125-150'
    return dict(ok=r['ok'], status=status, dc=round(dc, 3), rho_pct=round(r['rho'] * 100, 2), bars=f"{r['nbar']}-DB{r['db']}",
                grid=grid, delta_max=round(max(d), 2) if d else None, fc=fc,
                section=(f"Ø{c['b'] * 10:.0f}" if c['shape'] == 'circ' else f"{c['b'] * 10:.0f}×{c['h'] * 10:.0f}"),
                note=('forces of the current ETABS model – update ETABS for the new section' if changed else '') + hint)


if __name__ == '__main__':
    kw = json.loads(sys.argv[4]) if len(sys.argv) > 4 else {}
    print(check(sys.argv[1], sys.argv[2], sys.argv[3], **kw))
