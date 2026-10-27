"""v5.1 look of the app (CEDA UI mock-ups, 27 Oct 2026): CSS, page head, step navigation, cards, file rows, footer.

Only presentation – no design rule here. Colours / fonts = the mock-ups (IBM Plex Sans / Mono, navy sidebar, white cards).
Streamlit classes used: `st-key-<key>` of keyed containers / buttons (stable public API since 1.40) and data-testid's for a
few widgets; if Streamlit changes them the app still works, only the styling falls back to the theme.
"""
import html
import streamlit as st

STEP_TITLES = ['Files', 'Inputs', 'Check & run', "f'c study", 'Fix board', 'Final check', 'Results', 'Documents']

CSS = """
<style>
:root{--ink:#1B2230;--muted:#5A6372;--line:#DDE1E7;--blue:#1F5FA8}
.block-container{padding-top:2.2rem;padding-bottom:3rem;max-width:1280px}
h1,h2,h3,h4{font-family:'IBM Plex Sans',sans-serif;color:var(--ink)}
[data-testid="stMainBlockContainer"] h1{font-size:28px;font-weight:600;padding:2px 0 2px}
[data-testid="stMainBlockContainer"] h2{font-size:18px;font-weight:600}
[data-testid="stMainBlockContainer"] h3{font-size:15px;font-weight:600}
.crumb{font:500 12px 'IBM Plex Mono',monospace;color:var(--muted);letter-spacing:.06em;text-transform:uppercase;margin-bottom:-8px}
.lead{color:#4A5463;margin:-6px 0 4px;font-size:14.5px}
/* cards = keyed bordered containers */
[class*="st-key-card_"]{background:#fff;border-radius:8px}
.ch{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.ch .num{font:600 14px 'IBM Plex Mono',monospace;color:var(--muted)}
.ch .ttl{font-weight:600;font-size:15.5px;color:var(--ink)}
.ch .sp{flex:1}
.desc{color:#4A5463;font-size:13.5px;margin-top:-6px}
.badge{display:inline-flex;align-items:center;gap:4px;border-radius:4px;padding:2px 8px;font:600 11.5px 'IBM Plex Sans',sans-serif;letter-spacing:.02em;white-space:nowrap}
.b-ok{background:#E3F1E8;color:#1F5E3A}.b-warn{background:#FBEFD9;color:#7A4E00}.b-fail{background:#FBE4E1;color:#8E1B12}
.b-info{background:#E4EDF8;color:#1A4F8C}.b-gray{background:#ECEEF2;color:#3E4757}
.file{display:flex;align-items:center;gap:10px;border:1px solid var(--line);border-radius:6px;padding:9px 12px;background:#fff;min-height:22px}
.file .nm{font:500 13px 'IBM Plex Mono',monospace;color:var(--ink);overflow-wrap:anywhere}
.file .sz{margin-left:auto;font:12px 'IBM Plex Mono',monospace;color:var(--muted);white-space:nowrap}
.chips{display:flex;gap:6px;flex-wrap:wrap}
.chip{border:1px solid #C5CBD4;border-radius:16px;padding:3px 11px;font:500 12.5px 'IBM Plex Mono',monospace;background:#fff;color:#2A3242}
table.t{border-collapse:collapse;width:100%;font-size:13px;background:#fff;border:1px solid #E3E6EB;border-radius:6px}
.t th{background:#F0F2F5;text-align:left;font-weight:600;padding:8px 10px;border-bottom:1px solid var(--line);white-space:nowrap;color:#2A3242}
.t td{padding:8px 10px;border-bottom:1px solid #EEF0F3;vertical-align:top}
.t td.mono{font-family:'IBM Plex Mono',monospace}
/* tables */
.scroll{overflow-x:auto;border:1px solid #E3E6EB;border-radius:6px}
.scroll table.t{border:0}
.t th.n,.t td.n{text-align:right;font-family:'IBM Plex Mono',monospace}
.t th{vertical-align:bottom}
.t th.grp{text-align:center;border-bottom:1px solid var(--line);font-family:'IBM Plex Sans',sans-serif}
.t thead th{font-size:12.5px}
.t.cases th.n{font-family:'IBM Plex Mono',monospace;font-weight:600}
.t tr.sel td{background:#EAF2FC}
.t td.fc{font-weight:600;font-size:14px;color:var(--ink)}
.qq{display:inline-flex;width:16px;height:16px;border-radius:50%;border:1px solid #8A94A3;align-items:center;justify-content:center;
  font:600 10px 'IBM Plex Sans',sans-serif;color:#3E4757;cursor:help;margin-left:4px;background:#fff;vertical-align:middle}
.strip{display:grid;gap:2px}
.strip div{font:500 10.5px 'IBM Plex Mono',monospace;text-align:center;padding:6px 0;border-radius:3px}
.s6{background:#1F5FA8;color:#fff}.s4{background:#D6E2F2;color:#1B2230}
/* inputs white like the mock-ups */
[data-testid="stMainBlockContainer"] [data-baseweb="input"],[data-testid="stMainBlockContainer"] [data-baseweb="select"] > div,
[data-testid="stMainBlockContainer"] [data-baseweb="textarea"],[data-testid="stMainBlockContainer"] [data-baseweb="input"] input{background:#fff}
[data-testid="stMainBlockContainer"] [data-baseweb="input"] input,[data-testid="stMainBlockContainer"] [data-baseweb="select"]{font-family:'IBM Plex Mono',monospace}
/* tabs: larger, panel as a white card */
[data-baseweb="tab-list"] button p{font-size:14.5px}
[role="tabpanel"]{background:#fff;border:1px solid var(--line);border-radius:8px;padding:18px 20px!important;margin-top:10px}
/* detail story stack */
.sstack{display:flex;flex-direction:column;gap:3px}
.srow{display:grid;grid-template-columns:44px 1fr 40px;gap:6px;align-items:center;font-size:12px}
.pill{border-radius:3px;padding:2px 6px;font:500 11.5px 'IBM Plex Sans',sans-serif}
.mono{font-family:'IBM Plex Mono',monospace}.muted{color:var(--muted)}
.t.cases th{white-space:normal;padding:6px 7px}.t.cases td{padding:6px 7px;white-space:nowrap}
[data-testid="stMainBlockContainer"] input,[data-testid="stMainBlockContainer"] textarea,
[data-testid="stMainBlockContainer"] [data-baseweb="base-input"]{background:#fff!important}
/* every bordered container on the page = white card */
[data-testid="stMainBlockContainer"] [data-testid="stVerticalBlockBorderWrapper"],[class*="st-key-card"]{background:#fff}
/* Table of Column */
.toc{max-height:720px}
.toc table.t th{position:sticky;top:0;z-index:1;text-align:center;font-family:'IBM Plex Mono',monospace}
.toc table.t td:first-child,.toc table.t th:first-child{position:sticky;left:0;background:#fff;z-index:2}
.toc td.tc{font:12px 'IBM Plex Mono',monospace;text-align:center;white-space:nowrap;border-left:1px solid #EEF0F3}
.toc td.tc .dc{display:block;color:var(--muted);font-size:10.5px}
.tc-enl{background:#FBEFD9!important;color:#5E3C00}.tc-acc{background:#FFF3C4!important}
.tc-ask{background:#FFE0B2!important}.tc-rev{background:#F8C9C9!important;color:#7A170F}
/* upload drop zone */
[data-testid="stFileUploaderDropzone"]{background:#FAFBFC;border:1.5px dashed #B5BDC8;border-radius:8px}
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"]{background:#253046;border-color:#46526A}
/* footer */
.footnote{color:var(--muted);font-size:13px;padding-top:10px}
[class*="st-key-foot"]{border-top:1px solid var(--line);padding-top:12px;margin-top:8px}
/* metrics as white tiles */
[data-testid="stMetric"]{background:#fff;border:1px solid var(--line);border-radius:8px;padding:12px 14px}
[data-testid="stMetricValue"]{font-family:'IBM Plex Mono',monospace;font-size:22px}
/* sidebar */
[data-testid="stSidebar"] .brand{font-weight:600;font-size:16px;color:#fff}
[data-testid="stSidebar"] .brand small{display:block;font-weight:400;font-size:12px;color:#AEB8C6;margin-top:2px;line-height:1.4}
[data-testid="stSidebar"] .brand{margin-bottom:10px;line-height:1.3}
.st-key-projbox{background:#253046;border-radius:8px;padding:12px}
.st-key-projbox .proj{padding:0 0 12px;background:transparent}
.st-key-projbox [data-testid="stMarkdownContainer"]{overflow:visible}
[data-testid="stSidebar"] .stDownloadButton button,[data-testid="stSidebar"] [data-testid="stPopover"] button{background:transparent;
  border:1px solid #46526A;color:#E8ECF2;justify-content:flex-start}
[data-testid="stSidebar"] .stDownloadButton button:disabled{color:#8792A3}
.proj{background:#253046;border-radius:8px;padding:12px;font-size:13px;color:#D5DCE6;line-height:1.5}
.proj b{color:#fff}
.sfoot{font-size:12px;color:#AEB8C6;margin-top:18px}
[class*="st-key-nav_"] button{background:transparent;border:0;color:#C9D1DC;justify-content:flex-start;padding:8px 12px;min-height:40px;
  width:100%;box-shadow:none}
[class*="st-key-nav_"] button:hover{background:#232D40;color:#fff}
[class*="st-key-nav_"] button p{font-size:14px;text-align:left}
[class*="st-key-nav_"] button > div{justify-content:flex-start;width:100%}
[class*="st-key-nav_"] button::before{content:var(--n);width:20px;height:20px;border-radius:50%;display:inline-flex;align-items:center;
  justify-content:center;font:600 11px 'IBM Plex Mono',monospace;margin-right:10px;flex:none;border:1px solid #6B778A;color:#AEB8C6}
[class*="st-key-nav_"][class*="_done"] button::before{background:#2E7D4F;border-color:#2E7D4F;color:#fff}
[class*="st-key-nav_"][class*="_warn"] button::before{background:#E0A33A;border-color:#E0A33A;color:#1B2230}
[class*="st-key-nav_"][class*="_on"] button{background:#2F3B54;color:#fff}
[class*="st-key-nav_"][class*="_on"] button p{font-weight:600}
[class*="st-key-nav_"][class*="_on"] button::before{background:#4D8FE0;border-color:#4D8FE0;color:#fff}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"]{gap:.35rem}
</style>
"""


def css():
    st.markdown(CSS, unsafe_allow_html=True)
    # numbers in the step circles (CSS variable per button)
    st.markdown('<style>' + ''.join(f'[class*="st-key-nav_{i}_"] button{{--n:"{i}"}}' for i in range(1, 9)) + '</style>',
                unsafe_allow_html=True)


def esc(x):
    return html.escape(str(x))


def badge(text, kind='gray'):
    return f'<span class="badge b-{kind}">{esc(text)}</span>'


def head(n, title, lead=None, help=None):
    st.markdown(f'<div class="crumb">Step {n} of 8</div>', unsafe_allow_html=True)
    st.title(title, help=help, anchor=False)
    if lead:
        st.markdown(f'<div class="lead">{lead}</div>', unsafe_allow_html=True)


def card_head(num, title, tag=None, help=None, desc=None):
    tags = {'required': 'info', 'optional': 'gray'}
    st.markdown(f'<div class="ch"><span class="num">{esc(num)}</span><span class="ttl">{esc(title)}</span><span class="sp"></span>'
                + (badge(tag, tags.get(tag, 'gray')) if tag else '') + '</div>', unsafe_allow_html=True, help=help)
    if desc:
        st.markdown(f'<div class="desc">{desc}</div>', unsafe_allow_html=True)


def file_row(name, size, state='read'):
    kind = {'read': 'ok', 'error': 'fail'}.get(state, 'gray')
    st.markdown(f'<div class="file">{badge("✓ " + state if state == "read" else state, kind)}<span class="nm">{esc(name)}</span>'
                f'<span class="sz">{(f"{size / 1e6:.1f} MB" if size >= 1e5 else f"{size / 1e3:.0f} kB")}</span></div>', unsafe_allow_html=True)


def table(header, rows, mono=()):
    th = ''.join(f'<th>{esc(h)}</th>' for h in header)
    tr = ''.join('<tr>' + ''.join(f'<td class="{"mono" if i in mono else ""}">{c}</td>' for i, c in enumerate(r)) + '</tr>' for r in rows)
    st.markdown(f'<table class="t"><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>', unsafe_allow_html=True)


def chips(values):
    st.markdown('<div class="chips">' + ''.join(f'<span class="chip">{esc(v)}</span>' for v in values) + '</div>', unsafe_allow_html=True)


def nav(steps, current, states, counts=None):
    """sidebar steps: numbered circles (green done, amber needs a decision, blue current). Returns the step clicked or None."""
    counts = counts or {}
    hit = None
    for i, s_ in enumerate(steps, 1):
        stt = 'on' if s_ == current else states.get(s_, 'todo')
        lab = STEP_TITLES[i - 1] + (f'  ·  {counts[s_]}' if counts.get(s_) else '')
        if st.button(lab, key=f'nav_{i}_{stt}', width='stretch'):
            hit = s_
    return hit


def foot(note, next_label=None, key='foot', disabled=False, help=None):
    """bottom bar of a page: note on the left, primary Next button on the right. Returns True when clicked."""
    with st.container(key=key):
        a, b = st.columns([3, 1], vertical_alignment='center')
        a.markdown(f'<div class="footnote">{note}</div>', unsafe_allow_html=True)
        if next_label:
            return b.button(next_label, type='primary', width='stretch', disabled=disabled, key=key + '_btn', help=help)
    return False
