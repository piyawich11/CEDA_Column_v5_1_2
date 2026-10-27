"""App v5 tests – run:  python3 tests/test_app.py ["<BKMPH02 folder>"]   -> ALL PASS
A  bundled skill self-test (engine/ceda-column-design) prints ALL PASS
B  app pipeline == skill CLI on the synthetic 3-model set; run without documents, documents on request; project file round trip
C  BKMPH02 (01 Seismic model, 02 Full Gravity, 04 Load Combination, Development of Reinforcement Table, BKMPH02_Column_Input_v136
   [+ expected_results.json]): fixed f'c run == final BKMPH02 run; v1.5 f'c cases (600/3F: 9 failing = 4 ρ 6–8 + 5 enlarge;
   recommended 500/1M at 10 %, 450/1M at 15–25 %); fix-board preview C75 B2 (overload 1.10 -> ACCEPTED, 1000×1100 -> OK);
   size proposals ≤ 0.90; only confirmed overload applied
"""
import os, sys, json, subprocess, tempfile, shutil, copy
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import app_io as AIO  # noqa: E402

fails = []


def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f'  [{info}]' if info else ''))
    if not cond:
        fails.append(name)


SK = AIO.SKILL
PY = [sys.executable, '-I']
tmp = tempfile.mkdtemp()
sig = lambda R: sorted((r['label'], q['story'], r['mark'], r['nbar'], r['db'], tuple(r['counts']), round(q['dc'], 4), q['status'])
                       for r in R['results'] for q in r['per'])
# ---------------------------------------------------------------- A
r = subprocess.run(PY + [os.path.join(SK, 'scripts', 'selftest.py'), SK], cwd=tmp, capture_output=True, text=True)
check(f'A skill v{AIO.ENGINE_VERSION} self-test ALL PASS', 'ALL PASS' in r.stdout, (r.stdout.strip().splitlines() or [r.stderr[-300:]])[-1])

# ---------------------------------------------------------------- B synthetic set
subprocess.run(PY + [os.path.join(SK, 'tests', 'fixtures', 'make_synthetic_etabs.py'), tmp], check=True, capture_output=True)
rd = lambda f: AIO.read_upload(os.path.join(tmp, f))[:2]
S, FR, FU = rd('seis.xlsx'), rd('full_red.xlsx'), rd('full_unred.xlsx')
tpl = AIO.empty_tpl(); tpl['exclude'] = ['U_B_99']; tpl['criteria'] = {'project.job': 'PAR', 'slender.sway': 'non-sway'}
p3 = AIO.prepare({'seismic': S, 'full_unreduced': FU, 'full_reduced': FR}, None, tpl)
dB = os.path.join(tmp, 'B'); os.makedirs(dB)
resB, outB = AIO.run_engine(dB, AIO.build_cfg(p3, dB, {}))
check('B run without documents (design only)', os.path.exists(os.path.join(outB, 'results.json')) and not AIO.documents_ready(outB)
      and not os.path.isdir(os.path.join(outB, 'marks')))
wb = os.path.join(tmp, 'tplB.xlsx'); open(wb, 'wb').write(AIO.INPW.make_template(p3['found'], tpl))
dC = os.path.join(tmp, 'Bcli')
subprocess.run(PY + [os.path.join(SK, 'scripts', 'prepare_inputs.py'), dC, '--seismic', os.path.join(tmp, 'seis.xlsx'),
                     '--full-reduced', os.path.join(tmp, 'full_red.xlsx'), '--full-unreduced', os.path.join(tmp, 'full_unred.xlsx'),
                     '--workbook', wb], capture_output=True, text=True)
subprocess.run(PY + [os.path.join(SK, 'scripts', 'run.py'), os.path.join(dC, 'config.json'), os.path.join(dC, 'OUT')], capture_output=True, check=True)
resC = json.load(open(os.path.join(dC, 'OUT', 'results.json')))
check('B app pipeline == skill CLI (labels, stories, marks, bars, D/C, status)', sig(resB) == sig(resC), f'{len(sig(resB))} rows')
AIO.make_documents(outB)
main_f, per = AIO.files(outB)
check('B documents on request: calc PDF, back-up, Table of Column DXF/PDF, per-mark files',
      AIO.documents_ready(outB) and all(any(n.endswith(x) for _, n, _ in main_f) for x in ('_Calc.pdf', '_Backup.xlsx', '_DRAFT.dxf', '_DRAFT.pdf'))
      and len(per) == len(set(resB['marks'].values())))
files = {'seismic': [('seis.xlsx', open(os.path.join(tmp, 'seis.xlsx'), 'rb').read())], 'full_unreduced': [], 'full_reduced': [],
         'combos': [], 'lap': [], 'workbook': []}
z = AIO.save_project(files, tpl, dict(lap_sheet='40mm'))
f2, t2, m2 = AIO.load_project(z)
check('B project file round trip (files, inputs, lap sheet; no overload confirmation stored)',
      f2['seismic'] == files['seismic'] and t2['criteria'] == tpl['criteria'] and m2['lap_sheet'] == '40mm' and 'ovl' not in json.dumps(m2))

# ---------------------------------------------------------------- C BKMPH02
D = sys.argv[1] if len(sys.argv) > 1 else None
if D and os.path.exists(os.path.join(D, '02 Full Gravity.xlsx')):
    S = AIO.read_upload(os.path.join(D, '01 Seismic model.xlsx'))[:2]
    G = AIO.read_upload(os.path.join(D, '02 Full Gravity.xlsx'))[:2]
    C = AIO.read_upload(os.path.join(D, '04 Load Combination.xlsx'))[:2]
    tplK = AIO.INPW.read_template(os.path.join(D, 'BKMPH02_Column_Input_v136.xlsx'))
    tplK.setdefault('prices_rows', [])
    if not tplK['lap_rows']:
        tplK['lap_rows'] = AIO.INPW.read_lap_table(os.path.join(D, 'Development of Reinforcement Table.xlsx'), '40mm')[0]
    pK = AIO.prepare({'seismic': S, 'full_unreduced': G, 'full_reduced': None}, C, tplK)
    ok = {(a, b): c for a, b, c in tplK['overload']}
    dK = os.path.join(tmp, 'K'); os.makedirs(dK)
    resK, outK = AIO.run_engine(dK, AIO.build_cfg(pK, dK, ok))
    ref = os.path.join(D, 'expected_results.json')
    if os.path.exists(ref):
        check('C fixed f\'c: app == final BKMPH02 run (1,277 label-stories)', sig(resK) == sig(json.load(open(ref))))
    prices = dict(concrete={'400': 2600, '450': 2700, '500': 2850, '560': 3000, '600': 3150, '700': 3500},
                  steel={'12': 24, '16': 23.5, '20': 23.5, '25': 23.5, '28': 24, '32': 24})
    cs = AIO.FS.cases_from_state(outK, prices)
    by = {(c['fc_bottom'], c['reduce_at']): c for c in cs['cases']}
    c6 = next((c for k, c in by.items() if k == (600, '3F')), None)
    rec = {k: (cs['cases'][i]['fc_bottom'], cs['cases'][i]['reduce_at']) for k, i in cs['rec'].items()}
    check("C f'c cases: 600/3F 9 failing (4 ρ 6–8, 5 enlarge); recommended 500/1M (10 %), 450/1M (15–25 %); every case priced",
          c6 is not None and (c6['n_fail'], c6['n_rho'], c6['n_enlarge']) == (9, 4, 5)
          and rec.get('10') == (500, '1M') and all(rec.get(k) == (450, '1M') for k in ('15', '20', '25'))
          and all(c['cost_thb'] for c in cs['cases']), f"{rec} 600/3F {c6 and (c6['n_fail'], c6['n_rho'], c6['n_enlarge'])}")
    q1 = AIO.quick(outK, 'C75', 'B2')
    q2 = AIO.quick(outK, 'C75', 'B2', dc_lim=1.10)
    q3 = AIO.quick(outK, 'C75', 'B2', b_mm=1000, h_mm=1100)
    check('C fix-board preview C75 B2: no action REVISE, overload 1.10 -> ACCEPTED, 1000×1100 -> OK with ETABS note',
          q2['status'] == 'ACCEPTED' and q3['status'] == 'OK' and 'ETABS' in q3['note'], f"{q1['status']} {q2} {q3['status']}")
    pr = AIO.FX.proposals(outK, 'C75', ['B2'], option=2)['options']
    check('C size proposals C75 B2 (option 2): every proposal D/C ≤ 0.90 (target), 50 mm steps',
          pr and all(p_['dc_max'] <= 0.90 + 1e-9 for p_ in pr) and all(p_['b'] % 50 == 0 and p_['h'] % 50 == 0 for p_ in pr),
          [(p_['kind'], p_['b'], p_['h'], round(p_['dc_max'], 3)) for p_ in pr][:4])
    one = dict(list(ok.items())[:1])
    dK2 = os.path.join(tmp, 'K2'); os.makedirs(dK2)
    cfg2 = AIO.build_cfg(pK, dK2, one)
    res2, _ = AIO.run_engine(dK2, cfg2)
    st2 = {}
    for x in res2['results']:
        for q in x['per']:
            st2[q['status']] = st2.get(q['status'], 0) + 1
    check('C only the confirmed overload row is applied (1 ACCEPTED, 4 REVISE, 4 pending)',
          st2.get('ACCEPTED') == 1 and st2.get('REVISE') == 4 and len(cfg2['accept_overload_pending']) == 4, str(st2))
    q = AIO.boq(outK, prices)
    check('C quantities + cost of the final design', sum(q['concrete_m3'].values()) > 3000 and q['cost_thb'] and not q['cost_missing'],
          f"{sum(q['concrete_m3'].values()):.1f} m³, {sum(q['steel_kg'].values()) / 1000:.1f} t, THB {q['cost_thb']:,.0f}")
else:
    print('SKIP C (pass the BKMPH02 folder)')
shutil.rmtree(tmp, ignore_errors=True)
print('ALL PASS' if not fails else f'{len(fails)} FAILED: {fails}')
sys.exit(1 if fails else 0)
