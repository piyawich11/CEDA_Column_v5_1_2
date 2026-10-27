"""Produce the deliverables from OUTDIR/results.json + state.pkl (made by run.py).

usage:
  python3 -I make_outputs.py OUTDIR [--per-mark]            -> calc PDF, back-up Excel, draft drawing (PDF/DXF/Excel);
                                                               --per-mark also writes OUTDIR/marks/<job>_<mark>_Calc.pdf / _Backup.xlsx
  python3 -I make_outputs.py OUTDIR --detail MARK BAND_BOTTOM_STORY   -> CEDA-style detailed Excel for one mark-band
"""
import sys, os, json, pickle, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import layout as LY
import design as DS


def load(outdir):
    res = json.load(open(os.path.join(outdir, 'results.json')))
    st = pickle.load(open(os.path.join(outdir, 'state.pkl'), 'rb'))
    return res, st


def pack_for(res, st, cache, r):
    """evaluate every column-story of a result (label-band)."""
    cols, grids, steps = st['cols'], st['grids'], st['steps']
    fy = st['cfg']['materials'].get('fy', 5000)
    out = []
    for s in r['stories']:
        c = cols[(r['label'], s)]
        ev = DS.evaluate(cache, grids[c['gkey']], c, st['fc_of'][s], fy, r['db'], tuple(r['counts']))
        i = st['stories'].index(s)
        out.append(dict(label=r['label'], story=s, dwg=(st['stories'][i - 1] if i else 'FDN', s), S=ev['S'], mg=ev['mg'], dc=ev['dc'],
                        dcmax=ev['dcmax'], rows=c['rows'], meta=c['meta'], Lu=c['Lu'], k=c['k'], betad=c['betad'], gkey=c['gkey']))
    return out


def groups(res):
    """mark-band -> list of results (one per label)."""
    g = {}
    for r in res['results']:
        g.setdefault((r['mark'], tuple(r['band'])), []).append(r)
    return g


def bars_txt(r):
    t = f"{r['nbar']}-DB{r['db']}"
    d = LY.describe(r['counts'], r.get('phase', 0))
    return t + (f' ({d.lower()})' if d else '')


def main(outdir, detail=None, per_mark=False):
    res, st = load(outdir)
    cfg = st['cfg']; P = dict(cfg['project']); job = P.get('job', 'job')
    P['_accept'] = {(str(a), str(b)): float(c) for a, b, c in cfg.get('accept_overload', [])}
    P['_accept_delta'] = {(str(a), str(b)): float(c) for a, b, c in cfg.get('accept_delta', [])}
    cache = DS.Cache()
    G = groups(res)
    order = sorted(G, key=lambda k: (int(''.join(c for c in k[0] if c.isdigit()) or 0), st['stories'].index(k[1][0])))
    if detail:
        mark, sb = detail
        key = next(k for k in G if k[0] == mark and k[1][0] == sb)
        packs = [q for r in G[key] for q in pack_for(res, st, cache, r)]
        gov = max(packs, key=lambda q: q['dcmax'])
        r = next(r for r in G[key] if r['label'] == gov['label'])
        g = st['grids'][gov['gkey']]
        bars = LY.bars_cm(g, r['db'], tuple(r['counts']))
        rows = []
        for q in packs:
            for i in range(len(q['dc'])):
                rows.append(dict(story=q['story'], col=q['label'], combo=q['meta'][i]['combo'], P=float(q['rows']['P'][i]),
                                 Mx=float(q['rows']['M3'][i]), My=float(q['rows']['M2'][i]), Mxd=float(q['mg']['x']['Md'][i]),
                                 Myd=float(q['mg']['y']['Md'][i]), dx=float(q['mg']['x']['delta'][i]), dy=float(q['mg']['y']['delta'][i])))
        import detail_xlsx
        H = dict(D1=P.get('name', ''), K1=P.get('date', ''), D2=P.get('location', ''), K2=P.get('job', ''), C3=P.get('building', ''))
        cb = P.get('calc_by', []) + [['', '']] * 2; ap = P.get('approve_by', ['', ''])
        H.update(C52=cb[0][0], F52=cb[0][1], C53=cb[1][0], F53=cb[1][1], C54=ap[0], F54=ap[1])
        ctx = dict(S=gov['S'], bars=bars, db=r['db'], rows=rows, H=H, page=f'{mark}-{sb}',
                   m=dict(b=r['b'], h=r['h'], fc=r['fc'], fy=cfg['materials'].get('fy', 5000), k=gov['k'], Lu=gov['Lu'], betad=gov['betad']),
                   title=f"{mark}  {key[1][0]}→{key[1][1]}  {r['b']*10:.0f}×{r['h']*10:.0f} mm  {bars_txt(r)}  f'c {r['fc']} ksc",
                   tie_db=r['tie_db'], so_cm=r['so'] / 10, s_cm=r['s'] / 10, nset=r['nset'])
        path = os.path.join(outdir, f'{job}_{mark}_{sb}_Detailed_Calc.xlsx')
        info = detail_xlsx.build(path, ctx)
        print('detailed', path, info)
        return
    # ------------------------------------------------------------------ calc PDF + back-up pages
    import calc_pdf, backup_xlsx, drawing
    pages, bpages = [], []
    sched = {}
    for n, key in enumerate(order, 1):
        mark, band = key
        packs = [q for r in G[key] for q in pack_for(res, st, cache, r)]
        r0 = G[key][0]
        gov = max(packs, key=lambda q: q['dcmax'])
        rg = next(r for r in G[key] if r['label'] == gov['label'])
        shmax = max(max(q['shear']['V2']['dc_lo'], q['shear']['V2']['dc_mid'], q['shear']['V3']['dc_lo'], q['shear']['V3']['dc_mid'])
                    for r in G[key] for q in r['per'])
        page_no = f'{mark}-{n:02d}'
        pages.append(dict(mark=mark, labels=sorted(r['label'] for r in G[key]), band=band, pack=packs,
                          sec=dict(b=rg['b'], h=rg['h'], fc=rg['fc'], fy=cfg['materials'].get('fy', 5000), bars=bars_txt(rg),
                                   shear=shmax, page=page_no),
                          ties_txt=f"{rg['nset']}ป{(' +' + str(rg['ncross']) + ' x-tie') if rg['ncross'] else ''} DB{rg['tie_db']} @{rg['so']}/{rg['s']} mm"))
        g = st['grids'][gov['gkey']]
        brows = []
        for q in packs:
            for i in range(len(q['dc'])):
                brows.append(dict(label=q['label'], story=q['story'], combo=q['meta'][i]['combo'], P=float(q['rows']['P'][i]),
                                  M3=float(q['rows']['M3'][i]), M2=float(q['rows']['M2'][i]), k=q['k'], Lu=q['Lu'], betad=q['betad'],
                                  Mxd=float(q['mg']['x']['Md'][i]), Myd=float(q['mg']['y']['Md'][i]), dc=float(q['dc'][i])))
        bpages.append(dict(name=f'{mark}_{band[0]}', title=f"{mark} {band[0]}→{band[1]}  {bars_txt(rg)}  f'c {rg['fc']}", S=gov['S'],
                           bars=LY.bars_cm(g, rg['db'], tuple(rg['counts'])), db=rg['db'], b=rg['b'], h=rg['h'], fc=rg['fc'],
                           fy=cfg['materials'].get('fy', 5000), rows=brows))
        rd = next((r for r in G[key] if r.get('ref')), rg)          # drawing in the orientation of the mark's reference label
        g = st['grids'][tuple(rd['gkey'])] if rd.get('gkey') else g
        T = LY.ties(g, rd['db'])
        rho = rg['As'] / (rg['b'] * rg['h']) * 100 if rg['shape'] == 'rect' else rg['As'] / (math.pi * rg['b'] ** 2 / 4) * 100
        dmax = max(q['dmax_y'] for r in G[key] for q in r['per'])
        dcm = max(q['dc'] for r in G[key] for q in r['per'])
        ng = [t for t, c in (('D/C>1', dcm > 1), ('δ>1.4', dmax > 1.4), ('ρ>6%', rho > 6), ('shear', shmax > 1)) if c]
        sched.setdefault(mark, {})[tuple(band)] = dict(gkey=tuple(rd['gkey']) if rd.get('gkey') else gov['gkey'], phase=rd.get('phase', 0), db=rd['db'], counts=tuple(rd['counts']), nbar=rd['nbar'],
                                                       nset=T['nset'], ncross=rd['ncross'], tie_db=rd['tie_db'], so=rd['so'], s=rd['s'],
                                                       T=T, lap=rd['lap'], labels=[r['label'] for r in G[key]],
                                                       check=(f"[CHECK] ρ={rho:.2f}%  D/C={dcm:.2f}  δy,max={dmax:.2f}" +
                                                              (f"  NG: {', '.join(ng)}" if ng else '  OK'), bool(ng)))
    calc_pdf.build(os.path.join(outdir, f'{job}_Column_Calc.pdf'), P, pages)
    backup_xlsx.build(os.path.join(outdir, f'{job}_Column_Backup.xlsx'), P, bpages)
    if per_mark:                                      # one calc PDF + one back-up Excel per mark (app downloads)
        md = os.path.join(outdir, 'marks'); os.makedirs(md, exist_ok=True)
        for mk in sorted({p['mark'] for p in pages}, key=lambda m: int(''.join(c for c in m if c.isdigit()) or 0)):
            calc_pdf.build(os.path.join(md, f'{job}_{mk}_Calc.pdf'), P, [p for p in pages if p['mark'] == mk])
            backup_xlsx.build(os.path.join(md, f'{job}_{mk}_Backup.xlsx'), P, [b for b in bpages if b['name'].split('_')[0] == mk])
    bands = [tuple(b) for b in res['bands']]
    drawing.build(sched, st['stories'], bands, st['fc_of'], P, st['grids'],
                  dict(pdf=os.path.join(outdir, f'{job}_Table_of_Column_DRAFT.pdf'), dxf=os.path.join(outdir, f'{job}_Table_of_Column_DRAFT.dxf'),
                       xlsx=os.path.join(outdir, f'{job}_Column_Schedule_DRAFT.xlsx')))
    print('outputs written to', outdir)


if __name__ == '__main__':
    a = sys.argv
    if '--detail' in a:
        i = a.index('--detail')
        main(a[1], (a[i + 1], a[i + 2]))
    else:
        main(a[1], per_mark='--per-mark' in a)
