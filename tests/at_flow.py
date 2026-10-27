"""AppTest flow on BKMPH02 (no browser): files -> run + f'c study -> case 600/3F -> fix board -> apply -> final check -> results.
   python3 tests/at_flow.py <BKMPH02 folder>"""
import sys, os, time, json
from streamlit.testing.v1 import AppTest
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
D = sys.argv[1]
rd = lambda n: (n, open(os.path.join(D, n), 'rb').read())
at = AppTest.from_file(os.path.join(HERE, 'app.py'), default_timeout=900)
at.run()
import app_io as AIO
files = {s: [] for s in AIO.SLOTS}
files['seismic'] = [rd('01 Seismic model.xlsx')]; files['full_unreduced'] = [rd('02 Full Gravity.xlsx')]
files['combos'] = [rd('04 Load Combination.xlsx')]; files['workbook'] = [rd('BKMPH02_Column_Input_v136.xlsx')]
tpl = AIO.empty_tpl(); tpl.update(AIO.INPW.read_template(os.path.join(D, 'BKMPH02_Column_Input_v136.xlsx')))
if not tpl['lap_rows']:
    tpl['lap_rows'] = AIO.INPW.read_lap_table(os.path.join(D, 'Development of Reinforcement Table.xlsx'), '40mm')[0]
at.session_state['files'] = files; at.session_state['tpl'] = tpl
def go(p):
    at.session_state['_goto'] = p; at.run()


SNAP_KEYS = ('workdir', 'files', 'tpl', 'ovl_ok', 'ovl_meta', 'out', 'extra_log', 'lap_sheet', 'nrun', 'cases', 'case', 'approved',
             'act', 'props', 'groups', 'prev', 'rounds', 'etabs_done', 'out_old', 'final', 'prov_ok', 'engineer', 'rfiles', 'wd',
             'last_match', 'rename', 'pm', 'page')


def snap(name):
    import pickle
    d = {k: at.session_state[k] for k in SNAP_KEYS if k in at.session_state}
    pickle.dump(d, open(os.path.join(HERE, 'tests', name), 'wb'))
def exc():
    return [e.value for e in at.exception]
go('3 Check & run')
print('check page exceptions', exc())
[cb.check() for cb in at.checkbox]; at.run()
t0 = time.time()
btn = next(b for b in at.button if b.label.startswith('▶ Run design'))
btn.click(); at.run()
print('run+study', round(time.time() - t0), 's', exc(), 'cases', len(at.session_state['cases']['cases']))
go("4 f'c study")
print('fc page', exc())
sb = next(s for s in at.selectbox if s.label == 'Case')
cid = next(c['id'] for c in at.session_state['cases']['cases'] if c['fc_bottom'] == 600 and c['reduce_at'] == '3F')
sb.set_value(cid); at.run()
at.text_input[0].input('Test Engineer'); at.run()
t0 = time.time()
next(b for b in at.button if b.label.startswith('Use this case')).click(); at.run()
print('case run', round(time.time() - t0), 's', exc(), at.session_state['case'])
go('5 Fix board')
print('fix page', exc())
print('metrics', [(m.label, m.value) for m in at.metric])
t0 = time.time()
next(b for b in at.button if b.label == 'Preview all rows').click(); at.run()
print('proposals', round(time.time() - t0), 's', exc())
print('chosen', [c.value for c in at.caption if any(k in c.value for k in ('within ', 'diameter ', 'short ', 'long ', 'ratio '))][:8])
snap('snap_fix.pkl')
for ti in at.text_input:
    if ti.placeholder == 'Reason (required)':
        ti.input('Low D/C; basement braced by walls (test)')
at.run()
eng = next(t for t in at.text_input if t.label.startswith('Engineer'))
eng.input('Test Engineer'); at.run()
t0 = time.time()
next(b for b in at.button if b.label.startswith('✔ Apply all actions')).click(); at.run()
print('apply', round(time.time() - t0), 's', exc(), [e.value for e in at.error][:5])
print('page now', at.session_state['page'], 'enlarge', at.session_state['tpl']['enlarge'], 'approved', at.session_state['approved'])
res = json.load(open(os.path.join(at.session_state['out'], 'results.json')))
from collections import Counter
print('status', Counter(q['status'] for r in res['results'] for q in r['per']))
go('6 Final check')
print('final page', exc(), [(m.label, m.value) for m in at.metric])
print('warnings', [w.value[:120] for w in at.warning][:3])
at.session_state['rfiles'] = {'seismic': files['seismic'], 'full_unreduced': files['full_unreduced']}
at.run()
b = next(b for b in at.button if b.label.startswith('▶ Re-check round'))
t0 = time.time(); b.click(); at.run()
print('round2 attempt (same exports)', round(time.time() - t0), 's', exc(), 'rounds', len(at.session_state['rounds']),
      'match', [(m['label'], m['design'], m['export'], m['ok']) for m in at.session_state['last_match']])
# round 2 simulated: the enlarged sizes are given as designer sections (the template is turned into ETABS-style tables, so the
# engine reads them like a new export). Forces stay the old ones – this checks the pipeline, not the physics.
enl = at.session_state['tpl']['enlarge']
# keep the designer's own Sections rows (BKMPH02 has some), add the enlarged sizes per label-story range
at.session_state['tpl']['sections'] = list(at.session_state['tpl'].get('sections') or []) + [[r[0], r[1], r[2], r[3], r[4], r[5]] for r in enl]
at.session_state['rfiles'] = {'seismic': files['seismic'], 'full_unreduced': files['full_unreduced']}
at.run()
b = next(b for b in at.button if b.label.startswith('▶ Re-check round'))
t0 = time.time(); b.click(); at.run()
print('round2 (sizes in the export)', round(time.time() - t0), 's', exc(), 'rounds', len(at.session_state['rounds']),
      'match ok', all(m['ok'] for m in at.session_state['last_match']), 'provisional', at.session_state['etabs_done'])
print('round2 metrics', [(m.label, m.value) for m in at.metric])
print('round2 info', [w.value[:100] for w in at.warning][:3], [s_.value[:80] for s_ in at.success][:3])
fb = [b.label for b in at.button if b.label.startswith('Mark FINAL')]
print('final button', fb, [b.disabled for b in at.button if b.label.startswith('Mark FINAL')])
if fb and not next(b for b in at.button if b.label.startswith('Mark FINAL')).disabled:
    old = dict(json.load(open(os.path.join(at.session_state['out'], 'results.json')))['marks'])
    t0 = time.time(); next(b for b in at.button if b.label.startswith('Mark FINAL')).click(); at.run()
    new = json.load(open(os.path.join(at.session_state['out'], 'results.json')))['marks']
    print('FINAL', round(time.time() - t0), 's', at.session_state['final'], exc(), 'renamed', sum(1 for k in new if new[k] != old.get(k)))
go('7 Results')
snap('snap_final.pkl')
print('results exc', exc(), [(m.label, m.value) for m in at.metric][:6])
go('8 Documents')
print('docs exc', exc())
json.dump(dict(out=at.session_state['out'], enlarge=at.session_state['tpl']['enlarge'], approved=at.session_state['approved']),
          open(os.path.join(HERE, 'tests', 'at_flow_state.json'), 'w'))
