"""AppTest of any project folder (no browser): files -> check & run + f'c study -> recommended case -> fix board (proposals).
Stops before Apply: the fix-board decisions are the designer's.
   python3 tests/at_project.py <folder with 01 Seismic model / 02 Full Gravity / 04 Load Combination / lap table / workbook>"""
import sys, os, time, json, glob, pickle
from streamlit.testing.v1 import AppTest
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import app_io as AIO
D = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, 'tests', 'at_project.json')
rd = lambda p: (os.path.basename(p), open(p, 'rb').read())
pick = lambda pat: [rd(p) for p in sorted(glob.glob(os.path.join(D, pat)))]
files = {s: [] for s in AIO.SLOTS}
files['seismic'] = pick('*Seismic*.xlsx'); files['full_unreduced'] = pick('*Full Gravity*.xlsx') or pick('*Unreduced*.xlsx')
files['full_reduced'] = pick('*Reduced*.xlsx'); files['combos'] = pick('*Load Combination*.xlsx')
wb = (glob.glob(os.path.join(D, '*Column_Input*.xlsx')) + [None])[0]
lap = (glob.glob(os.path.join(D, '*Development*.xlsx')) + [None])[0]
files['workbook'] = [rd(wb)] if wb else []
tpl = AIO.empty_tpl()
if wb:
    tpl.update(AIO.INPW.read_template(wb))
sheet = None
if lap and not tpl['lap_rows']:
    sheets = AIO.INPW.lap_sheets(lap); sheet = next((s for s in sheets if s.startswith('40')), sheets[0])
    tpl['lap_rows'] = AIO.INPW.read_lap_table(lap, sheet)[0]
    files['lap'] = [rd(lap)]
R = dict(files={k: [n for n, _ in v] for k, v in files.items()}, lap_sheet=sheet)
at = AppTest.from_file(os.path.join(HERE, 'app.py'), default_timeout=1800)
at.run()
at.session_state['files'] = files; at.session_state['tpl'] = tpl; at.session_state['lap_sheet'] = sheet


def go(p):
    at.session_state['_goto'] = p; at.run()


exc = lambda: [e.value for e in at.exception]
go('3 Check & run')
R['check_exc'] = exc()
R['route'] = [w.value for w in at.warning] + [c.value for c in at.caption][:6]
R['input_check'] = at.dataframe[0].value.to_dict('records') if at.dataframe else None
R['errors_check'] = [e.value for e in at.error]
R['metrics_check'] = [(m.label, m.value) for m in at.metric]
print('check', R['check_exc'], R['metrics_check'], R['errors_check'])
[cb.check() for cb in at.checkbox]; at.run()
btn = next(b for b in at.button if b.label.startswith('▶ Run design'))
print('run disabled?', btn.disabled)
t0 = time.time(); btn.click(); at.run()
R['run_s'] = round(time.time() - t0); R['run_exc'] = exc()
cs = at.session_state['cases']
print('run', R['run_s'], 's', R['run_exc'], 'cases', len(cs['cases']) if cs else None)
R['cases'] = [{k: c.get(k) for k in ('id', 'fc_bottom', 'reduce_at', 'type', 'n_fail', 'n_rho', 'n_enlarge', 'n_never', 'above', 'max_fail_share',
                                       'fcov_n', 'fcov_pct', 'low50_pct', 'low75_pct', 'checked', 'hi_m3', 'typ_m3', 'steel_t', 'cost_thb')}
              | dict(fails=[(f['label'], f['story'], f['kind']) for f in c['fails']]) for c in cs['cases']] if cs else []
R['rec'] = cs.get('rec') if cs else None; R['recommended'] = cs.get('recommended') if cs else None
R['never'] = cs.get('never') if cs else None; R['reduction_ok'] = cs.get('reduction_ok') if cs else None
R['fc_typical'] = cs.get('fc_typical') if cs else None
out1 = at.session_state['out']
res1 = json.load(open(os.path.join(out1, 'results.json')))
R['notes_study_run'] = res1.get('notes', [])[:40]
go("4 f'c study")
R['fc_exc'] = exc()
if cs and cs['cases']:
    cid = cs['recommended']
    R['chosen_case'] = cid
    sb = next(s for s in at.selectbox if s.label == 'Case'); sb.set_value(cid); at.run()
    next(t for t in at.text_input if t.label.startswith('Engineer')).input('Test Engineer'); at.run()
    t0 = time.time(); next(b for b in at.button if b.label.startswith('Use this case')).click(); at.run()
    R['case_run_s'] = round(time.time() - t0); R['case_exc'] = exc(); R['case'] = at.session_state['case']
    print('case', R['case'], R['case_run_s'], 's', R['case_exc'])
    go('5 Fix board')
    R['fix_exc'] = exc(); R['fix_metrics'] = [(m.label, m.value) for m in at.metric]
    print('fix', R['fix_exc'], R['fix_metrics'])
    pb = [b for b in at.button if b.label == 'Preview all rows']
    if pb:
        t0 = time.time(); pb[0].click(); at.run(); R['proposals_s'] = round(time.time() - t0)
    R['chosen'] = [c.value for c in at.caption if any(k in c.value for k in ('within ', 'diameter ', 'short ', 'long ', 'ratio ', 'open Detail', 'ρ '))][:30]
    out = at.session_state['out']
    res = json.load(open(os.path.join(out, 'results.json')))
    st_ = {}
    for r in res['results']:
        for q in r['per']:
            st_[q['status']] = st_.get(q['status'], 0) + 1
    R['status_after_case'] = st_
    R['failing_after_case'] = [(r['label'], q['story'], q['status'], round(float(q['dc']), 3), round(float(q['rho']) * 100, 2),
                                (f"Ø{r['b']*10:.0f}" if r['shape'] == 'circ' else f"{r['b']*10:.0f}×{r['h']*10:.0f}"), q['fc'])
                               for r in res['results'] for q in r['per'] if q['status'] != 'OK']
    R['delta_gt_14'] = [(r['label'], q['story'], round(max(float(q['dmax_x']), float(q['dmax_y'])), 2)) for r in res['results'] for q in r['per']
                        if max(float(q['dmax_x']), float(q['dmax_y'])) > 1.4]
    R['marks'] = len(set(res['marks'].values())); R['labels'] = len(res['marks']); R['stories'] = res['stories']
    R['label_stories'] = sum(len(r['per']) for r in res['results'])
    R['notes'] = res.get('notes', [])
    R['fc_of'] = res.get('fc_of')
    R['out'] = out
    groups = at.session_state['groups'].get(out) if isinstance(at.session_state['groups'], dict) else None
json.dump(R, open(OUT, 'w'), ensure_ascii=False, indent=1, default=str)
print('saved', OUT)
