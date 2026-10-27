"""Fix board tools (v1.5.0, CEDA 27 Oct 2026) – used by the app's fix board (step 5) and final check (step 6).

  ranges_for(outdir, label, failing, option)        stories that get the new size: option 1 = Table-of-Column row(s) of the
                                                    failing stories, option 2 = failing story down to the lowest story
  proposals(outdir, label, failing, option, ...)    enlargement proposals in 50 mm steps up to +500 mm per side:
                                                    'within' (inside the larger section below, keep the common side) first,
                                                    then short side / long side / keep b/h ratio; circular: diameter.
                                                    Every enlarged story is checked with D/C <= target (0.90, margin for the
                                                    force the larger section attracts) with the forces of the current export.
  check_size(...)                                   a typed size, same check
  approve_check(outdir, label, story, rho_ask)      passes with ρ up to the approval limit?
  etabs_update_xlsx(overrides, path, marks)         Excel list of new sizes for the ETABS update
  section_match(outdir, overrides)                  sizes in a new export vs the design sizes
  compare(old, new, ddc)                            round compare old vs new forces (results.json dicts)
  reduction_share(outdir, story, rho_low)           share of columns at ρ <= 1.5 % at the reduction story (warning in round 2)
Bar continuity at a section change (offset bend for the lap) is flagged with the face offset; the limit (75 mm, ACI 318-19
§10.7.4.1) is to be confirmed by the engineer – Code reference stated, not a substitute for the detail check.
"""
import os, sys, json, math, pickle, copy
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import quick_check as QC   # noqa: E402
import fc_study as FS      # noqa: E402

OFFSET_LIMIT_MM = 75.0


def _st(outdir):
    return QC._state(outdir)['st']


def _res(outdir):
    return json.load(open(os.path.join(outdir, 'results.json')))


def label_stories(st, label):
    return [s for s in st['stories'] if (label, s) in st['cols']]


def dims(st, label, story):
    c = st['cols'][(label, story)]
    return c['shape'], round(c['b'] * 10), round(c['h'] * 10)


def ranges_for(outdir, label, failing, option=2):
    st, res = _st(outdir), _res(outdir)
    ls = label_stories(st, label)
    fl = [s for s in ls if s in set(failing)]
    if not fl:
        return []
    if int(option) == 2:
        top = max(ls.index(s) for s in fl)
        return ls[:top + 1]
    out = set()
    for r in res['results']:
        if r['label'] == label and any(s in r['stories'] for s in fl):
            out |= set(r['stories'])
    return [s for s in ls if s in out]


def _apply(st, label, rng, shape, b, h, option):
    """new dims per story of the range: option 2 keeps a larger existing side of a lower story."""
    out = {}
    for s in rng:
        sh0, b0, h0 = dims(st, label, s)
        if shape == 'circ':
            d = max(b, b0) if (option == 2 and sh0 == 'circ') else b
            out[s] = ('circ', d, d)
        else:
            out[s] = ('rect', max(b, b0), max(h, h0)) if option == 2 and sh0 == 'rect' else ('rect', b, h)
    return out


def _vol_add(st, label, newd):
    add = 0.0
    for s, (sh, b, h) in newd.items():
        c = st['cols'][(label, s)]
        H = c.get('H') or c['Lu']
        A0 = math.pi * c['b'] ** 2 / 4 if c['shape'] == 'circ' else c['b'] * c['h']
        A1 = math.pi * (b / 10) ** 2 / 4 if sh == 'circ' else (b / 10) * (h / 10)
        add += (A1 - A0) * H / 1e6
    return round(add, 2)


def _changes(st, label, newd):
    ls = label_stories(st, label)
    seq = [newd.get(s, dims(st, label, s)) for s in ls]
    n, warn, offs = 0, [], []
    for i in range(1, len(seq)):
        lo, up = seq[i - 1], seq[i]
        if lo != up:
            n += 1
            if lo[0] == up[0] == 'rect':
                off = max(abs(up[1] - lo[1]), abs(up[2] - lo[2])) / 2
                if up[1] > lo[1] or up[2] > lo[2]:
                    warn.append(f'larger section above a smaller one at {ls[i]} ({up[1]}×{up[2]} on {lo[1]}×{lo[2]})')
            else:
                off = abs(up[1] - lo[1]) / 2
                if up[1] > lo[1]:
                    warn.append(f'larger section above a smaller one at {ls[i]} (Ø{up[1]} on Ø{lo[1]})')
            offs.append(dict(at=ls[i], offset_mm=off, offset_bend=off < OFFSET_LIMIT_MM))
    return n, warn, offs


def check_size(outdir, label, rng, shape, b_mm, h_mm, failing, option=2, target=0.90):
    """check every story of the range that gets a new size (D/C <= target); stories whose size does not change are skipped."""
    st = _st(outdir)
    newd = _apply(st, label, rng, shape, b_mm, h_mm, option)
    per, ok = [], True
    for s, (sh, b, h) in newd.items():
        if (sh, b, h) == dims(st, label, s):
            continue
        r = QC.check(outdir, label, s, shape=sh, b_mm=b, h_mm=h, dc_lim=target)
        good = r['status'] in ('OK',) or (r['ok'] and r['dc'] <= target + 1e-9)
        ok = ok and good
        per.append(dict(story=s, section=r['section'], dc=r['dc'], bars=r['bars'], rho=r['rho_pct'], ok=good, failing=s in failing))
    n, warn, offs = _changes(st, label, newd)
    n0 = _changes(st, label, {})[0]
    sh0, b0, h0 = dims(st, label, failing[0] if failing else rng[-1])
    A0 = math.pi * b0 ** 2 / 4 if sh0 == 'circ' else b0 * h0
    A1 = math.pi * b_mm ** 2 / 4 if shape == 'circ' else b_mm * h_mm
    # stories whose size really changes, as contiguous segments of one size (a larger existing side below is kept, option 2)
    ls = label_stories(st, label)
    segs = []
    for s in ls:
        if s in newd and newd[s] != dims(st, label, s):
            if segs and segs[-1]['dims'] == newd[s] and ls.index(segs[-1]['to']) == ls.index(s) - 1:
                segs[-1]['to'] = s
            else:
                segs.append(dict(frm=s, to=s, dims=newd[s]))
    return dict(shape=shape, b=b_mm, h=h_mm, ok=ok and bool(per), per=per, dc_max=max((p['dc'] for p in per), default=None),
                segments=[dict(story_from=g['frm'], story_to=g['to'], shape=g['dims'][0], b=g['dims'][1], h=g['dims'][2]) for g in segs],
                area_pct=round((A1 / A0 - 1) * 100), concrete_add_m3=_vol_add(st, label, newd), section_changes=n, section_changes_added=n - n0, warnings=warn,
                offsets=offs, range=rng, option=option)


def proposals(outdir, label, failing, option=2, target=0.90, step=50, max_add=500):
    st = _st(outdir)
    rng = ranges_for(outdir, label, failing, option)
    if not rng:
        return dict(range=[], options=[])
    top = max(failing, key=lambda s: st['stories'].index(s))
    sh, b0, h0 = dims(st, label, top)
    k = int(max_add // step)
    out = []
    if sh == 'circ':
        for i in range(1, k + 1):
            r = check_size(outdir, label, rng, 'circ', b0 + step * i, b0 + step * i, failing, option, target)
            if r['ok']:
                r['kind'] = 'diameter'; out.append(r); break
        return dict(range=rng, options=out, current=(sh, b0, h0))
    # within the larger section below (keep the common side) – CEDA 27 Oct 2026
    ls = label_stories(st, label)
    lower = [s for s in ls[:ls.index(top) + 1] if s not in failing] or ls[:1]
    bx = max([dims(st, label, s)[1] for s in lower if dims(st, label, s)[0] == 'rect'] + [b0])
    hx = max([dims(st, label, s)[2] for s in lower if dims(st, label, s)[0] == 'rect'] + [h0])
    within = sorted({(b, h) for b in range(b0, bx + 1, step) for h in range(h0, hx + 1, step)} - {(b0, h0)}, key=lambda x: (x[0] * x[1], x))
    for b, h in within:
        r = check_size(outdir, label, rng, 'rect', b, h, failing, option, target)
        if r['ok']:
            r['kind'] = 'within'; out.append(r); break
    short_is_b = b0 <= h0
    seqs = {'short': [(b0 + step * i, h0) if short_is_b else (b0, h0 + step * i) for i in range(1, k + 1)],
            'long': [(b0, h0 + step * i) if short_is_b else (b0 + step * i, h0) for i in range(1, k + 1)],
            'ratio': []}
    s0, l0 = min(b0, h0), max(b0, h0)
    for i in range(1, k + 1):
        ns = s0 + step * i
        nl = int(math.ceil(l0 * ns / s0 / step) * step)
        if nl - l0 <= max_add:
            seqs['ratio'].append((ns, nl) if short_is_b else (nl, ns))
    for kind, seq in seqs.items():
        for b, h in seq:
            r = check_size(outdir, label, rng, 'rect', b, h, failing, option, target)
            if r['ok']:
                r['kind'] = kind; out.append(r); break
    return dict(range=rng, options=out, current=(sh, b0, h0))


def approve_check(outdir, label, story, rho_ask=0.07):
    return QC.check(outdir, label, story, rho_max=rho_ask)


def etabs_update_xlsx(overrides, path, marks=None):
    import openpyxl
    from openpyxl.styles import Font, PatternFill
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = 'ETABS_update'
    ws.append(['CEDA column design – sections enlarged on the fix board. Update the frame sections in every ETABS model, run again '
               'and upload the new exports (step 6 C). Forces of the current design are PROVISIONAL.'])
    hdr = ['label', 'mark', 'story_from', 'story_to', 'old_section', 'new_shape', 'new_b_mm', 'new_h_mm', 'option', 'chosen', 'ETABS frame section']
    ws.append(hdr)
    for c in ws[2]:
        c.font = Font(bold=True); c.fill = PatternFill('solid', fgColor='D9E1F2')
    for o in overrides:
        ws.append([o['label'], (marks or {}).get(o['label'], ''), o['story_from'], o['story_to'], o.get('old', ''), o.get('shape', 'rect'),
                   o['b_mm'], o.get('h_mm') or o['b_mm'], o.get('option', 2), o.get('kind', ''), o.get('etabs_name', '')])
    for col, w in zip('ABCDEFGHIJK', (10, 8, 11, 11, 16, 10, 10, 10, 8, 14, 24)):
        ws.column_dimensions[col].width = w
    wb.save(path)
    return path


def section_match(outdir, overrides):
    st = _st(outdir)
    rows = []
    for o in overrides:
        ls = st['stories']
        if o['story_from'] not in ls or o['story_to'] not in ls:
            rows.append(dict(label=o['label'], stories=f"{o['story_from']}–{o['story_to']}", design='', export='story not found', ok=False)); continue
        i0, i1 = sorted((ls.index(o['story_from']), ls.index(o['story_to'])))
        want = (o.get('shape', 'rect'), round(o['b_mm']), round(o.get('h_mm') or o['b_mm']))
        got = set()
        for s in ls[i0:i1 + 1]:
            if (o['label'], s) in st['cols']:
                got.add(dims(st, o['label'], s))
        okk = got == {want} or (want[0] == 'rect' and got == {('rect', want[2], want[1])})
        fmt = lambda d: f'Ø{d[1]}' if d[0] == 'circ' else f'{d[1]}×{d[2]}'
        rows.append(dict(label=o['label'], stories=f"{o['story_from']}–{o['story_to']}", design=fmt(want),
                         export=', '.join(fmt(d) for d in sorted(got)) or '—', ok=okk))
    return rows


def _index(res):
    out = {}
    for r in res['results']:
        for q in r['per']:
            out[(r['label'], q['story'])] = dict(dc=q['dc'], status=q['status'], P=q['gov']['P'], M=math.hypot(q['gov']['Mx'], q['gov']['My']),
                                                 bars=f"{r['nbar']}-DB{r['db']}", mark=r['mark'],
                                                 section=f"Ø{r['b']*10:.0f}" if r['shape'] == 'circ' else f"{r['b']*10:.0f}×{r['h']*10:.0f}",
                                                 enlarged=r.get('enlarged', False))
    return out


def compare(old, new, ddc=0.05):
    a, b = _index(old), _index(new)
    rows = []
    for k in sorted(set(a) & set(b), key=lambda k: (new['stories'].index(k[1]) if k[1] in new['stories'] else 0, k[0])):
        x, y = a[k], b[k]
        d = y['dc'] - x['dc']
        why = []
        if y['enlarged'] or x['enlarged']:
            why.append('enlarged')
        if abs(d) > ddc:
            why.append('changed')
        if y['status'] == 'REVISE':
            why.append('failing')
        rows.append(dict(label=k[0], story=k[1], section=y['section'], dc_old=round(x['dc'], 3), dc_new=round(y['dc'], 3), d=round(d, 3),
                         dP_pct=round((y['P'] / x['P'] - 1) * 100, 1) if x['P'] else None,
                         dM_pct=round((y['M'] / x['M'] - 1) * 100, 1) if x['M'] else None,
                         status=y['status'], bars_changed=x['bars'] != y['bars'], mark_changed=x['mark'] != y['mark'], why=why))
    summ = dict(failing=sum(1 for r in rows if r['status'] == 'REVISE'), changed=sum(1 for r in rows if abs(r['d']) > ddc),
                bars_changed=sum(1 for r in rows if r['bars_changed']),
                marks_changed=len({r['label'] for r in rows if r['mark_changed']}))
    return rows, summ


def reduction_share(outdir, story, rho_low=0.015):
    res = _res(outdir)
    n = lo = 0
    for r in res['results']:
        for q in r['per']:
            if q['story'] == story:
                n += 1; lo += q['rho'] <= rho_low + 1e-9
    return (lo / n) if n else None
