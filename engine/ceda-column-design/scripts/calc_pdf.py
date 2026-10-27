"""Calculation sheets (PDF, CEDA header/footer) – one page per mark per story band (v7 format agreed with CEDA)."""
import os, re, math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Rectangle, Circle
from matplotlib.patches import Rectangle as _R
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

HERE = os.path.dirname(os.path.abspath(__file__))
plt.rcParams.update({'font.family': ['DejaVu Sans', 'Loma', 'Garuda', 'Norasi'], 'font.size': 7})
INK, ACC, RED, GRY = '#1d232b', '#1f4e79', '#b3261e', '#9aa4ae'


def short(cb):
    return str(cb).replace('UU_A_', 'B:').replace('U_A_', '').replace(' ', '')[:30]


def page(pdf, P, mark, labels, band, pack, sec, ties_txt, logo):
    """pack: list of dict(label, story, dwg, S, rows(P,M2,M3), mg, dc) for every column-story of the band."""
    # governing column-story
    gov = max(pack, key=lambda q: q['dcmax'])
    S, mg = gov['S'], gov['mg']
    Pk = np.concatenate([q['rows']['P'] for q in pack]) / 1000
    Mx = np.concatenate([q['mg']['x']['Md'] for q in pack]) / 1000
    My = np.concatenate([q['mg']['y']['Md'] for q in pack]) / 1000
    DC = np.concatenate([q['dc'] for q in pack])
    gi = int(np.argmax(DC))
    colr = np.where(DC > 1, RED, '#5b8fbf')
    fig = plt.figure(figsize=(8.27, 11.69))
    b, h = sec['b'], sec['h']
    rho = S.As / S.Ag * 100
    fig.text(0.06, 0.965, 'RC COLUMN DESIGN  —  BIAXIAL INTERACTION (STRAIN COMPATIBILITY)', fontsize=11, weight='bold', color=ACC)
    fig.text(0.06, 0.948, f"Column mark {mark}   |   Section {b*10:.0f} x {h*10:.0f} mm   |   Band {band[0]}→{band[1]}   |   "
             f"f'c = {sec['fc']} ksc   fy = {sec['fy']} ksc", fontsize=8.5)
    fig.text(0.06, 0.935, 'กฎกระทรวง 2566 ข้อ 7 (combos), ข้อ 8 (φ 0.70 tied/0.75 spiral, 0.90); φ transition ACI 318-19 21.2.2; '
             'φPn,max = 0.80φPo; Cm = 1', fontsize=6.3, color='#555')
    fig.add_artist(plt.Line2D([0.06, 0.94], [0.93, 0.93], color=ACC, lw=1.2))
    # section sketch
    ax = fig.add_axes([0.04, 0.70, 0.15, 0.215])
    if S.shape == 'circ':
        ax.add_patch(Circle((b / 2, b / 2), b / 2, fill=False, lw=1.2, color=INK))
    else:
        ax.add_patch(Rectangle((0, 0), b, h, fill=False, lw=1.2, color=INK))
    xs = S.bx + b / 2; ys = S.by + h / 2
    rr = math.sqrt(S.bA[0] / math.pi)
    for x, y in zip(xs, ys):
        ax.add_patch(Circle((x, y), rr, color=INK))
    ax.set_xlim(-8, b + 8); ax.set_ylim(-28, h + 4); ax.set_aspect('equal'); ax.axis('off')
    ax.text(b / 2, -4, sec['bars'].split(' ')[0], fontsize=7.5, weight='bold', ha='center', va='top')
    ax.text(b / 2, -17, f"{', '.join(labels)[:40]}", fontsize=5.5, color='#666', ha='center', va='top')
    ox, oy = mg['x'], mg['y']
    dmax = max(float(np.max(q['mg']['y']['delta'])) for q in pack)
    n14 = sum(int(np.sum((q['mg']['x']['delta'] > 1.4) | (q['mg']['y']['delta'] > 1.4))) for q in pack)
    lines = [
        ('Ast / ρ', f'{S.As:.1f} cm² / {rho:.2f}% (1–6%)', 1 <= rho <= 6),
        ('φPn,max = 0.80·0.70·Po', f'{S.phiPnmax/1000:,.0f} t', None),
        ('Lu / k (governing)', f"{gov['Lu']/100:.2f} m / {gov['k']}", None),
        ('kLu/r (x | y)', f"{ox['slr']:.1f} | {oy['slr']:.1f}  lim 22 → {'S' if ox['slender'] else 'NS'} | {'S' if oy['slender'] else 'NS'}", None),
        ('βd', f"{gov['betad']:.3f}", None),
        ('0.75Pc (x | y)', f"{0.75*ox['Pc']/1000:,.0f} | {0.75*oy['Pc']/1000:,.0f} t", None),
        ('δ max / n(δ>1.4)', f'{dmax:.2f} / {n14} of {len(DC)} (6.2.5.3)', n14 == 0),
        ('Bars', sec['bars'], None),
        ('Ties', ties_txt, None),
        ('Shear D/C max', f"{sec['shear']:.2f}", sec['shear'] <= 1),
        ('Combos checked', f'{len(DC)}', None),
        ('MAX D/C (radial)', f'{DC[gi]:.3f}', DC[gi] <= 1.0),
    ]
    y0 = 0.905
    for k_, v_, ok in lines:
        fig.text(0.215, y0, k_, fontsize=6.3, color='#444')
        fig.text(0.37, y0, v_ + ('' if ok is None else ('  OK' if ok else '  NG')), fontsize=6.3,
                 color=INK if ok is None else (ACC if ok else RED), weight='bold' if ok is not None else 'normal')
        y0 -= 0.0185
    # 3D surface
    a3 = fig.add_axes([0.55, 0.665, 0.37, 0.24], projection='3d')
    V = S.hull.points * S._scale()
    tris = [[(V[i, 1] / 1000, V[i, 2] / 1000, V[i, 0] / 1000) for i in sim] for sim in S.hull.simplices]
    a3.add_collection3d(Poly3DCollection(tris, facecolor='#9fb9d6', edgecolor='none', alpha=0.22))
    a3.scatter(Mx, My, Pk, s=2.5, c=colr, depthshade=False)
    a3.scatter([Mx[gi]], [My[gi]], [Pk[gi]], s=35, marker='x', color=RED)
    mx_, my_ = np.abs(V[:, 1]).max() / 1000, np.abs(V[:, 2]).max() / 1000
    a3.set_xlim(-mx_, mx_); a3.set_ylim(-my_, my_); a3.set_zlim(V[:, 0].min() / 1000, V[:, 0].max() / 1000 * 1.05)
    a3.set_xlabel('φMnx (t-m)', fontsize=5.5, labelpad=-5); a3.set_ylabel('φMny (t-m)', fontsize=5.5, labelpad=-5)
    a3.set_zlabel('φPn (t)', fontsize=5.5, labelpad=-6); a3.tick_params(labelsize=4.5, pad=-2); a3.view_init(elev=18, azim=-55)
    a3.set_title(f'Interaction surface – {len(DC)} combos (× max D/C)', fontsize=6.5, pad=0)
    for i, (axis, Md, lab) in enumerate((('x', Mx, 'φMnx (t-m)'), ('y', My, 'φMny (t-m)'))):
        a = fig.add_axes([0.115 + i * 0.455, 0.43, 0.35, 0.22])
        u = S.uniaxial(axis)
        a.plot(u[:, 1] / 1000, u[:, 0] / 1000, color=ACC, lw=1.3, label='uniaxial capacity')
        ok = DC <= 1
        a.scatter(np.abs(Md[ok]), Pk[ok], s=4, color='#5b8fbf', alpha=.6, lw=0, label='combo (D/C ≤ 1)')
        if (~ok).any():
            a.scatter(np.abs(Md[~ok]), Pk[~ok], s=7, color=RED, lw=0, label='combo (D/C > 1)')
        a.set_xlabel(lab); a.set_ylabel('φPn (t)'); a.grid(alpha=.3, lw=.4); a.axhline(0, color='k', lw=.5)
        a.set_title(f'P–M{axis} (uniaxial view, magnified moments)', fontsize=7.5)
        if i == 0:
            a.legend(fontsize=5.5, loc='upper right')
    fig.text(0.115, 0.383, 'Note: uniaxial curves are an overview. Pass/fail is by the biaxial radial D/C.', fontsize=6, color='#666', style='italic')
    a = fig.add_axes([0.115, 0.10, 0.33, 0.26])
    Pg = Pk[gi] * 1000
    C = S.contour(min(Pg, S.phiPnmax * 0.9999))
    if len(C):
        a.plot(C[:, 0] / 1000, C[:, 1] / 1000, color=ACC, lw=1.2, label=f'capacity at P = {Pg/1000:,.0f} t')
    sel = np.abs(Pk * 1000 - Pg) <= 0.10 * max(abs(Pg), 1)
    a.scatter(np.abs(Mx[sel]), np.abs(My[sel]), s=6, c=colr[sel], lw=0, label='combos within ±10% P')
    a.scatter([abs(Mx[gi])], [abs(My[gi])], s=30, marker='x', color=RED, label='governing combo')
    a.set_xlabel('Mux (t-m)'); a.set_ylabel('Muy (t-m)'); a.grid(alpha=.3, lw=.4); a.set_xlim(0, None); a.set_ylim(0, None)
    a.set_title('Mx–My contour at governing Pu', fontsize=7.5); a.legend(fontsize=5.5, loc='upper right')
    # max per story/label table
    tab = []
    for q in sorted(pack, key=lambda q: -q['dcmax'])[:12]:
        i = int(np.argmax(q['dc']))
        tab.append([q['story'], f"{q['dwg'][0]}→{q['dwg'][1]}", q['label'], short(q['meta'][i]['combo']),
                    f"{q['rows']['P'][i]/1000:,.0f}", f"{q['mg']['x']['Md'][i]/1000:.1f}", f"{q['mg']['y']['Md'][i]/1000:.1f}",
                    f"{q['mg']['y']['delta'][i]:.2f}", f"{q['dc'][i]:.3f}"])
    hdr = ['ETABS\nstory', 'Dwg level\n(bot→top)', 'Label', 'Combo', 'Pu\n(t)', 'Mux*\n(t-m)', 'Muy*\n(t-m)', 'δy', 'D/C']
    ta = fig.add_axes([0.48, 0.10, 0.46, 0.26]); ta.axis('off')
    t = ta.table(cellText=tab, colLabels=hdr, loc='upper center', cellLoc='center', colWidths=[.08, .12, .07, .31, .08, .08, .08, .06, .07])
    t.auto_set_font_size(False); t.set_fontsize(5.3); t.scale(1, 1.45)
    for (i, j), c in t.get_celld().items():
        c.set_linewidth(.3)
        if i == 0:
            c.set_facecolor('#eef1f4'); c.set_text_props(weight='bold')
        elif i == 1:
            c.set_facecolor('#fdf0d5')
        if i > 0 and j == 8 and float(c.get_text().get_text()) > 1:
            c.set_text_props(color=RED, weight='bold')
    ta.set_title('Max D/C per column-story (shaded = governing)', fontsize=7.5)
    fig.text(0.48, 0.085, '* Mu = sign(M)·max(|M|, M2,min)·δ when slender; M2,min = Pu(1.5 + 0.03h) cm', fontsize=5.8, color='#666')
    fig.text(0.48, 0.072, 'ETABS story = column below that level; drawing level = column from that level upward', fontsize=5.6, color='#666')
    fig.add_artist(plt.Line2D([0.06, 0.94], [0.06, 0.06], color=ACC, lw=.8))
    acc = (P.get('_accept') or {}).get((str(gov.get('label')), str(gov.get('story'))))
    verdict = 'O.K.' if DC[gi] <= 1 else (f'OVERLOAD ACCEPTED BY THE ENGINEER (≤ {acc:.2f})' if acc and DC[gi] <= acc + 1e-9 else 'NOT O.K.')
    fig.text(0.06, 0.045, f'RESULT (D/C basis): max D/C = {DC[gi]:.3f}  →  {verdict}', fontsize=9, weight='bold',
             color=ACC if verdict == 'O.K.' else ('#b26b00' if verdict.startswith('OVERLOAD') else RED))
    extra = f'  |  ρ = {rho:.2f}% > 6% – engineer approval' if rho > 6 else ''
    accd = [(P.get('_accept_delta') or {}).get((str(q.get('label')), str(q.get('story')))) for q in pack]
    acc_txt = ' – accepted by the engineer (δ ≤ %.2f)' % max(a for a in accd if a) if any(accd) else ' – engineer review'
    note = (f'Note: δ > 1.4 in {n14} of {len(DC)} combos (ACI 6.2.5.3){acc_txt}{extra}' if n14 else
            (f'Note:{extra[3:]}' if extra else 'Slenderness: δ ≤ 1.4 OK (ACI 6.2.5.3)'))
    fig.text(0.06, 0.03, note, fontsize=6.2, color=RED if (n14 or rho > 6) else '#555')
    fig.text(0.94, 0.045, 'DRAFT – for check', fontsize=6.5, color='#999', ha='right')
    # remap and CEDA header/footer
    def Y(y): return 0.062 + (y - 0.02) * (0.845 / 0.955)
    for axx in fig.axes:
        p = axx.get_position(); axx.set_position([p.x0, Y(p.y0), p.width, p.height * 0.885])
    for tt in fig.texts:
        x_, y_ = tt.get_position(); tt.set_position((x_, Y(y_)))
    for ar in fig.artists + fig.lines:
        if isinstance(ar, plt.Line2D):
            ar.set_ydata([Y(v) for v in ar.get_ydata()])

    def box(x0, y0, x1, y1, txt='', fs=7, wt='normal', ha='center', lw=0.8):
        fig.add_artist(_R((x0, y0), x1 - x0, y1 - y0, transform=fig.transFigure, fill=False, lw=lw, color='k'))
        if txt:
            fig.text((x0 + x1) / 2 if ha == 'center' else x0 + 0.008, (y0 + y1) / 2, txt, fontsize=fs, weight=wt, ha=ha, va='center')
    L, R_ = 0.04, 0.96
    r1, r2, r3, r4 = 0.985, 0.962, 0.939, 0.916
    box(L, r3, 0.20, r1)
    if logo is not None:
        la = fig.add_axes([L + 0.005, r3 + 0.003, 0.15, r1 - r3 - 0.006]); la.imshow(logo); la.axis('off')
    box(0.20, r2, 0.30, r1, 'PROJECT', 8, 'bold'); box(0.20, r3, 0.30, r2, 'LOCATION', 8, 'bold')
    box(0.30, r2, 0.76, r1, P.get('name', ''), 7.2, 'bold', 'left'); box(0.30, r3, 0.76, r2, P.get('location', ''), 7.5, 'bold', 'left')
    box(0.76, r2, 0.85, r1, 'DATE', 7.5, 'bold'); box(0.85, r2, R_, r1, P.get('date', ''), 7.5)
    box(0.76, r3, 0.85, r2, 'JOB NO.', 7.5, 'bold'); box(0.85, r3, R_, r2, P.get('job', ''), 7.5)
    box(L, r4, 0.20, r3, 'BUILDING', 8, 'bold'); box(0.20, r4, 0.50, r3, P.get('building', ''), 8, 'bold')
    box(0.50, r4, 0.58, r3, 'TYPE', 8, 'bold'); box(0.58, r4, 0.76, r3, 'RC. COLUMN', 8, 'bold')
    box(0.76, r4, 0.85, r3, 'MEMBER', 7.5, 'bold'); box(0.85, r4, R_, r3, sec['page'], 8, 'bold')
    box(L, r4, R_, r1, lw=1.6)
    f1, f2, f3, f4 = 0.052, 0.038, 0.024, 0.010
    cb = P.get('calc_by', []) + [['', '']] * 2
    ap = P.get('approve_by', ['', ''])
    fig.text(L + 0.005, (f1 + f2) / 2, 'Calculated by :', fontsize=7, va='center')
    fig.text(0.19, (f1 + f2) / 2, cb[0][0], fontsize=7, va='center'); fig.text(0.47, (f1 + f2) / 2, cb[0][1], fontsize=7, va='center')
    fig.text(0.19, (f2 + f3) / 2, cb[1][0], fontsize=7, va='center'); fig.text(0.47, (f2 + f3) / 2, cb[1][1], fontsize=7, va='center')
    fig.text(L + 0.005, (f3 + f4) / 2, 'Approve by :', fontsize=7, va='center')
    fig.text(0.19, (f3 + f4) / 2, ap[0], fontsize=7, va='center'); fig.text(0.47, (f3 + f4) / 2, ap[1], fontsize=7, va='center')
    box(0.66, f4, 0.78, f1, 'Page No.', 7.5, 'bold'); box(0.78, f4, R_, f1, sec['page'], 9, 'bold')
    box(L, f4, R_, f1, lw=1.2); box(L, f4, R_, r1, lw=1.6)
    pdf.savefig(fig); plt.close(fig)


def build(path, project, pages):
    logo_p = next((p for p in (os.path.join(HERE, '..', 'assets', 'ceda_logo.jpeg'), os.path.join(HERE, 'assets', 'ceda_logo.jpeg'))
                   if os.path.exists(p)), '')
    logo = plt.imread(logo_p) if os.path.exists(logo_p) else None
    with PdfPages(path) as pdf:
        for pg in pages:
            page(pdf, project, pg['mark'], pg['labels'], pg['band'], pg['pack'], pg['sec'], pg['ties_txt'], logo)
