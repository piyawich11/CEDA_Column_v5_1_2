"""CEDA RC Column Design – Streamlit v5.1 (front end of the ceda-column-design skill v1.5.0, engine/ceda-column-design).

v5.1: look of the UI mock-ups (ui.py, .streamlit/config.toml) – no design change.
Steps (sidebar): 1 Files · 2 Inputs · 3 Check & run · 4 f'c study · 5 Fix board · 6 Final check · 7 Results · 8 Documents
v5 (CEDA 27 Oct 2026): f'c case table A/B (fc_study.cases), ρ ≤ 6 % for every column until the fix board, fix board per
label (enlarge with proposals / approve ρ up to the approval limit / overload ticked per row / δ), final check with
rounds of new ETABS exports, mark names locked after the f'c case, column detail (surface + section).
The app never re-implements a design rule. Overload is never accepted without the designer (ticked every session).
"""
import os, io, json, hashlib, tempfile, datetime, copy
import pandas as pd
import streamlit as st
import app_io as AIO
from helptext import h
import ui

INPW = AIO.INPW
st.set_page_config(page_title='CEDA Column Design', layout='wide')
ui.css()
ss = st.session_state
for k, v in dict(workdir=tempfile.mkdtemp(prefix='ceda_col5_'), files={s: [] for s in AIO.SLOTS}, tpl=AIO.empty_tpl(),
                 ovl_ok={}, ovl_meta={}, visit=0, out=None, extra_log=[], lap_sheet=None, fix_ver=0, nrun=0,
                 cases=None, case=None, approved=[], act={}, props={}, groups={}, prev={}, rounds=[], etabs_done=[],
                 out_old=None, final=False, prov_ok=None, engineer='', msg=None, page='1 Files', rfiles={}).items():
    ss.setdefault(k, v)
SNAP_KEYS = ('workdir', 'files', 'tpl', 'ovl_ok', 'ovl_meta', 'out', 'extra_log', 'lap_sheet', 'nrun', 'cases', 'case', 'approved',
             'act', 'props', 'groups', 'prev', 'rounds', 'etabs_done', 'out_old', 'final', 'prov_ok', 'engineer', 'rfiles', 'wd',
             'last_match', 'rename', 'pm', 'page')
if os.environ.get('CEDA_SNAPSHOT') and not ss.get('_snap'):        # test / screenshot hook only (never set in normal use)
    import pickle
    for k, v in pickle.load(open(os.environ['CEDA_SNAPSHOT'], 'rb')).items():
        ss[k] = v
    ss._snap = True
FCS = [210, 240, 280, 320, 400, 450, 500, 560, 600, 700]
STEPS = ['1 Files', '2 Inputs', '3 Check & run', "4 f'c study", '5 Fix board', '6 Final check', '7 Results', '8 Documents']


# ================================================================================================ helpers
def md5(*parts):
    m = hashlib.md5()
    for p in parts:
        m.update(p if isinstance(p, bytes) else str(p).encode())
    return m.hexdigest()[:12]


def files_stamp(slots=('seismic', 'full_unreduced', 'full_reduced', 'combos')):
    return md5(*[n.encode() + d[:4096] + str(len(d)).encode() for s_ in slots for n, d in ss.files.get(s_, [])])


@st.cache_data(show_spinner='Reading ETABS tables …', max_entries=12)
def read_blobs(key, blobs):
    parts, info = [], []
    d = tempfile.mkdtemp()
    for name, data in blobs:
        p = os.path.join(d, name); open(p, 'wb').write(data)
        t, u, i = AIO.read_upload(p)
        parts.append((t, u)); info += i
    T, U = AIO.merge(parts)
    return T, U, info


def blob_path(name, data):
    p = os.path.join(tempfile.mkdtemp(), name); open(p, 'wb').write(data)
    return p


def models():
    out = {}
    for s_ in ('seismic', 'full_unreduced', 'full_reduced'):
        fl = ss.files.get(s_) or []
        out[s_] = read_blobs(md5(s_, *[n for n, _ in fl], *[len(d) for _, d in fl]), tuple(fl))[:2] if fl else None
    fl = ss.files.get('combos') or []
    cmb = read_blobs(md5('c', *[n for n, _ in fl], *[len(d) for _, d in fl]), tuple(fl))[:2] if fl else None
    if cmb and not cmb[0].get('Load Combination Definitions'):
        cmb = None
    return out, cmb


@st.cache_resource(max_entries=6, show_spinner='Preparing inputs …')
def _prep(stamp, tpl_json):
    m, c = models()
    return AIO.prepare(m, c, json.loads(tpl_json))


def prep_now():
    m, _ = models()
    if not m['seismic'] or not (m['full_unreduced'] or m['full_reduced']):
        return None
    return _prep(files_stamp(), json.dumps(ss.tpl, default=str, sort_keys=True))


def reset_run(msg=None):
    ss.out, ss.cases, ss.case, ss.out_old = None, None, None, None
    ss.act, ss.props, ss.groups, ss.prev, ss.rounds, ss.etabs_done, ss.final, ss.prov_ok = {}, {}, {}, {}, [], [], False, None
    ss.fix_ver += 1
    if msg:
        ss.msg = msg


def new_inputs():
    """inputs replaced from outside (workbook / project): fresh widgets, overload confirmations cleared."""
    for k in [k for k in ss.keys() if str(k).startswith(('cw_', 'base_', 'ed_'))]:
        del ss[k]
    ss.visit += 1
    ss.ovl_ok, ss.ovl_meta, ss.extra_log = {}, {}, []
    reset_run()


def DF(rows, cols):
    return pd.DataFrame([list(r)[:len(cols)] + [None] * (len(cols) - len(r)) for r in (rows or [])], columns=cols)


def back(df):
    return [[None if (isinstance(v, float) and v != v) else v for v in r] for r in df.astype(object).where(pd.notna(df), None).values.tolist()
            if not all(x is None or (isinstance(x, str) and not x.strip()) or (isinstance(x, float) and x != x) for x in r)]


def E(name, cols, rows, help_=None, column_config=None, dynamic=True, height=None):
    """data editor bound to ss.tpl rows; base captured once per page visit (no double-applied edits)."""
    bk = f'base_{name}_{ss.visit}'
    if bk not in ss:
        ss[bk] = DF(rows, cols)
    if help_:
        st.caption(help_)
    kw = dict(height=height) if height else {}
    df = st.data_editor(ss[bk], key=f'ed_{name}_{ss.visit}', hide_index=True, width='stretch',
                        num_rows='dynamic' if dynamic else 'fixed', column_config=column_config or {}, **kw)
    return back(df)


DEFAULTS = {k: d for k, d, u, n in INPW.CRITERIA}


def W(c, key, label, kind='text', options=None):
    """criteria widget bound to ss.tpl['criteria'][key] (workbook form), with the help text of the key."""
    k = 'cw_' + key
    cur = ss.tpl['criteria'].get(key)
    v = DEFAULTS.get(key) if INPW._blank(cur) else cur
    if k not in ss:
        if kind == 'yn':
            ss[k] = str(v).strip().upper().startswith('Y')
        elif kind == 'sel':
            opts = [str(o) for o in options]
            sv = '' if v is None else str(v)
            if sv not in opts:
                try:
                    sv = next(o for o in opts if o and float(o) == float(sv))
                except (StopIteration, ValueError):
                    sv = opts[0]
            ss[k] = sv
        elif kind == 'num':
            try:
                ss[k] = float(v)
            except (TypeError, ValueError):
                ss[k] = 0.0
        else:
            ss[k] = '' if v is None else str(v)
    if kind == 'yn':
        out = 'Y' if c.toggle(label, key=k, help=h(key)) else 'N'
    elif kind == 'sel':
        out = c.selectbox(label, [str(o) for o in options], key=k, help=h(key))
    elif kind == 'num':
        out = c.number_input(label, key=k, help=h(key))
    elif kind == 'optnum':
        s_ = c.text_input(label, key=k, help=h(key))
        try:
            out = None if not s_.strip() else float(s_)
        except ValueError:
            c.error(f'{label}: enter a number or leave blank'); out = None
    else:
        out = c.text_input(label, key=k, help=h(key))
    ss.tpl['criteria'][key] = out
    return out


def status_icon(ok):
    return '✔' if ok else '•'


# ================================================================================================ run helpers (v5)
def crit(key, default=None):
    v = ss.tpl['criteria'].get(key)
    return default if INPW._blank(v) else v


def rho_ask():
    c = INPW.to_cfg(ss.tpl)
    return c['detailing']['rho_ask']


def is_smf():
    return INPW.to_cfg(ss.tpl)['detailing']['rho_ask'] <= 0.06 + 1e-9 and str(crit('seismic.frame', '')).upper() == 'SMF'


def now():
    return datetime.datetime.now().strftime('%d %b %Y %H:%M')


def log(item, lab, story, val, basis, source='app v5'):
    ss.extra_log.append([item, lab, story, val, basis, source, now()])


def res_of(out=None):
    out = out or ss.out
    return json.load(open(os.path.join(out, 'results.json'))) if out and os.path.exists(os.path.join(out, 'results.json')) else None


def do_run(note=None, approved=None, renumber=False, study=False):
    """one engine run in its own folder (round compare keeps the old one). approved = ρ approvals decided on the fix board."""
    p = prep_now()
    ss.nrun += 1
    wd = os.path.join(ss.workdir, f'run{ss.nrun}')
    os.makedirs(wd, exist_ok=True)
    with st.status('Running the design (run.py) …', expanded=False) as stt:
        try:
            cfg = AIO.build_cfg(p, wd, ss.ovl_ok, approved=ss.approved if approved is None else approved,
                                in_etabs=set(tuple(x) for x in ss.etabs_done), renumber=renumber or study)
            if study:
                cfg['materials'].pop('fc_by_story', None)
            res, out = AIO.run_engine(wd, cfg)
            job = cfg['project'].get('job', 'job')
            json.dump(cfg, open(os.path.join(out, 'config_used.json'), 'w'), ensure_ascii=False, indent=1)
            tpl_used = dict(ss.tpl, approve=[list(x) for x in cfg['approved_rho_over_6']],
                            overload=[[l, s_, d] for (l, s_), d in sorted(ss.ovl_ok.items())])
            open(os.path.join(out, f'{job}_Column_Input_used.xlsx'), 'wb').write(INPW.make_template(p['found'], tpl_used))
            open(os.path.join(out, f'{job}_Column_Decisions_Log.xlsx'), 'wb').write(
                AIO.decisions_log(ss.tpl, cfg, res, p, ss.ovl_meta, extra=ss.extra_log))
            ss.out, ss.wd = out, wd
            ss.groups, ss.prev = {}, {}
            ss.fix_ver += 1
            if study:
                ss.cases = AIO.fc_cases(out)
            stt.update(label='Design done', state='complete')
            ss.msg = note or 'Design done.'
        except Exception as e:
            stt.update(label='Engine error', state='error'); st.exception(e); st.stop()
    return res


def lock_marks(res):
    ss.tpl['marks'] = [[l, m] for l, m in sorted(res['marks'].items(), key=lambda kv: (len(kv[0]), kv[0]))]


def provisional():
    return bool(ss.tpl.get('enlarge')) and not all((r[0], r[1], r[2]) in set(tuple(x) for x in ss.etabs_done) for r in ss.tpl['enlarge'])


# ================================================================================================ sidebar
if ss.get('_goto'):
    ss.page = ss.pop('_goto')
with st.sidebar:
    st.markdown(f'<div class="brand">CEDA Column Design<small>App v5.1 · engine ceda-column-design v{AIO.ENGINE_VERSION}</small></div>',
                unsafe_allow_html=True)
    m0, _ = models()
    have_files = bool(m0['seismic'] and (m0['full_unreduced'] or m0['full_reduced']))
    res0 = res_of()
    nrev = sum(1 for r in res0['results'] for q in r['per'] if q['status'] in ('REVISE', 'ASK_RHO')) if res0 else 0
    p0 = prep_now() if have_files else None
    job = ss.tpl['criteria'].get('project.job') or '–'
    info = (f"{len(p0['stories'])} stories · {len(p0['labels'])} column labels · {len(p0['label_story']):,} label-stories"
            if p0 else 'no ETABS files yet')
    with st.container(key='projbox'):
        st.markdown(f'<div class="proj">Project <b>{ui.esc(job)}</b><br>{info}'
                    + (' · <b>FINAL</b>' if ss.final else (' · PROVISIONAL' if ss.rounds else '')) + '</div>', unsafe_allow_html=True)
        st.download_button('Save project (.zip)', AIO.save_project(ss.files, ss.tpl, dict(lap_sheet=ss.lap_sheet, etabs_done=ss.etabs_done,
                           engineer=ss.engineer, case=ss.case)),
                           f"{ss.tpl['criteria'].get('project.job') or 'JOB'}_column_project.zip", help=h('save_project'),
                           disabled=not any(ss.files.values()), width='stretch')
        with st.popover('Open project…', width='stretch', help=h('f_project')):
            pj = st.file_uploader('Open project (.zip)', type=['zip'], key='up_project', help=h('f_project'))
    if pj is not None and ss.get('_pj') != md5(pj.name, len(pj.getvalue())):
        ss._pj = md5(pj.name, len(pj.getvalue()))
        f_, t_, meta = AIO.load_project(pj.getvalue())
        ss.files, ss.tpl, ss.lap_sheet = f_, t_, meta.get('lap_sheet')
        new_inputs()
        ss.etabs_done = meta.get('etabs_done', []); ss.engineer = meta.get('engineer', '')
        ss.msg = f'Project opened: {pj.name} – overload ticks are asked again'
        st.rerun()
    states = {'1 Files': 'done' if have_files else 'todo', '2 Inputs': 'done' if have_files and ss.cases else 'todo',
              '3 Check & run': 'done' if ss.cases else 'todo', "4 f'c study": 'done' if ss.case else 'todo',
              '5 Fix board': ('warn' if (ss.case and nrev and not ss.rounds) else ('done' if ss.rounds else 'todo')),
              '6 Final check': 'done' if ss.final else ('warn' if ss.rounds else 'todo'),
              '7 Results': 'done' if ss.final else 'todo',
              '8 Documents': 'done' if res0 and AIO.documents_ready(ss.out) else 'todo'}
    hit = ui.nav(STEPS, ss.page, states, counts={'5 Fix board': nrev if (ss.case and nrev and not ss.rounds) else None})
    if hit and hit != ss.page:
        ss._goto = hit; st.rerun()
    st.markdown('<div class="sfoot">UI in English · every control has (?) help<br>Outputs are drafts for engineer review.</div>',
                unsafe_allow_html=True)
page = ss.page
if ss.get('_last_page') != page:
    ss._last_page = page
    ss.visit += 1
if ss.msg:
    st.toast(ss.msg); ss.msg = None


# ================================================================================================ 1 Files
def _store(slot, new):
    ss.files[slot] = new
    if slot == 'workbook':
        tpl = INPW.read_template(blob_path(*new[0]))
        base = AIO.empty_tpl(); base.update(tpl)
        ss.tpl = base
        new_inputs(); ss.msg = f'Inputs loaded from {new[0][0]}'
    else:
        reset_run()


def _uploader(slot, multi, label, key):
    up = st.file_uploader(label, type=['xlsx', 'xlsm'], accept_multiple_files=multi, key=key, help=h('f_' + slot),
                          label_visibility='collapsed')
    got = (up if multi else ([up] if up else [])) or []
    if got:
        new = [(f.name, f.getvalue()) for f in got]
        if [n for n, _ in new] != [n for n, _ in ss.files.get(slot, [])] or \
                [len(d) for _, d in new] != [len(d) for _, d in ss.files.get(slot, [])]:
            _store(slot, new)
            st.rerun()


FILE_SPEC = [('seismic', '1.1', 'Seismic model', 'required', True,
              'ETABS export: column forces (seismic combinations), story data, point connectivity.'),
             ('full_unreduced', '1.2', 'Full model – unreduced stiffness', 'required', True,
              'ETABS export of the full gravity model, gross (unreduced) section stiffness.'),
             ('full_reduced', '1.3', 'Full model – reduced stiffness', 'optional', True,
              'Optional. When given it becomes the primary model for gravity + slenderness.'),
             ('combos', '1.4', 'Load combinations', 'optional', True,
              'Optional. ETABS table “Load Combination Definitions”.'),
             ('lap', '1.5', 'Development length table (lap)', 'required', False,
              'CEDA TABLE 11.04 – Development of Reinforcement.'),
             ('workbook', '1.6', 'CEDA input workbook', 'optional', False,
              'Optional. Inputs of an earlier run or the template filled in Excel.')]


def page_files():
    ui.head(1, 'Files', 'Upload the ETABS exports and CEDA tables. The app reads them and shows what it found before anything is '
            'designed. ETABS: <i>Display → Show Tables (Ctrl+T) → Export to Excel</i>; a sheet pasted without its <code>TABLE:</code> '
            'row is read by its sheet name.', help=h('step_files'))
    cols = st.columns(2, gap='medium')
    for i, (slot, num, title, tag, multi, desc) in enumerate(FILE_SPEC):
        with cols[i % 2].container(border=True, key=f'card_{slot}'):
            tag_ = 'optional' if (slot == 'full_unreduced' and ss.files.get('full_reduced')) else tag
            if slot == 'lap' and ss.tpl.get('lap_rows') and not ss.files.get('lap'):
                tag_ = 'optional'                     # Lap sheet already filled (workbook / earlier upload)
            ui.card_head(num, title, tag_, help=h('f_' + slot), desc=desc)
            have = ss.files.get(slot) or []
            if not have:
                _uploader(slot, multi, title, f'up_{slot}_{ss.visit}')
            else:
                for n, d in have:
                    a, b, c = st.columns([5, 1.6, 1.6], vertical_alignment='center')
                    with a:
                        ui.file_row(n, len(d))
                    with b.popover('Replace', width='stretch', help='Choose another file for this slot'):
                        _uploader(slot, multi, title, f'rp_{slot}_{ss.visit}')
                    if c.button('Remove', key=f'rm_{slot}_{n}', width='stretch', help='Remove this file'):
                        ss.files[slot] = [x for x in ss.files[slot] if x[0] != n]
                        reset_run(); st.rerun()
            if slot == 'combos' and have:
                T = read_blobs(md5('c', *[n for n, _ in have]), tuple(have))[0]
                names, cur = [], None
                for r in T.get('Load Combination Definitions') or []:
                    nm = AIO.E.col(r, 'Name', 'Combo') or cur; cur = nm
                    if nm and nm not in names:
                        names.append(nm)
                if names:
                    st.markdown(f'{len(names)} combos read. Combinations in this file **replace** the combinations of the model files '
                                '**by name**.', help=h('f_combos'))
                else:
                    st.error('No "Load Combination Definitions" table in this file.')
            if slot == 'lap' and have:
                n, d = have[0]
                shs = INPW.lap_sheets(blob_path(n, d))
                cur = ss.lap_sheet if ss.lap_sheet in shs else next((s_ for s_ in shs if s_.startswith('40')), shs[0])
                a, b = st.columns([1, 1.2])
                ss.lap_sheet = a.selectbox('Sheet (bar spacing case)', shs, index=shs.index(cur), help=h('f_lapsheet'))
                try:
                    rows, note = INPW.read_lap_table(blob_path(n, d), ss.lap_sheet)
                    with b:
                        st.markdown("f'c rows found", help=note)
                        ui.chips([str(int(r[0])) for r in rows if r and r[0] is not None])
                    if not ss.tpl.get('lap_rows'):
                        ss.tpl['lap_rows'] = rows; ss.visit += 1
                except Exception as e_:
                    st.error(f'Not a CEDA development-length table: {e_}')
            if slot == 'workbook' and have:
                st.caption('The inputs on screen were replaced with this workbook (step 2 shows them; missing v1.5 keys use the defaults).')
    m, _ = models()
    ready = bool(m['seismic'] and (m['full_unreduced'] or m['full_reduced']))
    if ready:
        with st.container(border=True, key='card_routing'):
            st.markdown('### Model routing', help=h('route'))
            nm = lambda s_: ', '.join(n for n, _ in ss.files.get(s_) or []) or '—'
            ok, gray, warn = ui.badge('given', 'ok'), ui.badge('not given', 'gray'), ui.badge('ASSUMPTION', 'warn')
            red = bool(m['full_reduced'])
            rows = [['Seismic', ui.esc(nm('seismic')), 'Seismic combinations (with E)', ok],
                    ['Full – unreduced', ui.esc(nm('full_unreduced')),
                     'Gravity combinations' + ('' if red else ', slenderness (primary)') if m['full_unreduced'] else '—',
                     (ok if red else warn + ' no reduced model: unreduced used as primary') if m['full_unreduced'] else gray],
                    ['Full – reduced', ui.esc(nm('full_reduced')), 'Gravity + slenderness (primary)' if red else '—', ok if red else gray],
                    ['Combinations', ui.esc(nm('combos')), 'Replace model combinations by name' if ss.files.get('combos') else '—',
                     ok if ss.files.get('combos') else gray]]
            ui.table(['Model', 'File', 'Used for', 'Note'], rows, mono=(1,))
        p = prep_now()
        lap = f" · lap table {ss.lap_sheet} with {len(ss.tpl.get('lap_rows') or [])} f'c rows" if ss.tpl.get('lap_rows') else \
            ' · no lap table yet (1.5 or sheet Lap)'
        if p:
            st.success(f"**Files ready.** {len(p['stories'])} stories · {len(p['labels'])} column labels{lap}. Continue to the inputs.")
            dc = AIO.PI.data_check(p)
            nc = sum(1 for it in dc if it['level'] == 'confirm')
            if nc:
                st.warning(f"**Data check: {nc} item(s) to confirm on step 3** – " + '; '.join(it['title'] for it in dc if it['level'] == 'confirm'))
    else:
        st.info('Upload the seismic model and at least one full model to continue.')
    st.download_button('⬇ Blank input workbook', open(os.path.join(os.path.dirname(__file__), 'templates',
                       'CEDA_Column_Input_TEMPLATE.xlsx'), 'rb').read(), 'CEDA_Column_Input_TEMPLATE.xlsx',
                       help='Empty CEDA input workbook with every sheet and the criteria keys.')
    if ui.foot('Nothing is designed on this step.', 'Next: 2 Inputs →', disabled=not ready):
        ss._goto = '2 Inputs'; st.rerun()


# ================================================================================================ 2 Inputs
def page_inputs():
    ui.head(2, 'Inputs', 'Six groups, one per sheet of the input workbook. Change them here or in Excel, then save them back to Excel.', help=h('step_inputs'))
    p = prep_now()
    if p is None:
        st.info('Upload the files first (step 1).'); return
    found = p['found']
    STO, LABS = list(found['stories']), list(found['labels'])
    tpl = ss.tpl
    t = st.tabs(['Project & seismic', "Materials & f'c", 'Stories, Lu & sections', 'Loads & lap', 'Marks, ranges & prices',
                 'Designer decisions'])
    with t[0]:
        a, b = st.columns(2)
        for i, (k, lab) in enumerate((('project.name', 'Project'), ('project.location', 'Location'), ('project.building', 'Building'),
                                      ('project.job', 'Job no. (file prefix)'), ('project.date', 'Date'),
                                      ('project.calc_by_1', 'Calculated by'), ('project.calc_by_2', 'Checked by'),
                                      ('project.approve_by', 'Approved by'))):
            W(a if i % 2 == 0 else b, k, lab)
        st.subheader('Seismic', help='มยผ. 1301/1302-61 – asked before every column design.')
        a, b, c = st.columns(3)
        W(a, 'seismic.design', 'Seismic design required', 'yn')
        cat = W(b, 'seismic.category', 'Seismic design category', 'sel', ['ก', 'ข', 'ค', 'ง'])
        fr = W(c, 'seismic.frame', 'Columns are', 'sel', ['gravity', 'IMF', 'SMF'])
        W(a, 'seismic.zone', 'Zone'); W(b, 'seismic.importance', 'Importance factor'); W(c, 'seismic.system', 'Lateral system')
        W(a, 'seismic.R', 'R', 'num'); W(b, 'seismic.Omega0', 'Ω0', 'num'); W(c, 'seismic.Cd', 'Cd', 'num')
        if cat == 'ง':
            st.warning('Category ง with ordinary walls: height ≤ 60 m and seismic force +40 % – check.')
        if fr == 'SMF':
            st.warning('SMF detailing (ACI 18.7) is not automated – design forces only.')
            st.error('SMF: ρ max and ρ max with approval are locked at 6 % and cannot be changed (ACI 318-19 §18.7.4.1); '
                     '“Approve ρ” is disabled on the fix board.')
    with t[1]:
        a, b, c, d = st.columns(4)
        W(a, 'materials.fc_typical', "Typical f'c (ksc)", 'sel', FCS)
        W(b, 'materials.fy', 'fy (ksc)', 'num'); W(c, 'materials.fyt', 'fyt ties (ksc)', 'num')
        W(d, 'materials.fc_slab', "Slab f'c (ksc)", 'num')
        W(a, 'materials.fc_mode', "Column f'c", 'sel', ['auto', 'fixed'])
        W(b, 'materials.fc_bottom', "Bottom f'c (fixed)", 'sel', FCS)
        W(c, 'materials.fc_reduce_at', "Typical f'c from story (fixed)", 'sel', [''] + STO)
        W(d, 'detailing.cover_mm', 'Cover to ties (mm)', 'num')
        W(a, 'detailing.tie_db', 'Tie size (mm)', 'sel', [12, 16])
        smf = str(ss.tpl['criteria'].get('seismic.frame') or '').upper() == 'SMF' or 'SPECIAL MOMENT' in str(ss.tpl['criteria'].get('seismic.system') or '').upper()
        if smf:
            ss.tpl['criteria']['detailing.rho_max_pct'] = 6.0; ss.tpl['criteria']['detailing.rho_ask_pct'] = 6.0
            for k_ in ('cw_detailing.rho_max_pct', 'cw_detailing.rho_ask_pct'):
                ss[k_] = 6.0
        W(b, 'detailing.rho_max_pct', 'ρ max without approval (%)', 'num')
        rk = W(b, 'detailing.rho_ask_pct', 'ρ max with approval (%)', 'num')
        if rk and (rk > 8 or rk < 6):
            st.error('ρ max with approval must be 6–8 % (ACI 318-19 §10.6.1.1) – the engine clamps it.')
        W(c, 'slender.k', 'Default k', 'num'); W(d, 'slender.beta_d', 'βd (blank = from load cases)', 'optnum')
        W(a, 'slender.sway', 'Sway check', 'sel', ['', 'non-sway'])
        W(b, 'gravity.DL', 'DL case names'); W(c, 'gravity.SDL', 'SDL case names'); W(d, 'gravity.LL', 'LL case names')
        if str(ss.tpl['criteria'].get('seismic.frame') or '').upper() == 'SMF':
            st.error('SMF: ρ limits locked at 6 % (ACI 318-19 §18.7.4.1) – the values above are not used.')
        W(c, 'detailing.splice', 'Splice method – project default', 'sel', ['Lap – staggered', 'Lap – one level', 'Mechanical coupler'])
        st.subheader("f'c study rule", help=h('step_fc'))
        a, b, c, d, e, f_ = st.columns(6)
        W(a, 'fc.limits_pct', 'Failing limits per story (%)'); W(b, 'fc.max', "Maximum f'c (ksc)", 'sel', [f_x for f_x in FCS if f_x >= 450])
        W(c, 'fc.share_low_pct', 'Reduction story share at ρ ≤ 1.5 % (%)', 'num'); W(d, 'fc.dc_min', 'Low D/C threshold', 'num')
        W(e, 'fc.dc_low', 'Low D/C band', 'num'); W(f_, 'fc.exempt_rho_pct', 'Not checked: typical f\'c with ρ ≤ (%)', 'num')
        st.subheader('Section enlargement (fix board)', help=h('fix_props'))
        a, b, c, d = st.columns(4)
        W(a, 'fix.target_dc', 'Target D/C for enlarged sections', 'num'); W(b, 'fix.step_mm', 'Step (mm)', 'num')
        W(c, 'fix.max_add_mm', 'Max increase per side (mm)', 'num'); W(d, 'fix.compare_ddc', 'Round compare: show |ΔD/C| >', 'num')
        st.caption('Bar rules (fixed, skill §5): c/c 125–150 mm for singles and 2-bar bundles, ≤ 160 mm for 3–4-bar bundles (couplers); '
                   'bundles from the tie corners, each size over the whole section first; inner bars last; ρ ≤ 6 %.')
    with t[2]:
        st.subheader('Stories', help=h('t_stories'))
        st0 = tpl['stories'] or [[s_, *found['z'].get(s_, (None, None)), None, None, None, None] for s_ in STO]
        tpl['stories'] = E('stories', INPW.HDR['Stories'], st0,
                           column_config={'basement': st.column_config.SelectboxColumn(options=['', 'Y', 'N'], help='Y = below the seismic model'),
                                          'Lu_m': st.column_config.NumberColumn(help='Clear height override for the whole story, m'),
                                          'k': st.column_config.NumberColumn(help='Effective length factor override'),
                                          'fc_ksc': st.column_config.NumberColumn(help="Fixed f'c of the story (fixed mode)")})
        st.subheader('Columns – Lu / k per column-story', help=h('t_columns'))
        tpl['columns'] = E('columns', INPW.HDR['Columns'], tpl['columns'],
                           column_config={'label': st.column_config.SelectboxColumn(options=LABS, help='ETABS column label'),
                                          'story': st.column_config.SelectboxColumn(options=STO, help='ETABS story'),
                                          'Lu_m': st.column_config.NumberColumn(help='Unsupported length, m'),
                                          'k': st.column_config.NumberColumn(help='Effective length factor')})
        st.subheader('Sections set by the designer', help=h('t_sections'))
        have = found['sec_of']
        with st.expander(f'Sizes read from ETABS ({len(have)} labels)'):
            st.dataframe(pd.DataFrame([dict(label=l, sizes=', '.join(f'{sh} {b_}×{h_}' + (' (from name)' if a_ else '') for sh, b_, h_, a_ in sorted(s_)))
                                       for l, s_ in sorted(have.items(), key=lambda kv: (len(kv[0]), kv[0]))]), hide_index=True, width='stretch')
        se0 = tpl['sections'] or [[l, None, None, 'rect', None, None] for l in LABS if l not in have]
        tpl['sections'] = [r for r in E('sections', INPW.HDR['Sections'], se0, column_config={
            'label': st.column_config.SelectboxColumn(options=LABS, help='ETABS column label'),
            'story_from': st.column_config.SelectboxColumn(options=[''] + STO, help='First story (blank = all)'),
            'story_to': st.column_config.SelectboxColumn(options=[''] + STO, help='Last story (blank = all)'),
            'shape': st.column_config.SelectboxColumn(options=['rect', 'circ'], help='circ: b = diameter'),
            'b_mm': st.column_config.NumberColumn(help='t2, bends about My, mm'), 'h_mm': st.column_config.NumberColumn(help='t3, bends about Mx, mm')})
            if r[0] and r[4] is not None]
    with t[3]:
        st.subheader('Load combinations', help=h('t_combos'))
        cases0 = tpl['combo_cases'] or list(found['cases']) or ['DL', 'SDL', 'LL', 'EQX', 'EQY']
        ctxt = st.text_input('Load case columns', ', '.join(map(str, cases0)), key=f'cases_{ss.visit}', help=h('cases'))
        cases = [c_.strip() for c_ in ctxt.split(',') if c_.strip()]
        if p['undefined']:
            st.error('No definition for: ' + ', '.join(p['undefined']) + ' – enter factors below, add them to the combination file, or exclude them.')
        cb0 = ([[r[0]] + [dict(zip(tpl['combo_cases'] or cases0, r[1:])).get(c_) for c_ in cases] for r in tpl['combos_rows']]
               if tpl['combos_rows'] else [[c_] + [None] * len(cases) for c_ in p['undefined']])
        rows = E('combos_' + md5(ctxt), ['combo'] + cases, cb0)
        tpl['combos_rows'] = [r for r in rows if r[0] and any(v not in (None, '') for v in r[1:])]
        tpl['combo_cases'] = cases
        tpl['exclude'] = st.multiselect('Exclude combos', found['combos'], default=[c_ for c_ in tpl['exclude'] if c_ in found['combos']],
                                        key=f'excl_{ss.visit}', help=h('exclude'))
        st.subheader('Lap table', help=h('t_lap'))
        lap0 = tpl['lap_rows'] or [[f] + [INPW.LAP_KNOWN.get(f, {}).get(d_) for d_ in (12, 16, 20, 25, 28, 32)] for f in (400, 560)]
        tpl['lap_rows'] = E('lap', INPW.HDR['Lap'], lap0)
    with t[4]:
        st.subheader('Marks', help='CEDA criterion A (20 Oct 2026).')
        a, b, c = st.columns(3)
        W(a, 'marks.envelope', 'Mark envelope (criterion A)', 'yn')
        W(b, 'marks.max_weight_pct', 'Extra steel per label (%)', 'num'); W(c, 'marks.project_max_weight_pct', 'Extra steel project (%)', 'num')
        W(a, 'marks.max_rows', 'Max rows that differ (blank = none)', 'optnum'); W(b, 'marks.max_step', 'Max steps per row (blank = none)', 'optnum')
        W(c, 'story_ranges.mode', 'Story ranges (no table)', 'sel', ['auto', 'each'])
        W(a, 'marks.renumber', 'Renumber marks at FINAL', 'yn')
        st.subheader('Story ranges fixed by the designer', help=h('t_ranges'))
        rg0 = ss.pop('rg_prefill', None) or tpl.get('ranges') or []
        if st.button('Prefill with the ranges of the last run', disabled=not ss.out,
                     help='Copies the story ranges of the last run into the table so you can merge or split them.'):
            ss.tpl['ranges'] = json.load(open(os.path.join(ss.out, 'results.json')))['bands']
            ss.visit += 1; st.rerun()
        tpl['ranges'] = [r for r in E('ranges', INPW.HDR['Story_ranges'], rg0, column_config={
            c_: st.column_config.SelectboxColumn(options=STO, help='bottom → top') for c_ in INPW.HDR['Story_ranges']}) if r[0] and r[1]]
        st.subheader("Unit prices – information only", help=h('fc_cost'))
        tpl['prices_rows'] = E('prices', INPW.HDR['Prices'], tpl.get('prices_rows') or INPW.PRICE_ROWS, column_config={
            'item': st.column_config.SelectboxColumn(options=['concrete', 'steel'], help='concrete or longitudinal steel'),
            'size': st.column_config.TextColumn(help="f'c in ksc for concrete, DB12 … DB32 for steel"),
            'unit': st.column_config.TextColumn(help='THB/m3 or THB/kg'),
            'price_thb': st.column_config.NumberColumn(help='Material price, THB per unit (no formwork / labour)')})
    with t[5]:
        st.subheader('Approve_rho (pre-selected on the fix board)', help=h('fix_wb'))
        cc = {'label': st.column_config.SelectboxColumn(options=LABS), 'story': st.column_config.SelectboxColumn(options=STO)}
        tpl['approve'] = E('approve', INPW.HDR['Approve_rho'], tpl['approve'], column_config=cc)
        st.subheader('δ above 1.4 accepted', help=h('t_delta'))
        tpl['delta_ok'] = E('delta', INPW.HDR['Accept_delta'], tpl['delta_ok'], column_config=cc)
        st.subheader('Proposed overload acceptances', help=h('t_overload'))
        tpl['overload'] = E('overload', INPW.HDR['Accept_overload'], tpl['overload'], column_config=cc)
        st.subheader('Enlarged sections (written by the fix board)', help=h('fix_range'))
        tpl['enlarge'] = E('enlarge', INPW.HDR['Enlarge'], tpl.get('enlarge', []), column_config={
            'label': st.column_config.SelectboxColumn(options=LABS), 'story_from': st.column_config.SelectboxColumn(options=STO),
            'story_to': st.column_config.SelectboxColumn(options=STO), 'shape': st.column_config.SelectboxColumn(options=['rect', 'circ']),
            'option': st.column_config.SelectboxColumn(options=[1, 2], help=h('fix_range'))})
        st.subheader('Splice per column', help=h('fix_splice'))
        tpl['splice'] = E('splice', INPW.HDR['Splice'], tpl.get('splice', []), column_config={
            'label': st.column_config.SelectboxColumn(options=LABS), 'story_from': st.column_config.SelectboxColumn(options=[''] + STO),
            'story_to': st.column_config.SelectboxColumn(options=[''] + STO),
            'method': st.column_config.SelectboxColumn(options=['Lap – staggered', 'Lap – one level', 'Mechanical coupler'])})
    st.divider()
    st.download_button('⬇ Save inputs to Excel', INPW.make_template(found, tpl), f"{tpl['criteria'].get('project.job') or 'JOB'}_Column_Input.xlsx",
                       help=h('save_inputs'))


# ================================================================================================ 3 Check & run
def data_check_card(p):
    """v1.5.1: what in the uploads may not be what the designer meant (steel in the column table, sizes from names, braces …).
    'confirm' items must be ticked before the run; returns True when every one is ticked and nothing stops the run."""
    items = AIO.PI.data_check(p)
    with st.container(border=True, key='card_datacheck'):
        n_c = sum(1 for it in items if it['level'] == 'confirm')
        st.markdown('### Data check', help='Things in the ETABS uploads that may not be what you meant. Items marked CONFIRM must be '
                    'ticked before the run; INFO items are for reading. Every confirmation is written to the decisions log.')
        if not items:
            st.success('Nothing unusual in the uploads.'); return True
        st.caption(f'{n_c} item(s) to confirm · {len(items) - n_c} for information')
        ok = True
        for it in items:
            kind = {'stop': 'fail', 'confirm': 'warn', 'info': 'info'}[it['level']]
            st.markdown(ui.badge(it['level'].upper(), kind) + f" **{ui.esc(it['title'])}**", unsafe_allow_html=True)
            st.caption(it['detail'])
            if it['rows']:
                with st.expander(f"{len(it['rows'])} line(s)", expanded=it['level'] != 'info' and len(it['rows']) <= 6):
                    for r in it['rows']:
                        st.markdown(f"<span class='mono small'>{ui.esc(r)}</span>", unsafe_allow_html=True)
            if it['level'] == 'stop':
                ok = False
            elif it['level'] == 'confirm':
                if not st.checkbox('I checked this – it is right', key=f"dc_{it['key']}_{ss.visit}", help='Written to the decisions log'):
                    ok = False
    return ok


def page_check():
    ui.head(3, 'Check & run', "The app lists what it will use. Confirm, then run the design and the f'c study together.", help=h('step_check'))
    p = prep_now()
    if p is None:
        st.info('Upload the files first (step 1).'); return
    with st.container(border=True, key='card_page_check_1'):
        st.subheader('Models used', help=h('route'))
        for n in p['route']:
            (st.warning if 'ASSUMPTION' in n else st.caption)(n)
    with st.container(border=True, key='card_page_check_2'):
        st.subheader('Input check', help=h('check'))
        rows = AIO.input_check(p)
        miss = ss.tpl.get('missing_keys') or []
        if any(ss.files.get('workbook') or []) and miss:
            rows.append(dict(input='workbook version', ok=True, info='v1.5.0 keys missing – defaults used and shown on step 2: ' + ', '.join(miss[:8])
                             + (' …' if len(miss) > 8 else '') + '. “Save inputs to Excel” writes a v1.5.0 workbook.'))
        if ss.tpl.get('approve'):
            rows.append(dict(input='Approve_rho in workbook', ok=True, info=f"{len(ss.tpl['approve'])} label-stories – NOT used in the f'c study; "
                             'pre-selected on the fix board, applied only with Apply'))
        if ss.tpl.get('overload'):
            rows.append(dict(input='Overload rows in workbook', ok=True, info=f"{len(ss.tpl['overload'])} rows – NOT applied: overload is ticked "
                             'per row on the fix board, every session'))
        if ss.tpl.get('delta_ok'):
            rows.append(dict(input='Accepted δ in workbook', ok=True, info=f"{len(ss.tpl['delta_ok'])} rows – shown on the fix board"))
        chk = pd.DataFrame(rows)
        st.dataframe(chk.assign(ok=chk['ok'].map({True: '✔', False: '✖'})), hide_index=True, width='stretch',
                     column_config={'input': st.column_config.TextColumn(help='What is checked'),
                                    'ok': st.column_config.TextColumn(help='✖ = fix in step 2 or in the workbook'),
                                    'info': st.column_config.TextColumn(help='Details / what is missing')})
        if p['undefined']:
            st.error('Combos without definition: ' + ', '.join(p['undefined']) + ' – step 2 › Loads & lap: enter factors or exclude them.')
        with st.expander(f"Merge report ({len(p['merge_rep'])})"):
            for r in p['merge_rep']:
                st.caption(r)
        a, b, c = st.columns(3)
        a.metric('Labels', len(p['labels']), help='Column labels with forces in the uploads')
        b.metric('Stories', len(p['stories']), help='Story order used (bottom → top)')
        c.metric('Label-stories', len(p['label_story']), help='Column segments: one label in one story')
        ok = chk['ok'].all()
        dc_ok = data_check_card(p)
        conf = st.checkbox('I confirm the inputs and the assumptions above', help=h('confirm'), key=f'confirm_{ss.visit}')
        if not dc_ok:
            st.caption('Tick every “confirm” item of the data check above first.')
        if st.button("▶ Run design + f'c study (≈ 2 min on BKMPH02)", type='primary', disabled=not (ok and conf and dc_ok), help=h('run')):
            log('Inputs confirmed', '', '', 'check & run', 'Designer')
            for it in AIO.PI.data_check(p):
                if it['level'] == 'confirm':
                    log('Data check confirmed', '', '', it['title'], 'Designer (step 3)')
            do_run("Design + f'c study done – choose the case on step 4.", approved=[], study=True)
            st.rerun()
        if ss.cases:
            st.success("Case table ready – continue with step 4.")


# ================================================================================================ 4 f'c study
def prices_now():
    return INPW.prices_dict(ss.tpl.get('prices_rows'))


def case_label(c):
    if c['type'] == 'T':
        return f"{c['fc_bottom']:.0f} everywhere (T – typical f'c)"
    return f"{c['fc_bottom']:.0f} / {c['reduce_at']} ({c['type']})"


def page_fc():
    ui.head(4, "f'c study", "One f'c for the whole project, by story. Each candidate f'c gives two cases: <b>A</b> the lowest reduction story with failing within the limit, <b>B</b> the lowest reduction story with no failing column above it. Pick one case; the failing columns go to the fix board.", help=h('step_fc'))
    if not ss.cases:
        st.info('Run the design first (step 3).'); return
    S = ss.cases
    for c in S['cases']:
        c['cost_thb'], c['cost_missing'] = AIO.FS.cost(c, prices_now())
    rule = S['rule']
    a, b, c_, d = st.columns(4)
    a.metric("Typical f'c", f"{S['fc_typical']:.0f}", help='Upper-story f\'c and the start of the study')
    fcs = sorted({x['fc_bottom'] for x in S['cases']})
    b.metric('Candidates', f"{fcs[0]:.0f}–{fcs[-1]:.0f}" if fcs else '–', help=h('fc.max'))
    res = res_of()
    c_.metric('Label-stories', sum(len(r['per']) for r in res['results']) if res else '–', help='Column segments in the study')
    last = S['cases'][-1] if S['cases'] else None
    d.metric('Study stopped at', (f"{last['fc_bottom']:.0f} · B = {last['n_fail']}" if last else '–'),
             help="Stops when case B has 0 failing or f'c reaches the maximum.")
    if S.get('never'):
        st.warning(f"{len(S['never'])} label-stories fail at the highest f'c even with the approval limit: " + ', '.join(S['never'][:15]))
    recs = {int(k): v for k, v in S['rec'].items()}
    tag = {}
    for L, i in recs.items():
        tag.setdefault(i, []).append(f'{L}')
    rows = []
    for c in S['cases']:
        rows.append({"f'c low": int(c['fc_bottom']), 'case': c['type'] + (f"  ★ limit {'·'.join(tag[c['id']])} %" if c['id'] in tag else ''),
                     'reduce to typical at': c['reduce_at'], 'failing': c['n_fail'], 'ρ 6–8 %': c['n_rho'], 'enlarge': c['n_enlarge'],
                     'never': c['n_never'], 'failing above reduction': c['above'], 'max share %': round(c['max_fail_share'] * 100, 1),
                     "f'c-overstrength n": c['fcov_n'], "% of high-f'c concrete at overstrength": round(c['fcov_pct']),
                     'D/C < 0.50 %': round(c['low50_pct']), 'D/C 0.50–0.75 %': round(c['low75_pct']),
                     "concrete high f'c m³": c['hi_m3'], "concrete typical f'c m³": c['typ_m3'], 'main bars t': c['steel_t'],
                     'cost M THB': round(c['cost_thb'] / 1e6, 2) if c['cost_thb'] else None})
    ids = [c['id'] for c in S['cases']]
    cur = ss.case['id'] if ss.case else S['recommended']
    if ss.get('fc_sel') not in ids:
        ss.fc_sel = cur if cur in ids else ids[0]
    with st.container(border=True, key='card_cases'):
        x, y = st.columns([3, 2], vertical_alignment='center')
        x.markdown('### Cases', help=h('step_fc'))
        lim = y.segmented_control('Show limit', [10, 15, 20, 25], selection_mode='multi', default=[10, 15, 20, 25],
                                  format_func=lambda v: f'{v} %', help='Mark the recommended case of these failing limits (★)',
                                  key='fc_lims')
        q = lambda k: f' <span class="qq" title="{ui.esc(h(k))}">?</span>'
        hdr = ('<tr><th rowspan="2" class="n">f\'c low<br>(ksc)</th><th rowspan="2">Case</th><th rowspan="2" class="n">Reduce to<br>'
               f'{S["fc_typical"]:.0f} at</th><th colspan="4" class="grp">Failing label-stories{q("fc_fail")}</th>'
               f'<th rowspan="2" class="n">Failing above<br>reduction{q("fc_above")}</th><th rowspan="2" class="n">Max share<br>per story %'
               f'{q("fc_share")}</th><th colspan="2" class="grp">f\'c-overstrength{q("fc_fcov")}</th>'
               f'<th colspan="2" class="grp">Low D/C, % of checked{q("fc_low")}</th><th colspan="2" class="grp">Concrete m³{q("fc_conc")}</th>'
               f'<th rowspan="2" class="n">Main<br>bars t{q("fc_steel")}</th><th rowspan="2" class="n">Cost<br>M THB{q("fc_cost")}</th></tr>'
               '<tr><th class="n">Total</th><th class="n">ρ 6–8 %</th><th class="n">Enlarge</th><th class="n">Never</th><th class="n">Count</th>'
               '<th class="n">% of high-f\'c concrete<br>at overstrength</th><th class="n">&lt; 0.50</th><th class="n">0.50–0.75</th>'
               '<th class="n">High f\'c</th><th class="n">Typical f\'c</th></tr>')
        body, prev = '', None
        for c in S['cases']:
            stars = [L for L in sorted(tag.get(c['id'], []), key=int) if int(L) in (lim or [])]
            typ = {'A': 'A · within limit', 'B': 'B · none above', 'A=B': 'A = B', 'T': "T · typical f'c everywhere"}.get(c['type'], c['type'])
            fc_cell = f'<td class="n fc">{c["fc_bottom"]:.0f}</td>' if c['fc_bottom'] != prev else '<td class="n fc"></td>'
            prev = c['fc_bottom']
            body += (f'<tr class="{"sel" if c["id"] == ss.fc_sel else ""}">{fc_cell}<td>{typ}'
                     + (f' {ui.badge("★ limit " + " · ".join(stars) + " %", "info")}' if stars else '') + '</td>'
                     f'<td class="n">{c["reduce_at"] or "–"}</td><td class="n"><b>{c["n_fail"]}</b></td><td class="n">{c["n_rho"]}</td>'
                     f'<td class="n">{c["n_enlarge"]}</td><td class="n">{c["n_never"]}</td><td class="n">{c["above"]}</td>'
                     f'<td class="n">{c["max_fail_share"] * 100:.1f}</td><td class="n">{c["fcov_n"]}</td><td class="n">{c["fcov_pct"]:.0f} %</td>'
                     f'<td class="n">{c["low50_pct"]:.0f} %</td><td class="n">{c["low75_pct"]:.0f} %</td><td class="n">{c["hi_m3"]:,.1f}</td>'
                     f'<td class="n">{c["typ_m3"]:,.1f}</td><td class="n">{c["steel_t"]:,.1f}</td>'
                     f'<td class="n">{(c["cost_thb"] / 1e6) if c["cost_thb"] else 0:,.2f}</td></tr>')
        st.markdown(f'<div class="scroll"><table class="t cases"><thead>{hdr}</thead><tbody>{body}</tbody></table></div>',
                    unsafe_allow_html=True)
        st.info(f"**{ss.tpl['criteria'].get('project.job') or 'Project'}, v{AIO.ENGINE_VERSION} rules:** ρ ≤ {rule['rho_max'] * 100:.0f} % "
                f"for every column (workbook approvals not used), ρ 6–8 % split at the {rule['rho_ask'] * 100:.0f} % approval limit, count rule "
                f"max(limit × columns, 1), reduction story ≥ {rule['share_low'] * 100:.0f} % of columns at ρ ≤ 1.5 % at {S['fc_typical']:.0f} ksc. "
                'Cost is information only.')
    with st.container(border=True, key='card_selected'):
        x, y = st.columns([3, 2], vertical_alignment='bottom')
        sel = y.selectbox('Case', ids, index=ids.index(ss.fc_sel), format_func=lambda i: case_label(S['cases'][i]),
                          help='Pick the case for the project (the row is highlighted in the table).')
        if sel != ss.fc_sel:
            ss.fc_sel = sel; st.rerun()
        c = S['cases'][sel]
        x.markdown(f"### Selected: {c['fc_bottom']:.0f} ksc, reduce to {S['fc_typical']:.0f} at {c['reduce_at'] or '–'} (case {c['type']})",
                   help='The case used when you press “Use this case”.')
        sts = list(c['fc_of'].keys())
        st.markdown("f'c by story", help="Bottom → top. Dark = the high f'c, light = the typical f'c.")
        st.markdown('<div class="strip" style="grid-template-columns:repeat(%d,minmax(0,1fr))">' % len(sts)
                    + ''.join(f'<div class="{"s6" if c["fc_of"][s_] > S["fc_typical"] else "s4"}" title="{s_} · {c["fc_of"][s_]:.0f} ksc">'
                              f'{ui.esc(s_)}</div>' for s_ in sts) + '</div>', unsafe_allow_html=True)
        a, b, c3 = st.columns(3)
        with a.container(border=True):
            rho_ = [f for f in c['fails'] if f['kind'] == 'rho']; enl_ = [f for f in c['fails'] if f['kind'] != 'rho']
            st.markdown(f"**{c['n_fail']} failing → fix board**")
            st.caption((f"ρ 6–8 % ({len(rho_)}): " + ', '.join(f"{f['label']} {f['story']}" for f in rho_) + '. ' if rho_ else '')
                       + (f"Enlarge ({len(enl_)}): " + ', '.join(f"{f['label']} {f['story']}" for f in enl_) + '.' if enl_ else '') or '–')
        with b.container(border=True):
            st.markdown(f"**f'c-overstrength: {c['fcov_n']} · {c['fcov_pct']:.0f} % of {c['fc_bottom']:.0f} ksc concrete**")
            st.caption(f"{c['fcov_pct']:.0f} % of the high-f'c concrete is in columns where {S['fc_typical']:.0f} ksc would do. "
                       "The price of one f'c per story, for information.")
        with c3.container(border=True):
            st.markdown(f"**Low D/C: {c['low50_pct']:.0f} % < 0.50 · {c['low75_pct']:.0f} % 0.50–0.75**")
            st.caption(f"of {c['checked']} checked label-stories (typical f'c with ρ ≤ 1.5 % not checked)")
            with st.popover('Show list (label, story, f\'c, D/C, ρ)'):
                st.dataframe(pd.DataFrame(c['lows']), hide_index=True, width='stretch')
    x, y = st.columns([3, 2])
    nm = x.text_input('Engineer', value=ss.engineer, help=h('fix_engineer'), key=f'eng4_{ss.visit}')
    if y.button('Use this case → Fix board', type='primary', disabled=not nm.strip(), help=h('fc_use')):
        ss.engineer = nm.strip()
        cr = ss.tpl['criteria']
        cr['materials.fc_mode'] = 'fixed'; cr['materials.fc_bottom'] = c['fc_bottom']; cr['materials.fc_reduce_at'] = c['reduce_at']
        ss.tpl['stories'] = [list(r[:6]) + [None] for r in ss.tpl['stories']]
        for k in [k for k in ss.keys() if str(k).startswith('cw_materials.')]:
            del ss[k]
        log("f'c case chosen", '', '', f"{case_label(c)} – failing {c['n_fail']}, overstrength {c['fcov_n']} · {c['fcov_pct']:.0f} %",
            'Designer', f'screen ({ss.engineer})')
        ss.case = dict(id=c['id'], fc_bottom=c['fc_bottom'], reduce_at=c['reduce_at'], type=c['type'])
        ss.tpl['marks'], ss.tpl['enlarge'], ss.approved, ss.act, ss.rounds, ss.etabs_done = [], [], [], {}, [], []
        res = do_run(f"Case {case_label(c)} applied – mark names locked. Continue with the fix board.", approved=[], renumber=True)
        lock_marks(res)
        st.rerun()


# ================================================================================================ fix component (steps 5 and 6E)
ACT_ENL = ['Enlarge – proposal', 'Enlarge – type size', 'Accept overload', 'No action']
ACT_RHO = ['Approve ρ 6–8 %', 'Enlarge – proposal', 'Enlarge – type size', 'Accept overload', 'No action']
SPLICE = ['Project default', 'Mechanical coupler', 'Lap – staggered', 'Lap – one level']


def groups_now(out):
    if out not in ss.groups:
        with st.spinner('Checking the failing label-stories (approval limit) …'):
            ss.groups[out] = AIO.fix_groups(res_of(out), out, rho_ask())
    return ss.groups[out]


def gkey(g):
    return f"{g['label']}|{g['kind']}"


def default_act(g):
    if g['kind'] == 'rho' and not is_smf():
        return dict(action='Approve ρ 6–8 %', splice='Project default')
    return dict(action='Enlarge – proposal', option=2, choice=None)


def props(out, g, option):
    k = (out, g['label'], tuple(g['stories']), int(option))
    if k not in ss.props:
        fx = INPW.to_cfg(ss.tpl).get('fix', {})
        with st.spinner(f"Proposals for {g['label']} (option {option}) …"):
            ss.props[k] = AIO.FX.proposals(out, g['label'], g['stories'], int(option), fx.get('target_dc', 0.90), int(fx.get('step_mm', 50)),
                                           int(fx.get('max_add_mm', 500)))
    return ss.props[k]


def chosen_size(out, g, a):
    """(shape, b, h, result) of an enlarge action or None."""
    if a['action'] == 'Enlarge – type size':
        return a.get('typed')
    p = ss.props.get((out, g['label'], tuple(g['stories']), int(a.get('option', 2))))
    if not p or not p['options']:
        return None
    kinds = [o['kind'] for o in p['options']]
    kind = a.get('choice') if a.get('choice') in kinds else kinds[0]
    return next(o for o in p['options'] if o['kind'] == kind)


def superseded(out, groups, acts):
    """ρ rows inside the range of an enlargement of the same label – re-designed on the new size."""
    out_ = set()
    for g in groups:
        a = acts.get(gkey(g))
        if g['kind'] != 'enlarge' or not a or not a['action'].startswith('Enlarge'):
            continue
        rng = AIO.FX.ranges_for(out, g['label'], g['stories'], int(a.get('option', 2)))
        for g2 in groups:
            if g2['label'] == g['label'] and g2['kind'] == 'rho':
                for s_ in g2['stories']:
                    if s_ in rng:
                        out_.add((g2['label'], s_))
    return out_


def render_fix(out, ctx):
    res = res_of(out)
    groups, delta = groups_now(out)
    acts = ss.act.setdefault(ctx, {})
    for g in groups:
        acts.setdefault(gkey(g), default_act(g))
    dacts = ss.act.setdefault(ctx + '_d', {})
    wb_delta = {(a, b): c for a, b, c in ss.tpl.get('delta_ok', []) if a}
    for d in delta:
        dacts.setdefault(f"{d['label']}|{d['story']}", dict(action='Accept δ' if (d['label'], d['story']) in wb_delta else 'No action',
                                                           limit=float(wb_delta.get((d['label'], d['story']), 1.5) or 1.5), reason=''))
    n_rho = sum(len(g['stories']) for g in groups if g['kind'] == 'rho')
    n_enl = sum(len(g['stories']) for g in groups if g['kind'] == 'enlarge')
    m = st.columns(4)
    m[0].metric('Failing label-stories', n_rho + n_enl, help='D/C > 1 at ρ ≤ 6 %')
    m[1].metric('Fixable by ρ 6–8 %', n_rho, help=f'Pass with ρ up to the approval limit ({rho_ask() * 100:.1f} %).')
    m[2].metric('Need enlargement', n_enl, help='Fail even at the approval limit – enlarge or accept overload.')
    m[3].metric('δns > 1.4', len(delta), help=h('fix_delta'))
    if is_smf():
        st.error('SMF: “Approve ρ” is disabled – ρ is limited to 6 % (ACI 318-19 §18.7.4.1).')
    if not groups and not delta:
        st.success('Every label-story passes – nothing to fix.')
    sup = superseded(out, groups, acts)
    if groups:
        with st.container(border=True, key=f'card_fix1_{ctx}'):
            st.subheader('Failing columns', help=h('step_fix'))
            hd = st.columns([1.1, 1.1, 1.5, 1.2, 0.8, 0.8, 2.0, 1.1, 2.6, 0.8])
            for c_, t_, k_ in zip(hd, ['Label', 'Section', 'Failing', 'D/C', 'ρ %', 'ρ 8 % OK', 'Action', 'Range', 'Chosen', ''],
                                  ['', '', '', '', '', '', 'fix_action', 'fix_range', '', '']):
                c_.markdown(f'**{t_}**', help=h(k_) if k_ else None)
            for g in groups:
                k = gkey(g); a = acts[k]
                cs = st.columns([1.1, 1.1, 1.5, 1.2, 0.8, 0.8, 2.0, 1.1, 2.6, 0.8])
                cs[0].markdown(f"**{g['label']}**  \n{g['mark']}")
                cs[1].write(g['section'])
                cs[2].write(' · '.join(s_ + ('*' if s_ in g.get('carried', []) else '') for s_ in g['stories']))
                cs[3].write(' · '.join(f'{x:.3f}' for x in g['dc']))
                cs[4].write(f"{max(g['rho']):.2f}")
                cs[5].write('yes' if g['kind'] == 'rho' else 'no')
                opts = [o for o in (ACT_RHO if g['kind'] == 'rho' else ACT_ENL) if not (o.startswith('Approve') and is_smf())]
                a['action'] = cs[6].selectbox('Action', opts, index=opts.index(a['action']) if a['action'] in opts else 0,
                                              key=f'a_{ctx}_{k}_{ss.fix_ver}', label_visibility='collapsed', help=h('fix_action'))
                if a['action'].startswith('Enlarge'):
                    a['option'] = cs[7].selectbox('Range', [2, 1], index=[2, 1].index(a.get('option', 2)), key=f'o_{ctx}_{k}_{ss.fix_ver}',
                                                  format_func=lambda x: {1: '1 · row', 2: '2 · down'}[x], label_visibility='collapsed', help=h('fix_range'))
                else:
                    cs[7].write('—')
                with cs[8]:
                    if a['action'] == 'Approve ρ 6–8 %':
                        if any((g['label'], s_) in sup for s_ in g['stories']):
                            st.caption('superseded by the enlargement of this label (re-designed on the new size)')
                        else:
                            st.caption(' · '.join(f"{s_}: {x['bars']} ρ {x['rho_pct']:.2f} % D/C {x['dc']:.3f}" for s_, x in zip(g['stories'], g['ap'])))
                            a['splice'] = st.selectbox('Splice', SPLICE, index=SPLICE.index(a.get('splice', 'Project default')),
                                                       key=f'sp_{ctx}_{k}_{ss.fix_ver}', help=h('fix_splice'), label_visibility='collapsed')
                    elif a['action'] == 'Accept overload':
                        import math
                        dflt = math.ceil(max(g['dc']) * 100) / 100
                        a['dc_lim'] = st.number_input('D/C limit', 1.0, 2.0, float(a.get('dc_lim', dflt)), 0.01, key=f'dl_{ctx}_{k}_{ss.fix_ver}',
                                                      help=h('fix_overload'))
                        a['tick'] = st.checkbox(f"I accept the overload ({max(g['dc']):.3f} ≤ {a['dc_lim']:.2f})", value=False,
                                                key=f'tk_{ctx}_{k}_{ss.fix_ver}', help=h('fix_overload'))
                    elif a['action'] == 'Enlarge – proposal':
                        o = chosen_size(out, g, a)
                        if o:
                            sz = f"Ø{o['b']}" if o['shape'] == 'circ' else f"{o['b']} × {o['h']}"
                            st.caption(f"{o['kind']} {sz} · D/C {o['dc_max']:.3f} · +{o['concrete_add_m3']} m³")
                        else:
                            st.caption('open Detail → Find proposals')
                    elif a['action'] == 'Enlarge – type size':
                        o = a.get('typed')
                        st.caption((f"{o['b']} × {o['h']} · D/C {o['dc_max']} · {'OK' if o['ok'] else 'above target'}") if o else 'open Detail → type a size')
                    else:
                        st.caption('stays open – step 6')
                if cs[9].button('Detail', key=f'dt_{ctx}_{k}', help='Show the detail of this row below'):
                    ss[f'detail_{ctx}'] = k
            if any(g.get('carried') for g in groups):
                st.caption('* passes with ρ ≤ 6 % on its own – needs more steel only because the bars of the story above continue down '
                           '(CEDA: a story never carries less than the story above, same section and f\'c). Fixing the story above removes it.')
        with st.container(border=True, key=f'card_detail_{ctx}'):
            dk = ss.get(f'detail_{ctx}') or gkey(groups[0])
            g = next((x for x in groups if gkey(x) == dk), groups[0])
            render_detail(out, res, g, acts[gkey(g)], ctx)
    if delta:
        with st.container(border=True, key=f'card_fix2_{ctx}'):
            st.subheader('Slenderness δns > 1.4', help=h('fix_delta'))
            for d in delta:
                k = f"{d['label']}|{d['story']}"; a = dacts[k]
                cs = st.columns([1, 1, 1, 1, 2, 1, 3])
                cs[0].markdown(f"**{d['label']}**"); cs[1].write(d['story']); cs[2].write(f"δ {d['delta']:.2f}"); cs[3].write(f"D/C {d['dc']:.2f}")
                a['action'] = cs[4].selectbox('δ action', ['Accept δ', 'No action'], index=['Accept δ', 'No action'].index(a['action']),
                                              key=f'da_{ctx}_{k}_{ss.fix_ver}', label_visibility='collapsed', help=h('fix_delta'))
                a['limit'] = cs[5].number_input('limit', 1.4, 3.0, float(a['limit']), 0.05, key=f'dlim_{ctx}_{k}_{ss.fix_ver}',
                                                label_visibility='collapsed', help='Accept δ up to this value')
                a['reason'] = cs[6].text_input('Reason', a.get('reason', ''), key=f'dr_{ctx}_{k}_{ss.fix_ver}', placeholder='Reason (required)',
                                               label_visibility='collapsed', help='Required to accept δ; written in the decisions log')
    wb = [(a_, b_) for a_, b_ in ss.tpl.get('approve', []) if a_]
    if wb:
        with st.container(border=True, key=f'card_fix3_{ctx}'):
            st.subheader('Approve_rho from the workbook (pre-selected)', help=h('fix_wb'))
            fl = {(g['label'], s_): g for g in groups for s_ in g['stories']}
            rows = []
            for a_, b_ in wb:
                g = fl.get((a_, b_))
                if g is None:
                    stt = 'not needed – OK at ρ ≤ 6 %'
                elif (a_, b_) in sup:
                    stt = 'superseded by enlargement'
                elif g['kind'] == 'enlarge':
                    stt = 'not enough – ρ at the approval limit still fails, choose another action'
                else:
                    stt = 'used – pre-selected' if acts[gkey(g)]['action'].startswith('Approve') else 'not used (other action chosen)'
                rows.append(dict(label=a_, story=b_, status=stt))
            st.dataframe(pd.DataFrame(rows), hide_index=True, width='stretch')
    return groups, delta, acts, dacts, sup


def render_detail(out, res, g, a, ctx):
    st.subheader(f"Detail · {g['label']} (mark {g['mark']}) · {g['section']}", help=h('fix_props'))
    st_ = AIO.load_state(out)
    ls = [s_ for s_ in st_['stories'] if (g['label'], s_) in st_['cols']]
    stat = {}
    for r in res['results']:
        if r['label'] == g['label']:
            for q in r['per']:
                stat[q['story']] = q
    left, right = st.columns([1, 4])
    with left:
        st.markdown(f"Stories at {g['section']}", help='Top → bottom. Red = enlarge, blue = ρ 6–8 %, green = OK at ρ ≤ 6 %.')
        rows_ = ''
        for s_ in reversed(ls):
            q = stat.get(s_)
            k_, t_ = (('fail', 'enlarge') if s_ in g['stories'] and g['kind'] == 'enlarge' else
                      (('info', 'ρ 6–8 %') if s_ in g['stories'] else ('ok', 'OK ≤ 6 %')))
            rows_ += (f'<div class="srow"><span class="mono">{ui.esc(s_)}</span><span class="pill b-{k_}">{t_}</span>'
                      f'<span class="mono muted">{q["dc"]:.2f}</span></div>' if q else '')
        st.markdown(f'<div class="sstack">{rows_}</div>', unsafe_allow_html=True)
    with right:
        if g['kind'] == 'rho' and a['action'] == 'Approve ρ 6–8 %':
            st.dataframe(pd.DataFrame([dict(story=s_, bars=x['bars'], rho_pct=x['rho_pct'], DC=x['dc'], grid=x['grid'])
                                       for s_, x in zip(g['stories'], g['ap'])]), hide_index=True, width='stretch')
            st.caption(f"D/C ≤ 1.00 (section unchanged) · approval limit {rho_ask() * 100:.1f} % · splice: {a.get('splice')}")
            return
        if not a['action'].startswith('Enlarge'):
            st.caption('Choose an Enlarge action to see proposals.'); return
        c1, c2 = st.columns(2)
        if c1.button('Find proposals (options 1 and 2)', key=f'fp_{ctx}_{gkey(g)}', help=h('fix_props')):
            props(out, g, 1); props(out, g, 2)
        opt = int(a.get('option', 2))
        p1 = ss.props.get((out, g['label'], tuple(g['stories']), 1)); p2 = ss.props.get((out, g['label'], tuple(g['stories']), 2))
        if p1 or p2:
            cc = st.columns(2)
            for col_, (n_, p_) in zip(cc, ((1, p1), (2, p2))):
                with col_.container(border=True):
                    st.markdown(f"**{n_} · {'Row only' if n_ == 1 else 'Failing story down to the lowest'}**" + (' · chosen' if n_ == opt else ''))
                    if not p_:
                        st.caption('–'); continue
                    st.caption(f"Range {p_['range'][0]} – {p_['range'][-1]}")
                    if p_['options']:
                        o = p_['options'][0]
                        st.caption(f"best {o['kind']}: +{o['concrete_add_m3']} m³ · section changes {o['section_changes']} "
                                   f"(+{o['section_changes_added']})")
                        for w in o['warnings']:
                            st.warning(w)
                    else:
                        st.caption('no size within the limits – needs a new concept')
        p = ss.props.get((out, g['label'], tuple(g['stories']), opt))
        if p and p['options']:
            rows = [dict(kind=o['kind'], size=(f"Ø{o['b']}" if o['shape'] == 'circ' else f"{o['b']} × {o['h']}"), DC_max=o['dc_max'],
                         area_pct=o['area_pct'], concrete_add_m3=o['concrete_add_m3'],
                         bars=' · '.join(f"{q['story']} {q['bars']}" for q in o['per']),
                         continuity=' · '.join(f"{x['at']}: {x['offset_mm']:.0f} mm {'offset bend' if x['offset_bend'] else 'DOWELS'}" for x in o['offsets']))
                    for o in p['options']]
            st.dataframe(pd.DataFrame(rows), hide_index=True, width='stretch', column_config={
                'kind': st.column_config.TextColumn(help=h('fix_props')), 'DC_max': st.column_config.NumberColumn('D/C max', help='Highest D/C of the enlarged stories'),
                'continuity': st.column_config.TextColumn(help='Face offset at each section change: offset bend for the lap, or dowels (ACI 318-19 §10.7.4 – to confirm)')})
            kinds = [o['kind'] for o in p['options']]
            a['choice'] = st.radio('Proposal', kinds, index=kinds.index(a['choice']) if a.get('choice') in kinds else 0, horizontal=True,
                                   key=f'ch_{ctx}_{gkey(g)}_{opt}', help=h('fix_props'))
            if a['action'] != 'Enlarge – proposal':
                st.caption('The action is “type size” – the proposal is shown for reference.')
        elif p is not None:
            st.error('No size within +' + str(INPW.to_cfg(ss.tpl)['fix']['max_add_mm']) + ' mm reaches the target – type a size or choose another action.')
        st.markdown('**Or type a size**', help='Multiples of 50 mm; must reach D/C ≤ target. Leave as is to use the proposal.')
        x1, x2, x3 = st.columns(3)
        circ = g['shape'] == 'circ'
        tb = x1.number_input('Ø (mm)' if circ else 'b (mm)', 0, 3000, 0, 50, key=f'tb_{ctx}_{gkey(g)}')
        th = tb if circ else x2.number_input('h (mm)', 0, 3000, 0, 50, key=f'th_{ctx}_{gkey(g)}')
        if x3.button('Check typed size', key=f'ct_{ctx}_{gkey(g)}', disabled=not tb):
            fx = INPW.to_cfg(ss.tpl)['fix']
            rng = AIO.FX.ranges_for(out, g['label'], g['stories'], opt)
            r = AIO.FX.check_size(out, g['label'], rng, 'circ' if circ else 'rect', int(tb), int(th), g['stories'], opt, fx['target_dc'])
            r['kind'] = 'typed'
            a['typed'] = r; a['action'] = 'Enlarge – type size'; ss.fix_ver += 1
            st.rerun()
        if a.get('typed'):
            o = a['typed']
            (st.success if o['ok'] else st.error)(f"typed {o['b']} × {o['h']}: D/C max {o['dc_max']} – " +
                                                  ('OK' if o['ok'] else f"above the target {INPW.to_cfg(ss.tpl)['fix']['target_dc']}"))
        st.info('ETABS: a larger section changes stiffness and forces – the result is PROVISIONAL until ETABS is re-run (export on step 6).')


def apply_fix(out, groups, delta, acts, dacts, sup, round_ctx=False):
    """validate + write the actions into the inputs, then one re-run. Returns an error list (nothing changed) or None."""
    errs = []
    if not ss.engineer.strip():
        errs.append('Enter the engineer name at the top of the page.')
    enl, appr, spl = [], [], []
    for g in groups:
        a = acts[gkey(g)]
        if a['action'].startswith('Enlarge'):
            o = chosen_size(out, g, a)
            if not o:
                errs.append(f"{g['label']}: no size chosen – Detail → Find proposals or type a size"); continue
            if not o['ok']:
                errs.append(f"{g['label']}: size {o['b']}×{o['h']} does not reach the target D/C"); continue
            enl.append((g, a, o))
        elif a['action'] == 'Approve ρ 6–8 %':
            for s_ in g['stories']:
                if (g['label'], s_) not in sup:
                    appr.append([g['label'], s_])
                    if a.get('splice') and a['splice'] != 'Project default':
                        spl.append([g['label'], s_, s_, a['splice']])
        elif a['action'] == 'Accept overload':
            if not a.get('tick'):
                errs.append(f"{g['label']}: tick “I accept the overload” in the row (or choose another action)")
    for k, a in dacts.items():
        if a['action'] == 'Accept δ' and not a.get('reason', '').strip():
            errs.append(f'{k.replace("|", " ")}: reason required to accept δ')
    if errs:
        return errs
    t = now()
    for g, a, o in enl:
        rng = o['range']
        ss.tpl['enlarge'] = [r for r in ss.tpl.get('enlarge', []) if not (r[0] == g['label'] and (r[1] in rng or r[2] in rng))]
        for sg in o['segments']:                  # only the stories whose size changes (a larger existing side below is kept)
            ss.tpl['enlarge'].append([g['label'], sg['story_from'], sg['story_to'], sg['shape'], sg['b'], sg['h'], int(a.get('option', 2))])
            log('Section enlarged (fix board)', g['label'], f"{sg['story_from']} → {sg['story_to']}",
                f"{g['section']} → {'Ø' + str(sg['b']) if sg['shape'] == 'circ' else str(sg['b']) + '×' + str(sg['h'])} ({o['kind']}, option "
                f"{a.get('option', 2)}, D/C {o['dc_max']})", 'Designer – PROVISIONAL until ETABS is re-run', f'fix board ({ss.engineer})')
    for g in groups:
        a = acts[gkey(g)]
        if a['action'] == 'Accept overload':
            for s_ in g['stories']:
                ss.ovl_ok[(g['label'], s_)] = float(a['dc_lim'])
                ss.ovl_meta[(g['label'], s_)] = dict(at=t, by=ss.engineer)
    newa = [x for x in appr if x not in ss.approved]
    ss.approved = sorted({tuple(x) for x in ss.approved} | {tuple(x) for x in appr})
    ss.approved = [list(x) for x in ss.approved]
    for x in newa:
        log('ρ 6–8 % approved', x[0], x[1], f'ρ ≤ {rho_ask() * 100:.1f} %', 'Engineering judgment', f'fix board ({ss.engineer})')
    ss.tpl['splice'] = [r for r in ss.tpl.get('splice', []) if [r[0], r[1]] not in [[s[0], s[1]] for s in spl]] + spl
    for x in sup:
        log('ρ approval superseded by the enlargement', x[0], x[1], 're-designed on the new size', 'Result', 'fix board')
    for k, a in dacts.items():
        l_, s_ = k.split('|')
        if a['action'] == 'Accept δ':
            ss.tpl['delta_ok'] = [r for r in ss.tpl.get('delta_ok', []) if not (r[0] == l_ and r[1] == s_)] + [[l_, s_, float(a['limit'])]]
            log('δ accepted', l_, s_, f"δ ≤ {a['limit']} – {a['reason']}", 'Engineering judgment (CEDA limit 1.4)', f'fix board ({ss.engineer})')
    ss.visit += 1
    ss.props = {}
    do_run(f"{len(enl)} enlarged, {len(newa)} approved – {'round ' + str(len(ss.rounds) + 1) if round_ctx else 'step 6'}.")
    return None


# ================================================================================================ 5 Fix board
def page_fix():
    ui.head(5, 'Fix board', 'One row per label, failing stories and action. Choose an action, preview it in seconds, then apply all actions with one re-run.' + (f" Case: <b>{ss.case['fc_bottom']} ksc, reduce to typical at {ss.case['reduce_at'] or '–'}</b>." if ss.case else ''), help=h('step_fix'))
    if not ss.case:
        st.info("Choose the f'c case first (step 4)."); return
    st.markdown(f"Case **{ss.case['fc_bottom']:.0f} ksc, reduce to typical at {ss.case['reduce_at']}** ({ss.case['type']}) · "
                f"ρ ≤ 6 % for all, approval limit {rho_ask() * 100:.1f} %")
    ss.engineer = st.text_input('Engineer (confirms the decisions on this page)', value=ss.engineer, key=f'eng5_{ss.visit}', help=h('fix_engineer'))
    if ss.rounds:
        st.info('The fix board was applied – later fixes are made on step 6 (E).')
    groups, delta, acts, dacts, sup = render_fix(ss.out, 'p5')
    st.divider()
    a, b = st.columns(2)
    if a.button('Preview all rows', help=h('fix_preview'), disabled=not groups):
        with st.spinner('Quick check …'):
            for g in groups:
                ac = acts[gkey(g)]
                if ac['action'] == 'Enlarge – proposal':
                    props(ss.out, g, ac.get('option', 2))
        st.rerun()
    if b.button('✔ Apply all actions and re-run', type='primary', help=h('fix_apply'), disabled=not (groups or delta)):
        errs = apply_fix(ss.out, groups, delta, acts, dacts, sup)
        if errs:
            for e_ in errs:
                st.error(e_)
        else:
            ss.rounds = [dict(n=1, src='original exports (step 1)', enlarged=len(ss.tpl.get('enlarge', [])), out=ss.out, status='provisional – old forces'
                              if ss.tpl.get('enlarge') else 'forces with the final sizes')]
            ss._goto = '6 Final check'
            st.rerun()
    if not groups and not delta and st.button('No fixes needed → step 6', type='primary'):
        ss.rounds = [dict(n=1, src='original exports (step 1)', enlarged=0, out=ss.out, status='forces with the final sizes')]
        ss._goto = '6 Final check'; st.rerun()
    st.caption("f'c is a project decision – change it on step 4, not per column.")


# ================================================================================================ 6 Final check
def page_final():
    ui.head(6, 'Final check', "Everything after the fix board ends here: check with the old forces, update ETABS, upload the new forces, compare, fix again on this page, and finish. The f'c case chosen on step 4 stays locked.", help=h('step_final'))
    if not ss.rounds:
        st.info('Apply the fix board first (step 5).'); return
    res = res_of()
    prov = provisional()
    if prov:
        st.warning(f"PROVISIONAL · round {len(ss.rounds)} – {len(ss.tpl['enlarge'])} enlarged range(s) checked with the forces of an export "
                   'that has the old sizes. Update ETABS (B), then upload the new exports (C).')
    elif ss.final:
        st.success('FINAL – forces from ETABS with every final size, no open issue.')
    with st.container(border=True, key='card_page_final_1'):
        st.subheader('Rounds', help=h('fin_rounds'))
        st.dataframe(pd.DataFrame([{k: v for k, v in r.items() if k != 'out'} for r in ss.rounds]), hide_index=True, width='stretch')
    with st.container(border=True, key='card_page_final_2'):
        st.subheader('A · Check of the current round', help=h('fin_finish'))
        nrev = sum(1 for r in res['results'] for q in r['per'] if q['status'] in ('REVISE', 'ASK_RHO'))
        m = st.columns(5)
        m[0].metric('Open issues (D/C > 1)', nrev, help='Not passing and without an accepted decision')
        m[1].metric('Enlarged ranges', len(ss.tpl.get('enlarge', [])), help='Need the ETABS update (B)')
        m[2].metric('Approved ρ 6–8 %', len(ss.approved), help='Approved on the fix board, logged')
        m[3].metric('Accepted overload', len(ss.ovl_ok), help='Ticked this session, logged')
        m[4].metric('Accepted δ', len(ss.tpl.get('delta_ok', [])), help='With reason, logged')
    with st.container(border=True, key='card_page_final_3'):
        st.subheader('B · ETABS section update', help=h('fin_etabs'))
        if ss.tpl.get('enlarge'):
            st_ = AIO.load_state(ss.rounds[0]['out'])
            ov = []
            for r in ss.tpl['enlarge']:
                d0 = AIO.FX.dims(st_, r[0], r[2]) if (r[0], r[2]) in st_['cols'] else None
                ov.append(dict(label=r[0], story_from=r[1], story_to=r[2], shape=r[3], b_mm=r[4], h_mm=r[5], option=r[6],
                               old=(f'Ø{d0[1]}' if d0 and d0[0] == 'circ' else (f'{d0[1]}×{d0[2]}' if d0 else '')),
                               in_etabs=(r[0], r[1], r[2]) in set(tuple(x) for x in ss.etabs_done)))
            st.dataframe(pd.DataFrame(ov), hide_index=True, width='stretch')
            p = os.path.join(ss.workdir, 'ETABS_update.xlsx')
            AIO.FX.etabs_update_xlsx(ov, p, res['marks'])
            st.download_button('⬇ ETABS update (.xlsx)', open(p, 'rb').read(), f"{crit('project.job', 'JOB')}_ETABS_section_update.xlsx", help=h('fin_etabs'))
        else:
            st.caption('No enlarged section.')
    with st.container(border=True, key='card_page_final_4'):
        st.subheader('C · Re-check with the new ETABS exports', help=h('fin_upload'))
        cols = st.columns(3)
        for c_, (slot, title) in zip(cols, (('seismic', '6.1 Seismic model'), ('full_unreduced', '6.2 Full model – unreduced'),
                                            ('full_reduced', '6.3 Full model – reduced (if used in round 1)'))):
            with c_.container(border=True):
                up = st.file_uploader(title, type=['xlsx', 'xlsm'], accept_multiple_files=True, key=f'r_{slot}_{len(ss.rounds)}', help=h('fin_upload'))
                if up:
                    ss.rfiles[slot] = [(f.name, f.getvalue()) for f in up]
                for n, d in ss.rfiles.get(slot, []):
                    st.caption(f'📄 {n}')
        st.caption('Kept from the project: load combinations, lap table, inputs, decisions, f\'c case, mark names.')
        need = ['seismic'] + (['full_reduced'] if ss.files.get('full_reduced') else []) + (['full_unreduced'] if ss.files.get('full_unreduced') else [])
        ready = all(ss.rfiles.get(s_) for s_ in need)
        if st.button(f'▶ Re-check round {len(ss.rounds) + 1} (≈ 40 s)', type='primary', disabled=not ready, help=h('fin_upload')):
            ss.out_old = ss.out
            old_files = dict(ss.files)
            for s_ in need:
                ss.files[s_] = ss.rfiles[s_]
            done = [list(r[:3]) for r in ss.tpl.get('enlarge', [])]
            ss.etabs_done = done
            do_run(f'Round {len(ss.rounds) + 1} done – check the compare (D).')
            match = AIO.FX.section_match(ss.out, [dict(label=r[0], story_from=r[1], story_to=r[2], shape=r[3], b_mm=r[4], h_mm=r[5])
                                                  for r in ss.tpl.get('enlarge', [])])
            bad = [m_ for m_ in match if not m_['ok']]
            ss.last_match = match
            if bad:
                ss.files = old_files; ss.etabs_done = []
                ss.msg = 'Section match failed – the new export does not have the design sizes (see C).'
                ss.out = ss.out_old
            else:
                ss.rfiles = {}
                ss.rounds.append(dict(n=len(ss.rounds) + 1, src='new exports (step 6 C)', enlarged=len(ss.tpl.get('enlarge', [])), out=ss.out,
                                      status='forces with the final sizes'))
                log(f'Round {len(ss.rounds)} – new ETABS exports', '', '', ', '.join(n for s_ in need for n, _ in ss.files[s_]), 'Input', 'step 6')
            st.rerun()
        if ss.get('last_match'):
            st.markdown('**Section match**', help=h('fin_match'))
            st.dataframe(pd.DataFrame(ss.last_match), hide_index=True, width='stretch')
        if ss.out_old and len(ss.rounds) > 1:
            st.subheader('D · Old vs new forces', help=h('fin_compare'))
            ddc = float(INPW.to_cfg(ss.tpl)['fix']['compare_ddc'])
            rows, summ = AIO.FX.compare(res_of(ss.out_old), res, ddc)
            m = st.columns(4)
            m[0].metric('Now failing', summ['failing']); m[1].metric(f'|ΔD/C| > {ddc}', summ['changed'])
            m[2].metric('Bars changed', summ['bars_changed']); m[3].metric('Marks changed', summ['marks_changed'])
            flt = st.selectbox('Show', ['Enlarged + changed + failing', 'Failing only', 'All'], help=h('fin_compare'))
            df = pd.DataFrame(rows)
            if flt == 'Failing only':
                df = df[df['status'] == 'REVISE']
            elif flt.startswith('Enlarged'):
                df = df[df['why'].map(bool)]
            st.dataframe(df.assign(why=df['why'].map(', '.join)), hide_index=True, width='stretch')
            rs = AIO.FX.reduction_share(ss.out, ss.case['reduce_at'])
            if rs is not None and rs < 0.5:
                st.warning(f"Reduction-story rule with the new forces: {ss.case['reduce_at']} has {rs * 100:.0f} % of columns at ρ ≤ 1.5 % (rule 50 %). "
                           "Warning only – the f'c case stays locked; changing it means step 4 and a new design.")
        if nrev or (len(ss.rounds) > 1 and groups_now(ss.out)[1]):
            st.subheader('E · Fix on this page', help=h('step_fix'))
            ss.engineer = st.text_input('Engineer', value=ss.engineer, key=f'eng6_{ss.visit}', help=h('fix_engineer'))
            groups, delta, acts, dacts, sup = render_fix(ss.out, f'p6r{len(ss.rounds)}')
            if st.button('✔ Apply and re-run', type='primary', help=h('fix_apply'), disabled=not (groups or delta)):
                errs = apply_fix(ss.out, groups, delta, acts, dacts, sup, round_ctx=True)
                if errs:
                    for e_ in errs:
                        st.error(e_)
                else:
                    ss.rounds.append(dict(n=len(ss.rounds) + 1, src='fixes on step 6 (E)', enlarged=len(ss.tpl.get('enlarge', [])), out=ss.out,
                                          status='provisional – old forces' if provisional() else 'forces with the final sizes'))
                    st.rerun()
    with st.container(border=True, key='card_page_final_5'):
        st.subheader('F · Finish', help=h('fin_finish'))
        st.dataframe(pd.DataFrame([dict(status='✔' if not prov else '!', condition='Forces from ETABS with the final sizes',
                                        now='yes' if not prov else 'round uses old forces'),
                                   dict(status='✔' if nrev == 0 else '!', condition='Open issues = 0', now=str(nrev))]), hide_index=True, width='stretch')
        a, b = st.columns(2)
        with a.container(border=True):
            st.markdown('**Mark design FINAL**')
            ren = st.checkbox('Renumber marks by section size (C1 = largest)', value=str(crit('marks.renumber', 'Y')).upper().startswith('Y'),
                              help=h('marks.renumber'))
            if st.button('Mark FINAL', type='primary', disabled=prov or nrev > 0 or ss.final):
                old = res['marks']
                if ren:
                    res2 = do_run('FINAL – marks renumbered by section size.', renumber=True)
                    ss.rename = AIO.rename_table(old, res2['marks']); lock_marks(res2)
                ss.final = True
                log('Design marked FINAL', '', '', 'marks renumbered' if ren else 'marks kept', 'Designer', f'step 6 ({ss.engineer})')
                st.rerun()
        with b.container(border=True):
            st.markdown('**Continue provisional**')
            tk = st.checkbox('I continue with provisional results', key='provtk')
            nm = st.text_input('Name', value=ss.engineer, key='provnm')
            if st.button('Continue to 7 Results', disabled=not (tk and nm.strip())):
                ss.prov_ok = dict(by=nm.strip(), at=now())
                log('Continue PROVISIONAL', '', '', f'{len(ss.tpl.get("enlarge", []))} enlarged ranges, open issues {nrev}', 'Designer', f'step 6 ({nm.strip()})')
                ss._goto = '7 Results'; st.rerun()
        if ss.get('rename'):
            st.markdown('**Mark rename table**')
            st.dataframe(pd.DataFrame(ss.rename), hide_index=True, width='stretch')


# ================================================================================================ 7 Results
def cell(r):
    d = AIO.LY.describe(r['counts'], r.get('phase', 0))
    return f"{r['nbar']}-DB{r['db']}" + (' (' + d.lower().replace('bundle ', 'b').replace(' @ tie corners', '') + ')' if d else '')


def sec_txt(r):
    return f"Ø{r['b'] * 10:.0f}" if r['shape'] == 'circ' else f"{r['b'] * 10:.0f}×{r['h'] * 10:.0f}"


def page_results():
    ui.head(7, 'Results', 'Final design of the chosen case with the fixes. Shown on screen; files are made on step 8.', help=h('step_results'))
    if not ss.out:
        st.info('Run the design first (step 3).'); return
    res = res_of()
    R = res['results']
    if provisional():
        st.warning(f"PROVISIONAL – {len(ss.tpl['enlarge'])} enlarged range(s), ETABS not yet re-run.")
    cnt = lambda s_: sum(1 for r in R for q in r['per'] if q['status'] == s_)
    m = st.columns(7)
    m[0].metric('Label-stories', sum(len(r['per']) for r in R), help='Column segments checked')
    m[1].metric('Marks', len(set(res['marks'].values())), help=h('m_marks'))
    m[2].metric('OK', cnt('OK'), help=h('m_ok')); m[3].metric('ACCEPTED', cnt('ACCEPTED'), help=h('m_acc'))
    m[4].metric('REVISE + ASK', cnt('REVISE') + cnt('ASK_RHO'), help=h('m_rev'))
    q = AIO.boq(ss.out, prices_now())
    m[5].metric('Concrete m³', f"{sum(q['concrete_m3'].values()):,.1f}", help=h('boq'))
    m[6].metric('Main bars t', f"{sum(q['steel_kg'].values()) / 1000:,.1f}", help=h('boq'))
    marks = sorted(set(res['marks'].values()), key=lambda m_: int(''.join(ch for ch in m_ if ch.isdigit()) or 0))
    t = st.tabs(['Table of Column', 'Decisions', 'Quantities', 'Notes'])
    with t[0]:
        bands = [tuple(b_) for b_ in res['bands']]
        ref = {(r['mark'], tuple(r['band'])): r for r in R if r.get('ref')}
        RANK = {'OK': 0, 'ACCEPTED': 1, 'ASK_RHO': 2, 'REVISE': 3}
        CLS = {1: 'tc-acc', 2: 'tc-ask', 3: 'tc-rev'}
        x, y = st.columns([3, 1], vertical_alignment='bottom')
        x.markdown(f'### Table of Column ({len(marks)} marks)', help='Rows = story ranges (Table of Column rows), columns = marks. '
                   'Hover a cell for ties and D/C. Amber = enlarged on the fix board, yellow = ACCEPTED overload, red = REVISE / ASK.')
        shown = y.multiselect('Marks', marks, default=marks, key='toc_marks', help='Marks shown in the table')
        th = '<th>Story range</th><th class="n">f\'c</th>' + ''.join(f'<th>{ui.esc(mk)}</th>' for mk in shown)
        body = ''
        for b_ in reversed(bands):
            tr = f'<td class="mono"><b>{ui.esc(b_[0])}</b>' + (f' → {ui.esc(b_[1])}' if b_[1] != b_[0] else '') + \
                 f'</td><td class="n">{res["fc_of"][b_[0]]:.0f}</td>'
            for mk in shown:
                r = ref.get((mk, b_))
                if not r:
                    tr += '<td class="tc">–</td>'; continue
                qs = [x_ for x_ in R if x_['mark'] == mk and tuple(x_['band']) == b_]
                dcm = max(q_['dc'] for x_ in qs for q_ in x_['per'])
                worst = max(RANK.get(q_['status'], 3) for x_ in qs for q_ in x_['per'])
                enl = any(x_.get('enlarged') for x_ in qs)
                tip = (f"{mk} {b_[0]}→{b_[1]} · {sec_txt(r)} · {cell(r)} · ties {r['nset']} sets DB{r['tie_db']}@{r['so']}/{r['s']} · "
                       f"D/C {dcm:.2f}" + (' · ENLARGED (fix board)' if enl else ''))
                cls = CLS.get(worst) or ('tc-enl' if enl else '')
                tr += (f'<td class="tc {cls}" title="{ui.esc(tip)}">{sec_txt(r)} {r["nbar"]}-DB{r["db"]}'
                       f'<span class="dc">{dcm:.2f}</span></td>')
            body += f'<tr>{tr}</tr>'
        st.markdown(f'<div class="scroll toc"><table class="t"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>',
                    unsafe_allow_html=True)
        st.caption('Cell: section · main bars · max D/C of the mark in the range. Hover for ties. Sizes in mm.')
    with t[1]:
        rows = []
        for r in R:
            for q_ in r['per']:
                rows.append(dict(mark=r['mark'], label=r['label'], story=q_['story'], range=f"{r['band'][0]}→{r['band'][1]}",
                                 section=sec_txt(r), fc=q_['fc'], bars=cell(r), rho_pct=round(q_['rho'] * 100, 2), DC=round(q_['dc'], 3),
                                 combo=q_['gov'].get('combo', ''), Pu_t=round(q_['gov']['P'] / 1e3, 1), delta=round(max(q_['dmax_x'], q_['dmax_y']), 2),
                                 ties=f"{r['nset']}ป DB{r['tie_db']}@{r['so']}/{r['s']}", splice=r.get('splice', ''),
                                 lap=r.get('lap'), enlarged='yes' if r.get('enlarged') else '', status=q_['status']))
        df = pd.DataFrame(rows)
        flt = st.multiselect('Status', sorted(df['status'].unique()), default=sorted(df['status'].unique()), help='Filter the rows')
        st.dataframe(df[df['status'].isin(flt)], hide_index=True, width='stretch')
    with t[2]:
        qq = [dict(item=f"concrete {float(k):.0f} ksc", qty=round(v, 1), unit='m³') for k, v in q['concrete_m3'].items()] + \
             [dict(item=f"main bars DB{float(k):.0f}", qty=round(v / 1000, 2), unit='t') for k, v in q['steel_kg'].items()]
        st.dataframe(pd.DataFrame(qq), hide_index=True, width='stretch')
        st.caption('Final design after ranges and marks; ties, laps and couplers not included. Cost: ' +
                   (f"{q['cost_thb']:,.0f} THB (example prices – information only)" if q['cost_thb'] else 'no prices'))
    with t[3]:
        for n in res['notes']:
            (st.error if n.startswith(('SWAY', 'combo')) else st.warning if n.startswith('ENLARGED') else st.caption)(n)
    # ------------------------------------------------------------------ column detail
    with st.container(border=True, key='card_page_results_1'):
        st.subheader('Column detail', help=h('detail'))
        labs = sorted({r['label'] for r in R}, key=lambda x: (len(x), x))
        a, b, c = st.columns([2, 2, 3])
        lab = a.selectbox('Label', labs, key='cd_lab', help='ETABS column label')
        sts = [s_ for s_ in res['stories'] if any(r['label'] == lab and s_ in r['stories'] for r in R)]
        sto = b.selectbox('Story', sts, key='cd_sto', help='Story of this label')
        rr = next(r for r in R if r['label'] == lab and sto in r['stories'])
        qq = next(x for x in rr['per'] if x['story'] == sto)
        c.metric('D/C · status', f"{qq['dc']:.3f} · {qq['status']}", help='Biaxial D/C of this column-story')

        @st.cache_resource(show_spinner='Building the surface …', max_entries=12)
        def _surf(out_, lab_, sto_, stamp_):
            return AIO.surface_figures(AIO.label_story_eval(out_, lab_, sto_))

        @st.cache_data(show_spinner='Drawing the section …', max_entries=24)
        def _sec(out_, lab_, sto_, stamp_):
            return AIO.section_png(out_, lab_, sto_)[0]
        stamp = os.path.getmtime(os.path.join(ss.out, 'results.json'))
        l_, r_ = st.columns([3, 2])
        f3, f2, fc_, gov = _surf(ss.out, lab, sto, stamp)
        with l_:
            st.markdown('**Interaction surface**', help='3D φ-surface of this column-story with every combination point; rotate and hover.')
            st.plotly_chart(f3, width='stretch')
        with r_:
            st.markdown(f"**Section – {lab} {sto} (mark {rr['mark']})**", help='Drawn to scale from the design: bars, bundles, hoops and crossties.')
            st.image(_sec(ss.out, lab, sto, stamp), width='stretch')
            g_ = qq['gov']
            st.caption(f"{sec_txt(rr)} · f'c {qq['fc']:.0f} · {cell(rr)} (ρ {qq['rho'] * 100:.2f} %) · ties DB{rr['tie_db']} {rr['nset']} sets, "
                       f"so {rr['so']} / s {rr['s']} · lap {rr.get('lap') or '—'} mm · splice {rr.get('splice', '')}")
        x1, x2 = st.columns([2, 1])
        with x1.container(border=True):
            st.markdown(f"**Checks – {lab} {sto}**")
            st.caption(f"governing {g_.get('combo', '')} · P {g_['P'] / 1e3:,.1f} t · Mx {g_['Mx'] / 1e3:,.1f} t-m · My {g_['My'] / 1e3:,.1f} t-m · "
                       f"δ {max(qq['dmax_x'], qq['dmax_y']):.2f} · shear D/C " +
                       ' · '.join(f"{k} {v['dc_lo']:.2f}" for k, v in qq['shear'].items()))
        with x2.container(border=True):
            st.markdown('**Column plan**', help=h('plan'))
            pst = st.selectbox('Story', res['stories'], key='pm_story', help=h('plan'))
            if st.button('Make plan', help=h('plan')):
                try:
                    ss.pm = (pst,) + AIO.plan_map(ss.wd, ss.out, pst)
                except Exception as e:
                    st.error(f'plan_map: {e}')
            if ss.get('pm') and ss.pm[0] == pst and os.path.exists(ss.pm[2]):
                _, pdf, dxp, prow = ss.pm
                st.download_button('PDF', open(pdf, 'rb').read(), os.path.basename(pdf))
                st.download_button('DXF', open(dxp, 'rb').read(), os.path.basename(dxp))
                st.image(AIO.dxf_png(dxp, 80), width='stretch')


# ================================================================================================ 8 Documents
def page_docs():
    ui.head(8, 'Documents', 'Make the files you need. Heavy documents are made only on request.', help=h('step_docs'))
    if not ss.out:
        st.info('Run the design first (step 3).'); return
    res = res_of()
    job = res['config']['project'].get('job', 'job')
    prov = provisional()
    ready = AIO.documents_ready(ss.out)
    rows = [('Decisions log (.xlsx)', "f'c case, fixes, approvals, assumptions, names and times", os.path.join(ss.out, f'{job}_Column_Decisions_Log.xlsx'), None),
            ('Input workbook used (.xlsx)', 'All inputs of this run (v1.5.0), re-usable on step 1.6', os.path.join(ss.out, f'{job}_Column_Input_used.xlsx'), None),
            ('Decision table (.xlsx)', 'Label × story: section, f\'c, bars, ρ, D/C, combo, kLu/r, δ, status', os.path.join(ss.out, f'{job}_Column_Decision.xlsx'), None)]
    if ss.tpl.get('enlarge'):
        rows.append(('ETABS section update (.xlsx)', 'New sizes of the enlarged labels', os.path.join(ss.workdir, 'ETABS_update.xlsx'),
                     f'{job}_ETABS_section_update.xlsx'))
    ren = None
    if ss.get('rename'):
        bio = io.BytesIO(); pd.DataFrame(ss.rename).to_excel(bio, index=False); ren = bio.getvalue()
    with st.container(border=True, key='card_docs_files'):
        st.markdown('### Files', help='Ready files download at once; the heavy documents are made with the button below.')
        hd = st.columns([2.2, 3.6, 1, 1.2])
        for c_, t_ in zip(hd, ['Document', 'Content', 'Status', '']):
            c_.markdown(f'**{t_}**')
        def line(name, content, data, fname):
            c = st.columns([2.2, 3.6, 1, 1.2], vertical_alignment='center')
            c[0].markdown(f'**{name}**'); c[1].caption(content)
            c[2].markdown(ui.badge('ready', 'ok') if data else ui.badge('on request', 'gray'), unsafe_allow_html=True)
            if data:
                c[3].download_button('Download', data, fname, key='dd_' + fname, width='stretch')
        for name, content, path, fname in rows:
            line(name, content, open(path, 'rb').read() if os.path.exists(path) else None, fname or os.path.basename(path))
        line('Mark rename table (.xlsx)', 'Locked name → final name, made at Mark FINAL', ren, f'{job}_Mark_rename.xlsx')
        for name, content in (('Calculation PDF', 'Per mark: governing combination, surface, slenderness, ties, lap'),
                              ('Back-up Excel', 'All label-stories + one file per mark (live formulas)'),
                              ('Table of Column DXF / PDF / Excel', 'Draft drawing, CEDA layers; schedule for Revit')):
            if not ready:
                line(name, content, None, '')
        if prov:
            st.warning('PROVISIONAL – documents carry the PROVISIONAL label until ETABS is re-run with the enlarged sizes.')
    if ss.extra_log:
        with st.container(border=True, key='card_docs_log'):
            st.markdown('### Decisions log preview', help='Decisions made on screen this session (the full log is in the Excel).')
            ui.table(['Time', 'Decision', 'Label', 'Story', 'Basis', 'By'],
                     [[ui.esc(e[6]), ui.esc(f"{e[0]} – {e[3]}"), ui.esc(e[1]), ui.esc(e[2]), ui.esc(e[4]), ui.esc(e[5])] for e in ss.extra_log[-12:]],
                     mono=(0,))
    if not AIO.documents_ready(ss.out):
        st.info('Calculation PDF, back-up Excel, Table of Column DXF/PDF and schedule are made on request.')
        if st.button('Make calculation PDF, back-up Excel and Table of Column (several minutes)', type='primary', help=h('docs_make')):
            with st.spinner('make_outputs.py …'):
                if prov:
                    rp = os.path.join(ss.out, 'results.json'); rj = json.load(open(rp))
                    nm = rj['config']['project'].get('name', '')
                    if 'PROVISIONAL' not in nm:
                        rj['config']['project']['name'] = (nm + ' – ' if nm else '') + 'PROVISIONAL (ETABS not re-run)'
                        json.dump(rj, open(rp, 'w'), ensure_ascii=False, indent=1)
                AIO.make_documents(ss.out)
            st.rerun()
        return
    st.download_button('⬇ All outputs (ZIP)', AIO.zip_all(ss.out), f"{job}_Column_outputs{'_PROVISIONAL' if prov else ''}.zip", type='primary',
                       help='Every file of the run')
    main_files, per_mark = AIO.files(ss.out)
    with st.container(border=True, key='card_page_docs_1'):
        st.subheader('Project files', help='Files for the whole project')
        for p, n, d in main_files:
            st.download_button(f'{n} – {d}', open(p, 'rb').read(), n, key='dl_' + n, help=d)
    with st.container(border=True, key='card_page_docs_2'):
        st.subheader('Per mark', help='Calculation sheets and back-up Excel of each mark')
        for mk_ in sorted(per_mark, key=lambda m_: int(''.join(ch for ch in m_ if ch.isdigit()) or 0)):
            a, b, c = st.columns([1, 2, 2])
            a.markdown(f'**{mk_}**')
            if 'Calc.pdf' in per_mark[mk_]:
                b.download_button(f'{mk_} calculation (PDF)', open(per_mark[mk_]['Calc.pdf'], 'rb').read(), os.path.basename(per_mark[mk_]['Calc.pdf']), key='c_' + mk_)
            if 'Backup.xlsx' in per_mark[mk_]:
                c.download_button(f'{mk_} back-up (Excel)', open(per_mark[mk_]['Backup.xlsx'], 'rb').read(), os.path.basename(per_mark[mk_]['Backup.xlsx']), key='b_' + mk_)
    with st.container(border=True, key='card_page_docs_3'):
        st.subheader('Detailed CEDA-style Excel', help='9-point diagrams, load sheet, XY check – one mark and story range')
        a, b, c = st.columns(3)
        marks = sorted(per_mark, key=lambda m_: int(''.join(ch for ch in m_ if ch.isdigit()) or 0))
        if marks:
            dmk = a.selectbox('Mark', marks, key='dmk')
            dbd = b.selectbox('Story range', [tuple(r['band']) for r in res['results'] if r['mark'] == dmk and r.get('ref')],
                              format_func=lambda x: f'{x[0]} → {x[1]}', key='dbd')
            if c.button('Make detailed Excel'):
                p = AIO.detail_excel(ss.out, dmk, dbd[0])
                st.download_button(f'⬇ {os.path.basename(p)}', open(p, 'rb').read(), os.path.basename(p))


PAGES = {'1 Files': page_files, '2 Inputs': page_inputs, '3 Check & run': page_check, "4 f'c study": page_fc, '5 Fix board': page_fix,
         '6 Final check': page_final, '7 Results': page_results, '8 Documents': page_docs}
PAGES[page]()
# v5.1 footer of steps 2–7 (step 1 has its own): note + Next
FOOT = {'2 Inputs': ('Changed values are marked in the workbook when saved, and logged.', '3 Check & run', lambda: prep_now() is not None),
        '3 Check & run': ("After the run: step 4 opens.", "4 f'c study", lambda: bool(ss.cases)),
        "4 f'c study": ('The chosen case is locked for the rest of the project (mark names too).', '5 Fix board', lambda: bool(ss.case)),
        '5 Fix board': ('Apply all actions first – the final check starts from the applied design.', '6 Final check', lambda: bool(ss.rounds)),
        '6 Final check': ('FINAL needs the final sizes in ETABS and no open issue; otherwise continue PROVISIONAL.', '7 Results',
                          lambda: bool(res_of())),
        '7 Results': ('Nothing is changed on this step.', '8 Documents', lambda: bool(res_of()))}
if page in FOOT:
    note, nxt, ok_ = FOOT[page]
    if ui.foot(note, f'Next: {nxt} →', key='foot_' + page[0], disabled=not ok_()):
        ss._goto = nxt; st.rerun()
