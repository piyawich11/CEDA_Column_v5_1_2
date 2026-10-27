import openpyxl
def wtab(wb, name, hdr, units, rows):
    ws = wb.create_sheet(name[:31])
    ws.append(['TABLE:  ' + name]); ws.append(hdr); ws.append(units)
    for r in rows: ws.append(r)
stories = [('B2', 0, 3), ('B1', 3, 6), ('1F', 6, 10), ('2F', 10, 14)]
def model(path, stories_used, combos, cases_forces, with_cases):
    wb = openpyxl.Workbook(); wb.remove(wb.active)
    # points / columns
    pts, cols, ef = [], [], []
    pid = 1
    for lab, (x, y) in (('C1', (0, 0)), ('C2', (8, 0))):
        for st, zb, zt in stories_used:
            pts.append([str(pid), st, lab, 'No', 'No', x, y, zb]); pts.append([str(pid + 1), st, lab, 'No', 'No', x, y, zt])
            cols.append([f'{lab}{st}', st, lab, str(pid), str(pid + 1), zt - zb]); pid += 2
    wtab(wb, 'Point Object Connectivity', ['Unique Name', 'Story', 'PointBay', 'IsAuto', 'IsSpecial', 'X', 'Y', 'Z'], ['', '', '', '', '', 'm', 'm', 'm'], pts)
    wtab(wb, 'Column Object Connectivity', ['Unique Name', 'Story', 'ColumnBay', 'UniquePtI', 'UniquePtJ', 'Length'], ['', '', '', '', '', 'm'], cols)
    sa = [[st, lab, f'{lab}{st}', 'Concrete Rectangular', 'No', 'C 800x400' if lab == 'C1' else 'C 600x600'] for lab in ('C1', 'C2') for st, zb, zt in stories_used]
    wtab(wb, 'Frame Assignments - Section Properties', ['Story', 'Label', 'UniqueName', 'Shape', 'Auto Select', 'Section Property'], ['']*6, sa)
    wtab(wb, 'Frame Section Property Definitions - Concrete Rectangular', ['Name', 'Material', 'Depth', 'Width'], ['', '', 'm', 'm'],
         [['C 800x400', 'C400', 0.8, 0.4], ['C 600x600', 'C400', 0.6, 0.6]])
    rows = []
    for c, items in combos.items():
        for ld, sf in items: rows.append([c, 'Linear Add', 'No', ld, sf])
    wtab(wb, 'Load Combination Definitions', ['Name', 'Type', 'Is Auto', 'Load Name', 'SF'], ['', '', '', '', ''], rows)
    for lab in ('C1', 'C2'):
        for st, zb, zt in stories_used:
            for case, f in cases_forces(lab, st).items():
                for sta in (0, zt - zb):
                    P = f['P'] - (0 if sta == 0 else 1)
                    ef.append([st, lab, f'{lab}{st}', case, 'Combination' if case in combos else 'LinStatic', f.get('step'), sta, -P, f['V2'], f['V3'], 0, f['M2'], f['M3']])
    wtab(wb, 'Element Forces - Columns', ['Story', 'Column', 'Unique Name', 'Output Case', 'Case Type', 'Step Type', 'Station', 'P', 'V2', 'V3', 'T', 'M2', 'M3'],
         ['', '', '', '', '', '', 'm', 'tonf', 'tonf', 'tonf', 'tonf-m', 'tonf-m', 'tonf-m'], ef)
    wb.save(path)
CB = {'U_A_00_02': [('DL', 1.4), ('SDL', 1.4), ('LL', 1.7)], 'U_A_01_01': [('DL', 1.05), ('SDL', 1.05), ('LL', 1.275), ('EQX', 1.0)],
      'U_B_99': [('DL', 1.2), ('LL', 1.6)]}
# load-case P per story (cumulative from top): DL 100/storey, SDL 20, LL 30
def lc(lab, st):
    n = {'2F': 1, '1F': 2, 'B1': 3, 'B2': 4}[st]
    return {'DL': dict(P=100 * n, V2=1, V3=1, M2=2 * n, M3=3 * n), 'SDL': dict(P=20 * n, V2=0, V3=0, M2=0, M3=0), 'LL': dict(P=30 * n, V2=0.5, V3=0.5, M2=1, M3=1)}
def full(lab, st):
    d = lc(lab, st); out = dict(d)
    out['U_A_00_02'] = {k: 1.4 * d['DL'][k] + 1.4 * d['SDL'][k] + 1.7 * d['LL'][k] for k in ('P', 'V2', 'V3', 'M2', 'M3')}
    return out
def seis(lab, st):
    d = lc(lab, st)
    g = {k: 1.05 * (d['DL'][k] + d['SDL'][k]) + 1.275 * d['LL'][k] for k in ('P', 'V2', 'V3', 'M2', 'M3')}
    return {'U_A_00_02': {k: 1.4 * (d['DL'][k] + d['SDL'][k]) + 1.7 * d['LL'][k] for k in g},
            'U_A_01_01': dict(P=g['P'] + 10, V2=g['V2'] + 50, V3=g['V3'] + 5, M2=g['M2'] + 40, M3=g['M3'] + 80, step='Max')}
import sys, os
OUT = sys.argv[1] if len(sys.argv) > 1 else '.'
model(os.path.join(OUT, 'full_red.xlsx'), stories, CB, full, True)
model(os.path.join(OUT, 'full_unred.xlsx'), stories, CB, full, True)
model(os.path.join(OUT, 'seis.xlsx'), stories[2:], CB, seis, False)
