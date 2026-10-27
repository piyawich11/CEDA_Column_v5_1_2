"""Detailed, formula-driven calculation in the layout of the CEDA column Excel (Report / X / Y / load) plus a
rotated-NA biaxial check (XY_check) built from bars + concrete fibres with Excel formulas. One mark-band per workbook."""
import math
import numpy as np
from scipy.optimize import least_squares
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter as CL
from openpyxl.chart import ScatterChart, Reference, Series


def build(OUT, ctx):
    """ctx: S (Section), bars [(x,y,A) cm], db, rows [dict story,col,combo,P,Mx,My,Mxd,Myd,dx,dy], m dict(b,h,fc,fy,k,Lu,betad),
    H dict(project/header), title str, page str, tie_db, so_cm, s_cm, nset."""
    S, bars, db, rows, m, H = ctx['S'], ctx['bars'], ctx['db'], ctx['rows'], ctx['m'], ctx['H']
    for q in rows:
        q['dcT'] = S.dc(q['P'], q['Mxd'], q['Myd'])
    rows.sort(key=lambda q: -q['dcT'])
    F = 'Arial'
    f9 = Font(name=F, size=9); fb = Font(name=F, size=9, bold=True); fin = Font(name=F, size=9, color='000099')
    fgr = Font(name=F, size=9, color='666666', italic=True); fT = Font(name=F, size=11, bold=True)
    fR = Font(name=F, size=9, bold=True, color='B3261E'); fG = Font(name=F, size=9, bold=True, color='1F6F3F')
    HDR = PatternFill('solid', fgColor='E8EDF2'); PY = PatternFill('solid', fgColor='F2F2F2')
    thin = Side(style='thin', color='BFBFBF'); BOX = Border(left=thin, right=thin, top=thin, bottom=thin)


    def put(ws, ref, v, font=f9, fmt=None, fill=None):
        c = ws[ref]; c.value = v; c.font = font
        if fmt: c.number_format = fmt
        if fill: c.fill = fill
        return c


    def hdr(ws, row, col, titles, h=28):
        for j, t in enumerate(titles):
            c = ws.cell(row, col + j, t); c.font = fb; c.fill = HDR; c.border = BOX
            c.alignment = Alignment(wrap_text=True, horizontal='center', vertical='center')
        ws.row_dimensions[row].height = h


    wb = openpyxl.Workbook()
    # =====================================================================================  Bars
    wbars = wb.active; wbars.title = 'Bars'
    put(wbars, 'A1', f'BAR TABLE – {len(bars)}-DB{db}, true positions (origin at section corner). x along B ({m["b"]:.0f} cm), y along H ({m["h"]:.0f} cm)', fT)
    hdr(wbars, 3, 1, ['Bar', 'x (cm)', 'y (cm)', 'Ø (mm)', 'A (cm²)', 'x − B/2', 'y − H/2', 'A(x−B/2)²', 'A(y−H/2)²'])
    for i, (x, y, a) in enumerate(bars):
        rr = 4 + i
        wbars.cell(rr, 1, i + 1).font = f9
        wbars.cell(rr, 2, round(x, 4)).font = fin
        wbars.cell(rr, 3, round(y, 4)).font = fin
        wbars.cell(rr, 4, db).font = fin
        wbars.cell(rr, 5, f'=PI()*D{rr}^2/400').font = f9
        wbars.cell(rr, 6, f'=B{rr}-Report!$C$10/2').font = f9
        wbars.cell(rr, 7, f'=C{rr}-Report!$C$11/2').font = f9
        wbars.cell(rr, 8, f'=E{rr}*F{rr}^2').font = f9
        wbars.cell(rr, 9, f'=E{rr}*G{rr}^2').font = f9
    NB = len(bars); B0, B1 = 4, 3 + NB
    for col, w in zip('ABCDEFGHI', [6, 9, 9, 7, 9, 9, 9, 11, 12]):
        wbars.column_dimensions[col].width = w
    put(wbars, f'A{B1+2}', 'Ise,x = ΣA(y−H/2)² ; Ise,y = ΣA(x−B/2)²  (used in Report)', fgr)

    # =====================================================================================  Report
    wr = wb.create_sheet('Report', 0)
    wr.sheet_view.showGridLines = False
    put(wr, 'A1', 'PROJECT', fb); put(wr, 'C1', H['D1'], fb); put(wr, 'J1', 'DATE', fb); put(wr, 'K1', H['K1'])
    put(wr, 'A2', 'LOCATION', fb); put(wr, 'C2', H['D2'], fb); put(wr, 'J2', 'JOB NO.', fb); put(wr, 'K2', H['K2'])
    put(wr, 'A3', 'BUILDING', fb); put(wr, 'C3', str(H['C3']).strip(), fb); put(wr, 'F3', 'TYPE', fb); put(wr, 'G3', 'RC. COLUMN', fb)
    put(wr, 'I3', 'MEMBER', fb); put(wr, 'J3', ctx.get('page', ''), fb)
    put(wr, 'A4', ctx.get('title', ''), fT)

    put(wr, 'A6', 'Material Properties', fb)
    put(wr, 'A7', "Concrete f'c ="); put(wr, 'C7', m['fc'], fin); put(wr, 'D7', 'ksc')
    put(wr, 'E7', 'β1 ='); put(wr, 'F7', '=IF(C7<=280,0.85,MAX(0.65,0.85-0.05*(C7-280)/70))', fmt='0.000')
    put(wr, 'G7', 'Ec ='); put(wr, 'H7', '=15100*SQRT(C7)', fmt='#,##0'); put(wr, 'I7', 'ksc')
    put(wr, 'A8', 'Main steel fy ='); put(wr, 'C8', m['fy'], fin); put(wr, 'D8', 'ksc')
    put(wr, 'E8', 'Es ='); put(wr, 'F8', 2.04e6, fin, '#,##0'); put(wr, 'G8', 'εy ='); put(wr, 'H8', '=C8/F8', fmt='0.00000')
    put(wr, 'A9', 'φ (tied, compression) ='); put(wr, 'C9', 0.70, fin); put(wr, 'E9', 'α (Pn,max) ='); put(wr, 'F9', 0.80, fin)
    put(wr, 'G9', 'εcu ='); put(wr, 'H9', 0.003, fin)

    put(wr, 'A10', 'Input  B ='); put(wr, 'C10', m['b'], fin); put(wr, 'D10', 'cm')
    put(wr, 'E10', 'Ag ='); put(wr, 'F10', '=C10*C11', fmt='#,##0'); put(wr, 'G10', 'cm²')
    put(wr, 'A11', '          H ='); put(wr, 'C11', m['h'], fin); put(wr, 'D11', 'cm')
    put(wr, 'E11', 'Ast ='); put(wr, 'F11', f'=SUM(Bars!E{B0}:E{B1})', fmt='0.00'); put(wr, 'G11', 'cm²')
    put(wr, 'H11', 'ρ ='); put(wr, 'I11', '=F11/F10', fmt='0.00%'); put(wr, 'J11', '=IF(AND(I11>=0.01,I11<=0.06),"1–6% O.K.","CHECK")')
    put(wr, 'A12', 'No. of bars ='); put(wr, 'C12', f'=COUNT(Bars!A{B0}:A{B1})'); put(wr, 'D12', '=" DB"&Bars!D4')
    put(wr, 'E12', 'Po ='); put(wr, 'F12', '=0.85*C7*(F10-F11)+C8*F11', fmt='#,##0'); put(wr, 'G12', 'kg')
    put(wr, 'E13', 'φPn,max = α·φ·Po ='); put(wr, 'F13', '=F9*C9*F12', fmt='#,##0'); put(wr, 'G13', 'kg')

    put(wr, 'A15', 'Slenderness  (non-sway, ACI 318-19 6.2.5 / 6.6.4)', fb)
    hdr(wr, 16, 1, ['', 'X-axis (Mx, strong)', 'Y-axis (My, weak)', 'note'], 18)
    srows = [
        ('k', m['k'], m['k'], ctx.get('k_note', ''), True),
        ('Lu (m)', m['Lu'] / 100, m['Lu'] / 100, ctx.get('Lu_note', ''), True),
        ('r = 0.3·dim (cm)', '=0.3*C11', '=0.3*C10', 'ACI 6.2.5.2', False),
        ('kLu/r', '=B17*B18*100/B19', '=C17*C18*100/C19', '', False),
        ('limit = 34 − 12(M1/M2) ≤ 40', 22, 22, 'M1/M2 = +1 (single curvature, conservative)', True),
        ('slenderness effect?', '=IF(B20>B21,"YES","NO")', '=IF(C20>C21,"YES","NO")', '', False),
        ('Ig (cm⁴)', '=C10*C11^3/12', '=C11*C10^3/12', '', False),
        ('Ise (cm⁴)', f'=SUM(Bars!I{B0}:I{B1})', f'=SUM(Bars!H{B0}:H{B1})', 'from Bars (true positions)', False),
        ('βd', '=(1.4*(H9_DL+H9_SDL)+1.7*0.25*H9_LL)/(1.4*(H9_DL+H9_SDL)+1.7*H9_LL)', '=B25',
         'Rev.1: (1.4D + 0.25·1.7L)/(1.4D + 1.7L)', False),
        ('(EI)eff = (0.2EcIg+EsIse)/(1+βd)', '=(0.2*$H$7*B23+$F$8*B24)/(1+B25)', '=(0.2*$H$7*C23+$F$8*C24)/(1+C25)', 'ACI 6.6.4.4.4(a)', False),
        ('Pc = π²EI/(kLu)²  (kg)', '=PI()^2*B26/(B17*B18*100)^2', '=PI()^2*C26/(C17*C18*100)^2', 'no φ (D3)', False),
        ('0.75Pc (kg)', '=0.75*B27', '=0.75*C27', '', False),
        ('Cm', 1, 1, 'Cm = 1 always (agreed)', True),
    ]
    for i, (lab, vx, vy, note, inp) in enumerate(srows):
        rr = 17 + i
        put(wr, f'A{rr}', lab)
        put(wr, f'B{rr}', vx, fin if inp else f9, '#,##0.000' if i in (2, 3) else None)
        put(wr, f'C{rr}', vy, fin if inp else f9)
        put(wr, f'D{rr}', note, fgr)
    pass
    pass
    wr['B25'].value = float(m['betad']); wr['B25'].font = fin
    for rr in (23, 24, 26, 27, 28):
        for col in 'BC':
            wr[f'{col}{rr}'].number_format = '#,##0'
    wr['B25'].number_format = '0.000'; wr['C25'].number_format = '0.000'
    for rr in (19, 20):
        for col in 'BC':
            wr[f'{col}{rr}'].number_format = '0.00'

    put(wr, 'A31', 'Governing combination & moment magnifier', fb)
    g = rows[0]
    NL = len(rows)
    LG = f'load!$A$6:$Z${5+NL}'
    put(wr, 'A32', 'Governing row (max D/C) ='); put(wr, 'C32', '=MATCH(MAX(load!S6:S{0}),load!S6:S{0},0)'.format(5 + NL))
    put(wr, 'A33', 'Story / label / combo ='); put(wr, 'C33', '=INDEX(load!B6:B{0},C32)&" / "&INDEX(load!C6:C{0},C32)&" / "&INDEX(load!D6:D{0},C32)'.format(5 + NL))
    put(wr, 'A34', 'Pu ='); put(wr, 'C34', '=INDEX(load!E6:E{0},C32)'.format(5 + NL), fmt='#,##0'); put(wr, 'D34', 'kg')
    put(wr, 'A35', 'Mux (1st order) ='); put(wr, 'C35', '=INDEX(load!F6:F{0},C32)'.format(5 + NL), fmt='#,##0'); put(wr, 'D35', 'kg-m')
    put(wr, 'A36', 'Muy (1st order) ='); put(wr, 'C36', '=INDEX(load!G6:G{0},C32)'.format(5 + NL), fmt='#,##0'); put(wr, 'D36', 'kg-m')
    put(wr, 'A37', 'M2,min x / y = Pu(1.5+0.03h)/100 ='); put(wr, 'C37', '=C34*(1.5+0.03*C11)/100', fmt='#,##0')
    put(wr, 'D37', '=C34*(1.5+0.03*C10)/100', fmt='#,##0'); put(wr, 'E37', 'kg-m (used only if slender)', fgr)
    put(wr, 'A38', 'δx / δy ='); put(wr, 'C38', '=INDEX(load!J6:J{0},C32)'.format(5 + NL), fmt='0.000')
    put(wr, 'D38', '=INDEX(load!K6:K{0},C32)'.format(5 + NL), fmt='0.000')
    put(wr, 'A39', 'Mux, Muy design ='); put(wr, 'C39', '=INDEX(load!L6:L{0},C32)'.format(5 + NL), fmt='#,##0')
    put(wr, 'D39', '=INDEX(load!M6:M{0},C32)'.format(5 + NL), fmt='#,##0'); put(wr, 'E39', 'kg-m')

    put(wr, 'A41', 'Biaxial strength check (3D surface, radial D/C)', fb)
    put(wr, 'A42', 'D/C cap = Pu / φPn,max ='); put(wr, 'C42', '=C34/F13', fmt='0.000')
    put(wr, 'A43', 'D/C (3D surface, governing) ='); put(wr, 'C43', '=INDEX(load!S6:S{0},C32)'.format(5 + NL), fmt='0.000', font=fb)
    put(wr, 'D43', '=IF(C43<=1,"O.K.","NOT O.K.")', fb)
    put(wr, 'A44', 'Max D/C all combos ='); put(wr, 'C44', '=MAX(load!S6:S{0})'.format(5 + NL), fmt='0.000', font=fb)
    put(wr, 'A45', 'Independent check (XY_check sheet) ='); put(wr, 'C45', '=XY_check!C30', fmt='0.000'); put(wr, 'D45', '=XY_check!C29', fgr)
    put(wr, 'A46', 'Uniaxial X / Y diagrams: sheets X and Y (9 points, same layout as the CEDA Excel)', fgr)

    put(wr, 'A48', 'Tie (IMF minimum, ประกาศ มท. 2564 ข้อ 26 / มยผ. 1301/1302-61 5.2.7)', fb)
    put(wr, 'A49', 'Tie Ø ='); put(wr, 'C49', ctx.get('tie_db', 12), fin); put(wr, 'D49', 'mm')
    put(wr, 'A50', 'so ≤ min(8db, 24dt, B/2, 30) ='); put(wr, 'C50', '=MIN(8*Bars!D4/10,24*C49/10,C10/2,30)', fmt='0.0'); put(wr, 'D50', 'cm')
    put(wr, 'A51', 'lo ≥ max(Lu/6, H, 50) ='); put(wr, 'C51', '=MAX(B18*100/6,C11,50)', fmt='0'); put(wr, 'D51', 'cm')
    put(wr, 'A52', 'Use so / s ='); put(wr, 'C52', ctx.get('so_cm', 15), fin); put(wr, 'D52', ctx.get('s_cm', 30), fin)
    put(wr, 'E52', '=IF(AND(C52<=C50,D52<=2*C50),"O.K.","NOT O.K.")', fb)
    put(wr, 'A53', 'Sets per spacing (ACI 25.7.2.3, symmetric)'); put(wr, 'C53', f"{ctx.get('nset', '')} closed hoops")

    put(wr, 'A55', 'Calculated by :'); put(wr, 'C55', H.get('C52', '')); put(wr, 'F55', H.get('F52', ''))
    put(wr, 'C56', H.get('C53', '')); put(wr, 'F56', H.get('F53', ''))
    put(wr, 'A57', 'Approve by :'); put(wr, 'C57', H.get('C54', '')); put(wr, 'F57', H.get('F54', '')); put(wr, 'J57', 'DRAFT – for check', fgr)
    for col, w in zip('ABCDEFGHIJK', [30, 16, 16, 12, 16, 12, 10, 12, 10, 10, 12]):
        wr.column_dimensions[col].width = w


    # =====================================================================================  X / Y uniaxial (9 points, layered)
    def uniaxial_sheet(name, axis):
        ws = wb.create_sheet(name)
        ws.sheet_view.showGridLines = False
        dimW, dimD = ('Report!$C$10', 'Report!$C$11') if axis == 'X' else ('Report!$C$11', 'Report!$C$10')
        put(ws, 'A1', f'Interaction Diagram ({axis.lower()} - {axis.lower()} axis)   –   bending {"strong (depth along H)" if axis == "X" else "weak (depth along B)"}', fT)
        put(ws, 'A2', 'Layers = bars grouped by distance d from the compression face (true bundle positions). '
                      'Compression face at y = H (X) / x = B (Y).', fgr)
        # layers
        coord = [round(y if axis == 'X' else x, 4) for x, y, a in bars]
        Dv = m['h'] if axis == 'X' else m['b']
        dvals = sorted(set(round(Dv - c, 4) for c in coord))
        hdr(ws, 4, 1, ['Layer', 'd (cm)', 'No.', 'Ø (mm)', 'As (cm²)'])
        for i, d in enumerate(dvals):
            rr = 5 + i
            n = sum(1 for c in coord if abs(Dv - c - d) < 1e-6)
            ws.cell(rr, 1, i + 1).font = f9
            ws.cell(rr, 2, d).font = fin
            ws.cell(rr, 3, n).font = fin
            ws.cell(rr, 4, db).font = fin
            ws.cell(rr, 5, f'=C{rr}*PI()*D{rr}^2/400').font = f9
        L0, L1 = 5, 4 + len(dvals)
        put(ws, f'A{L1+1}', 'Σ'); put(ws, f'C{L1+1}', f'=SUM(C{L0}:C{L1})'); put(ws, f'E{L1+1}', f'=SUM(E{L0}:E{L1})', fmt='0.00')
        put(ws, f'A{L1+2}', 'check = Ast (Report)'); put(ws, f'E{L1+2}', f'=IF(ABS(E{L1+1}-Report!F11)<0.01,"O.K.","CHECK")')
        put(ws, 'G4', 'D (depth) ='); put(ws, 'H4', f'={dimD}'); put(ws, 'I4', 'cm')
        put(ws, 'G5', 'W (width) ='); put(ws, 'H5', f'={dimW}'); put(ws, 'I5', 'cm')
        put(ws, 'G6', 'd1 (extreme tension layer) ='); put(ws, 'H6', f'=MAX(B{L0}:B{L1})'); put(ws, 'I6', 'cm')
        # 9 points
        pts = [('Point 1', 'pure compression φPo (no α)', None),
               ('Point 2', 'c = D', '=H4'),
               ('Point 3', 'c = d1', '=H6'),
               ('Point 4', 'εs1 = −0.5εy', '=H6*Report!$H$9/(Report!$H$9+0.5*Report!$H$8)'),
               ('Point 5', 'εs1 = −εy (balanced)', '=H6*Report!$H$9/(Report!$H$9+1*Report!$H$8)'),
               ('Point 6', 'εs1 = −2εy', '=H6*Report!$H$9/(Report!$H$9+2*Report!$H$8)'),
               ('Point 7', 'εs1 = −2.5εy', '=H6*Report!$H$9/(Report!$H$9+2.5*Report!$H$8)'),
               ('Point 8', 'εs1 = −4εy', '=H6*Report!$H$9/(Report!$H$9+4*Report!$H$8)'),
               ('Point 9', 'pure tension 0.9·fy·Ast', None)]
        nL = len(dvals)
        top = L1 + 5
        summary = []
        col0 = 1
        rowp = top
        for k, (pn, desc, cform) in enumerate(pts):
            if cform is None:
                continue
            # block per point: header rows, then per-layer table
            put(ws, f'A{rowp}', f'at {pn}', fb); put(ws, f'C{rowp}', desc, fgr)
            put(ws, f'A{rowp+1}', 'c ='); put(ws, f'B{rowp+1}', cform, fmt='0.000'); put(ws, f'C{rowp+1}', 'cm')
            put(ws, f'A{rowp+2}', 'a = β1c ≤ D ='); put(ws, f'B{rowp+2}', f'=MIN(Report!$F$7*B{rowp+1},H4)', fmt='0.000'); put(ws, f'C{rowp+2}', 'cm')
            put(ws, f'A{rowp+3}', 'Cc = 0.85f\'c·W·a ='); put(ws, f'B{rowp+3}', f'=0.85*Report!$C$7*H5*B{rowp+2}', fmt='#,##0'); put(ws, f'C{rowp+3}', 'kg')
            put(ws, f'D{rowp+1}', 'εt ='); put(ws, f'E{rowp+1}', f'=MAX(0,-MIN(G{rowp+6}:G{rowp+5+nL}))', fmt='0.00000')
            put(ws, f'D{rowp+2}', 'φ ='); put(ws, f'E{rowp+2}', f'=IF(E{rowp+1}<=Report!$H$8,Report!$C$9,IF(E{rowp+1}>=Report!$H$8+0.003,0.9,'
                                                                f'Report!$C$9+(0.9-Report!$C$9)*(E{rowp+1}-Report!$H$8)/0.003))', fmt='0.000')
            put(ws, f'F{rowp+1}', 'Pn ='); put(ws, f'G{rowp+1}', f'=B{rowp+3}+SUM(J{rowp+6}:J{rowp+5+nL})', fmt='#,##0'); put(ws, f'H{rowp+1}', 'kg')
            put(ws, f'F{rowp+2}', 'Mn ='); put(ws, f'G{rowp+2}', f'=(B{rowp+3}*(H4/2-B{rowp+2}/2)+SUM(L{rowp+6}:L{rowp+5+nL}))/100', fmt='#,##0'); put(ws, f'H{rowp+2}', 'kg-m')
            put(ws, f'I{rowp+1}', 'φPn ='); put(ws, f'J{rowp+1}', f'=E{rowp+2}*G{rowp+1}', fmt='#,##0', font=fb); put(ws, f'K{rowp+1}', 'kg')
            put(ws, f'I{rowp+2}', 'φMn ='); put(ws, f'J{rowp+2}', f'=E{rowp+2}*G{rowp+2}', fmt='#,##0', font=fb); put(ws, f'K{rowp+2}', 'kg-m')
            hdr(ws, rowp + 5, 1, ['Layer', 'd (cm)', 'As (cm²)', '', '', '', 'εs', 'fs (ksc)', 'displaced 0.85f\'c', 'Fs (kg)', 'arm D/2−d (cm)', 'Fs·arm (kg-cm)'], 30)
            for i in range(nL):
                rr = rowp + 6 + i
                lr = L0 + i
                ws.cell(rr, 1, f'=A{lr}').font = f9
                ws.cell(rr, 2, f'=B{lr}').font = f9
                ws.cell(rr, 3, f'=E{lr}').font = f9
                ws.cell(rr, 7, f'=Report!$H$9*($B${rowp+1}-B{rr})/$B${rowp+1}').font = f9
                ws.cell(rr, 8, f'=MAX(-Report!$C$8,MIN(Report!$C$8,G{rr}*Report!$F$8))').font = f9
                ws.cell(rr, 9, f'=IF(B{rr}<=$B${rowp+2},0.85*Report!$C$7,0)').font = f9
                ws.cell(rr, 10, f'=(H{rr}-I{rr})*C{rr}').font = f9
                ws.cell(rr, 11, f'=$H$4/2-B{rr}').font = f9
                ws.cell(rr, 12, f'=J{rr}*K{rr}').font = f9
                ws.cell(rr, 7).number_format = '0.00000'
                for cc in (8, 10, 12): ws.cell(rr, cc).number_format = '#,##0'
            summary.append((pn, f'J{rowp+1}', f'J{rowp+2}'))
            rowp += 8 + nL
        # co-ordinates table (like CEDA Excel rows 79-100)
        put(ws, 'N4', f'Co-ordinates of Diagram {axis.lower()} - {axis.lower()} axis', fb)
        hdr(ws, 5, 14, ['Point', 'φPn (kg)', f'φMn{axis.lower()} (kg-m)'], 18)
        coords = [('Point 1', '=Report!$C$9*Report!$F$12', 0)] + [(p, f'={a}', f'={b}') for p, a, b in summary] + \
                 [('Point 9', '=-0.9*Report!$C$8*Report!$F$11', 0)]
        for i, (p, a, b) in enumerate(coords):
            rr = 6 + i
            put(ws, f'N{rr}', p); put(ws, f'O{rr}', a, fmt='#,##0'); put(ws, f'P{rr}', b, fmt='#,##0')
        put(ws, 'N16', 'φPn,max (cap)'); put(ws, 'O16', '=Report!$F$13', fmt='#,##0')
        put(ws, 'N17', 'Note: points 2–8 use the strain-based φ of each point (ACI 21.2.2).', fgr)
        # demand (max per load) for chart
        put(ws, 'N19', 'Demand (all combos, design moments)', fb)
        hdr(ws, 20, 14, ['Pu (kg)', f'Mu{axis.lower()} (kg-m)'], 18)
        for i in range(NL):
            rr = 21 + i
            ws.cell(rr, 14, f'=load!E{6+i}').font = f9
            ws.cell(rr, 15, f'=ABS(load!{"L" if axis == "X" else "M"}{6+i})').font = f9
        ch = ScatterChart(); ch.title = f'P–M{axis.lower()} (9-point diagram)'; ch.style = 13
        ch.x_axis.title = f'φMn{axis.lower()} (kg-m)'; ch.y_axis.title = 'φPn (kg)'
        s1 = Series(Reference(ws, min_col=15, min_row=6, max_row=14), Reference(ws, min_col=16, min_row=6, max_row=14), title='capacity')
        s1.marker.symbol = 'circle'
        ch.series.append(s1)
        s2 = Series(Reference(ws, min_col=14, min_row=21, max_row=20 + NL), Reference(ws, min_col=15, min_row=21, max_row=20 + NL), title='demand')
        s2.marker.symbol = 'dot'; s2.graphicalProperties.line.noFill = True
        ch.series.append(s2)
        # note: openpyxl Series(values, xvalues): swap so x = M
        ch.series[0] = Series(Reference(ws, min_col=15, min_row=6, max_row=14), Reference(ws, min_col=16, min_row=6, max_row=14), title='capacity')
        ch.series[1] = Series(Reference(ws, min_col=14, min_row=21, max_row=20 + NL), Reference(ws, min_col=15, min_row=21, max_row=20 + NL), title='demand')
        ch.series[1].graphicalProperties.line.noFill = True; ch.series[1].marker.symbol = 'dot'
        ch.height, ch.width = 9, 14
        ws.add_chart(ch, 'R4')
        for col, w in zip('ABCDEFGHIJKLMNOP', [22, 11, 9, 7, 10, 7, 10, 10, 10, 11, 11, 12, 2, 12, 13, 13]):
            ws.column_dimensions[col].width = w
        return ws


    uniaxial_sheet('X', 'X')
    uniaxial_sheet('Y', 'Y')

    # =====================================================================================  load
    wl = wb.create_sheet('load')
    put(wl, 'A1', 'Element forces – ' + ctx.get('title', '') + '  –  design moments and D/C', fT)
    put(wl, 'A2', 'Blue = ETABS values (kg, kg-m). Black = formulas. Grey S = radial D/C from the 3D surface (Python); T–V = capacity point on the same ray.', fgr)
    put(wl, 'A3', 'δ = Cm/(1−Pu/0.75Pc) ≥ 1 when slender (Report row 22); Mu design = sign(M)·max(|M|, M2,min)·δ; non-slender: Mu design = M.', fgr)
    hdr(wl, 5, 1, ['No', 'Story', 'Label', 'Combo', 'Pu (kg)', 'Mx (kg-m)', 'My (kg-m)', 'M2,min x', 'M2,min y', 'δx', 'δy',
                   'Mux design', 'Muy design', 'Pu/φPn,max', '', '', '', '', 'D/C (3D)', 'φPn on ray', 'φMnx on ray', 'φMny on ray', 'OK?'], 30)
    for i, q in enumerate(rows):
        rr = 6 + i
        vals = [i + 1, str(q['story']), q['col'], q['combo'], round(q['P'], 1), round(q['Mx'], 1), round(q['My'], 1)]
        for j, v in enumerate(vals):
            wl.cell(rr, 1 + j, v).font = fin if j >= 1 else f9
        wl.cell(rr, 8, f'=IF(Report!$B$22="YES",E{rr}*(1.5+0.03*Report!$C$11)/100,0)').font = f9
        wl.cell(rr, 9, f'=IF(Report!$C$22="YES",E{rr}*(1.5+0.03*Report!$C$10)/100,0)').font = f9
        wl.cell(rr, 10, f'=IF(Report!$B$22="YES",IF(E{rr}>=Report!$B$28,"NG",MAX(1,Report!$B$29/(1-E{rr}/Report!$B$28))),1)').font = f9
        wl.cell(rr, 11, f'=IF(Report!$C$22="YES",IF(E{rr}>=Report!$C$28,"NG",MAX(1,Report!$C$29/(1-E{rr}/Report!$C$28))),1)').font = f9
        wl.cell(rr, 12, f'=IF(F{rr}<0,-1,1)*MAX(ABS(F{rr}),H{rr})*J{rr}').font = f9
        wl.cell(rr, 13, f'=IF(G{rr}<0,-1,1)*MAX(ABS(G{rr}),I{rr})*K{rr}').font = f9
        wl.cell(rr, 14, f'=E{rr}/Report!$F$13').font = f9
        d = q['dcT']
        for j, v in enumerate((d, q['P'] / d, q['Mxd'] / d, q['Myd'] / d)):
            c = wl.cell(rr, 19 + j, round(float(v), 4 if j == 0 else 0)); c.font = fgr; c.fill = PY
        wl.cell(rr, 23, f'=IF(S{rr}<=1,"O.K.","NG")').font = f9
        for cc in (5, 6, 7, 8, 9, 12, 13, 20, 21, 22): wl.cell(rr, cc).number_format = '#,##0'
        for cc in (10, 11, 14, 19): wl.cell(rr, cc).number_format = '0.000'
    for col, w in zip('ABCDEFGHIJKLMNOPQRSTUVW', [5, 8, 7, 34, 11, 10, 10, 10, 10, 7, 7, 11, 11, 10, 2, 2, 2, 2, 9, 11, 11, 11, 6]):
        wl.column_dimensions[col].width = w
    wl.freeze_panes = 'E6'

    # =====================================================================================  XY_check (rotated NA, fibres)
    wx = wb.create_sheet('XY_check')
    wx.sheet_view.showGridLines = False


    def capacity_on_ray(P, Mx, My):
        """find θ, c with (φPn, φMnx, φMny) ∥ (P, Mx, My) on the uncapped surface."""
        v = np.array([P, Mx, My]); s = S._scale()
        vn = v / s; vn /= np.linalg.norm(vn)
        best = None
        for th0 in np.linspace(0, 2 * np.pi, 24, endpoint=False):
            for c0 in (0.3, 1.0, 3.0):
                def fun(z):
                    th, lc = z
                    Pn, Mnx, Mny, ph = S.point(th, math.exp(lc) * np.hypot(S.b, S.h))
                    w = np.array([ph * Pn, ph * Mnx, ph * Mny]) / s
                    nw = np.linalg.norm(w)
                    return (w / nw - vn) * 10 if nw > 0 else np.ones(3)
                sol = least_squares(fun, [th0, math.log(c0)], bounds=([-10, -6], [20, 3]))
                if best is None or sol.cost < best.cost:
                    best = sol
        th, lc = best.x
        c = math.exp(lc) * np.hypot(S.b, S.h)
        Pn, Mnx, Mny, ph = S.point(th, c)
        return th % (2 * np.pi), c, ph * Pn, ph * Mnx, ph * Mny, best.cost


    # choose the governing moment-driven combo (largest radial D/C on the UNCAPPED surface)
    # band is cap-governed; demonstrate the rotated-NA check on the combos where moment matters most
    sc_ = S._scale()
    cand = sorted(rows, key=lambda q: -(abs(q['Mxd']) / sc_[1] + abs(q['Myd']) / sc_[2]))[:6]
    best_q, best_unc, fallback = None, -1, None
    for q in cand:
        th, c, fP, fMx, fMy, cost = capacity_on_ray(q['P'], q['Mxd'], q['Myd'])
        unc = q['P'] / fP if abs(fP) > 1 else 0
        if fallback is None or cost < fallback[0]:
            fallback = (cost, q, (th, c, fP, fMx, fMy))
        if cost < 1e-4 and unc > best_unc:
            best_unc, best_q, best_sol = unc, q, (th, c, fP, fMx, fMy)
    if best_q is None:                       # no exact ray solution: use the closest (ray check row shows the mismatch)
        _, best_q, best_sol = fallback
    q = best_q; th, c, fP, fMx, fMy = best_sol
    put(wx, 'A1', 'BIAXIAL CHECK – rotated neutral axis, strain compatibility by Excel formulas (bars + concrete fibres)', fT)
    put(wx, 'A2', 'Change θ and c (blue) to trace any point. Prefilled θ, c put the capacity point on the ray of the selected combo.', fgr)
    put(wx, 'A4', 'Selected combo:'); put(wx, 'C4', f'{q["story"]} / {q["col"]} / {q["combo"]}', fb)
    put(wx, 'A5', 'Pu (kg) ='); put(wx, 'C5', round(q['P'], 1), fin, '#,##0')
    put(wx, 'A6', 'Mux design (kg-m) ='); put(wx, 'C6', round(q['Mxd'], 1), fin, '#,##0')
    put(wx, 'A7', 'Muy design (kg-m) ='); put(wx, 'C7', round(q['Myd'], 1), fin, '#,##0')
    put(wx, 'A9', 'θ NA direction (deg) ='); put(wx, 'C9', round(math.degrees(th), 6), fin, '0.0000')
    put(wx, 'D9', '0° = compression at +x (B side), 90° = compression at +y (H side)', fgr)
    put(wx, 'A10', 'c (cm, ⊥ NA) ='); put(wx, 'C10', round(c, 6), fin, '0.0000')
    put(wx, 'A11', 'cos θ / sin θ ='); put(wx, 'C11', '=COS(RADIANS(C9))', fmt='0.00000'); put(wx, 'D11', '=SIN(RADIANS(C9))', fmt='0.00000')
    put(wx, 'A12', 'u_max = (B/2)|cosθ| + (H/2)|sinθ| ='); put(wx, 'C12', '=Report!C10/2*ABS(C11)+Report!C11/2*ABS(D11)', fmt='0.000')
    put(wx, 'A13', 'a = β1·c ='); put(wx, 'C13', '=Report!F7*C10', fmt='0.000')
    put(wx, 'A15', 'Concrete C = Σ fibres ='); put(wx, 'C15', '=SUM(K41:K{0})'.format(40 + 30 * 133), fmt='#,##0'); put(wx, 'D15', 'kg')
    put(wx, 'A16', 'Steel F = Σ bars ='); put(wx, 'C16', f'=SUM(N41:N{40+NB})', fmt='#,##0'); put(wx, 'D16', 'kg')
    put(wx, 'A17', 'Pn = C + F ='); put(wx, 'C17', '=C15+C16', fmt='#,##0'); put(wx, 'D17', 'kg')
    put(wx, 'A18', 'Mnx = Σ(C·y) + Σ(F·y) ='); put(wx, 'C18', '=(SUM(L41:L{0})+SUM(O41:O{1}))/100'.format(40 + 30 * 133, 40 + NB), fmt='#,##0'); put(wx, 'D18', 'kg-m')
    put(wx, 'A19', 'Mny = −[Σ(C·x) + Σ(F·x)] ='); put(wx, 'C19', '=-(SUM(M41:M{0})+SUM(P41:P{1}))/100'.format(40 + 30 * 133, 40 + NB), fmt='#,##0'); put(wx, 'D19', 'kg-m')
    put(wx, 'A20', 'εt = max(0, −min εs) ='); put(wx, 'C20', f'=MAX(0,-MIN(R41:R{40+NB}))', fmt='0.00000')
    put(wx, 'A21', 'φ ='); put(wx, 'C21', '=IF(C20<=Report!H8,Report!C9,IF(C20>=Report!H8+0.003,0.9,Report!C9+(0.9-Report!C9)*(C20-Report!H8)/0.003))', fmt='0.000')
    put(wx, 'A22', 'φPn / φMnx / φMny ='); put(wx, 'C22', '=C21*C17', fmt='#,##0', font=fb); put(wx, 'D22', '=C21*C18', fmt='#,##0', font=fb)
    put(wx, 'E22', '=C21*C19', fmt='#,##0', font=fb)
    put(wx, 'A24', 'Ray check: φPn/Pu, φMnx/Mux, φMny/Muy (equal = on the ray)'); put(wx, 'C24', '=C22/C5', fmt='0.0000')
    put(wx, 'D24', '=IF(C6=0,"-",D22/C6)', fmt='0.0000'); put(wx, 'E24', '=IF(C7=0,"-",E22/C7)', fmt='0.0000')
    put(wx, 'A26', 'D/C uncapped surface = Pu/φPn ='); put(wx, 'C26', '=C5/C22', fmt='0.0000')
    put(wx, 'A27', 'D/C cap = Pu/φPn,max ='); put(wx, 'C27', '=C5/Report!F13', fmt='0.0000')
    put(wx, 'A28', 'D/C = max(uncapped, cap)'); put(wx, 'C28', '=MAX(C26,C27)', fmt='0.0000', font=fb)
    put(wx, 'A29', 'Engine D/C (load sheet, same combo) ='); put(wx, 'C29', round(float(q['dcT']), 4), fgr, '0.0000', fill=PY)
    put(wx, 'A30', 'Max D/C of the band (load sheet) ='); put(wx, 'C30', '=MAX(load!S6:S{0})'.format(5 + NL), fmt='0.0000', font=fb)
    put(wx, 'D28', 'capped surface = uncapped ∩ (P ≤ φPn,max) → radial D/C of the intersection = max of the two', fgr)
    put(wx, 'D29', 'difference vs engine: hull linear interpolation between surface points (small, conservative)', fgr)
    # fibre + bar tables
    hdr(wx, 40, 1, ['Bar', 'x (cm)', 'y (cm)', 'A (cm²)'], 18)
    hdr(wx, 40, 6, ['Fibre', 'x', 'y', 'A', 'd ⊥ NA', 'C (kg)', 'C·y', 'C·x'], 18)
    hdr(wx, 40, 14, ['F (kg)', 'F·y', 'F·x', 'd ⊥ NA', 'εs', 'fs'], 18)
    # bars (cols A-D inputs from Bars; N-S formulas)
    for i in range(NB):
        rr = 41 + i
        wx.cell(rr, 1, i + 1).font = f9
        wx.cell(rr, 2, f'=Bars!B{B0+i}-Report!$C$10/2').font = f9      # centred
        wx.cell(rr, 3, f'=Bars!C{B0+i}-Report!$C$11/2').font = f9
        wx.cell(rr, 4, f'=Bars!E{B0+i}').font = f9
        wx.cell(rr, 17, f'=$C$12-(B{rr}*$C$11+C{rr}*$D$11)').font = f9                        # d
        wx.cell(rr, 18, f'=Report!$H$9*($C$10-Q{rr})/$C$10').font = f9                         # εs
        wx.cell(rr, 19, f'=MAX(-Report!$C$8,MIN(Report!$C$8,R{rr}*Report!$F$8))').font = f9   # fs
        wx.cell(rr, 14, f'=(S{rr}-IF(Q{rr}<=$C$13,0.85*Report!$C$7,0))*D{rr}').font = f9       # F
        wx.cell(rr, 15, f'=N{rr}*C{rr}').font = f9
        wx.cell(rr, 16, f'=N{rr}*B{rr}').font = f9
        wx.cell(rr, 18).number_format = '0.00000'
    # concrete fibres 30 x 133 (same grid as the engine)
    nx, ny = 30, max(30, int(30 * m['h'] / m['b']))
    k = 0
    for jy in range(ny):
        for ix in range(nx):
            rr = 41 + k
            wx.cell(rr, 6, k + 1).font = f9
            wx.cell(rr, 7, f'=({ix}+0.5)/{nx}*Report!$C$10-Report!$C$10/2').font = f9
            wx.cell(rr, 8, f'=({jy}+0.5)/{ny}*Report!$C$11-Report!$C$11/2').font = f9
            wx.cell(rr, 9, f'=Report!$C$10*Report!$C$11/{nx * ny}').font = f9
            wx.cell(rr, 10, f'=$C$12-(G{rr}*$C$11+H{rr}*$D$11)').font = f9
            wx.cell(rr, 11, f'=IF(J{rr}<=$C$13,0.85*Report!$C$7*I{rr},0)').font = f9
            wx.cell(rr, 12, f'=K{rr}*H{rr}').font = f9
            wx.cell(rr, 13, f'=K{rr}*G{rr}').font = f9
            k += 1
    for col, w in zip('ABCDEFGHIJKLMNOPQRS', [36, 8, 12, 12, 12, 7, 8, 8, 7, 8, 9, 10, 10, 10, 10, 10, 8, 9, 8]):
        wx.column_dimensions[col].width = w
    wx.freeze_panes = 'A41'

    wb.save(OUT)
    return dict(combo=q['combo'], theta=math.degrees(th), c=c)
    print('saved', OUT, 'selected combo', q['story'], q['col'], q['combo'], 'theta', math.degrees(th), 'c', c,
          'uncapped D/C', q['P'] / fP, 'engine', q['dcT'])
