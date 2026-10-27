"""Column mapping plan for one story: section outline (true size), mark and label per column – PDF (A1) + DXF (mm) + rows.

usage:  python3 -I plan_map.py <ETABS full model xlsx with Point + Column Object Connectivity> <OUT/results.json> <out prefix> <story>
Needs the ETABS table 'Point Object Connectivity' (UniqueName, X, Y, Z) – exported with or without its 'TABLE:' title row.
ASSUMPTION (stated on the drawing): column local axis angle 0 -> depth t3 (h) along global X, width t2 (b) along global Y; export
'Frame Assignments - Local Axes' to confirm rotated columns. A column whose points are missing is listed, not drawn.
"""
import sys, os, json, math, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import etabs_io as E
import ezdxf
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle
from matplotlib.backends.backend_pdf import PdfPages
src, resj, out, story = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
T, U = E.read_tables(src); geo = E.geometry(T, U)
xy = {}
for (l, s), g in geo.items():
    if 'x' in g:
        xy.setdefault(l, {})[s] = (g['x'] / 100, g['y'] / 100)
R = json.load(open(resj))
rows = []
for r in R['results']:
    for p in r['per']:
        if p['story'] == story:
            lab = r['label']; src_st = story if story in xy.get(lab, {}) else next(iter(xy.get(lab, {})), None)
            x, y = xy[lab][src_st] if src_st else (None, None)
            rows.append(dict(mark=r['mark'], label=lab, shape=r['shape'], b=r['b'] * 10, h=r['h'] * 10, bars=f"{r['nbar']}-DB{r['db']}",
                             dc=p['dc'], status=p['status'], x=x, y=y, xy_from=src_st, fc=p['fc']))
json.dump(rows, open(out + '_rows.json', 'w'), indent=1)
# ---------------- DXF (mm, plan; ASSUMPTION: local axis angle 0 -> depth t3 (h) along global X, width t2 (b) along global Y)
doc = ezdxf.new('R2018', setup=True); doc.units = ezdxf.units.MM; msp = doc.modelspace()
for ly, c in (('S-COLS', 4), ('G-ANNO-TEXT', 7), ('G-ANNO-MARK', 1), ('G-ANNO-CHECK', 6)):
    doc.layers.add(ly, color=c)
for q in rows:
    if q['x'] is None:
        continue
    X, Y = q['x'] * 1000, q['y'] * 1000
    if q['shape'] == 'circ':
        msp.add_circle((X, Y), q['b'] / 2, dxfattribs={'layer': 'S-COLS'})
    else:
        dx, dy = q['h'] / 2, q['b'] / 2
        msp.add_lwpolyline([(X - dx, Y - dy), (X + dx, Y - dy), (X + dx, Y + dy), (X - dx, Y + dy)], close=True, dxfattribs={'layer': 'S-COLS'})
    xr = X + (q['b'] if q['shape'] == 'circ' else q['h']) / 2 + 150
    msp.add_text(q['mark'], height=300, dxfattribs={'layer': 'G-ANNO-MARK'}).set_placement((xr, Y + 50), align=ezdxf.enums.TextEntityAlignment.BOTTOM_LEFT)
    msp.add_text(q['label'], height=200, dxfattribs={'layer': 'G-ANNO-TEXT'}).set_placement((xr, Y - 50), align=ezdxf.enums.TextEntityAlignment.TOP_LEFT)
    if q['status'] != 'OK' or q['xy_from'] != story:
        msp.add_circle((X, Y), max(q['b'], q['h']) * 0.9, dxfattribs={'layer': 'G-ANNO-CHECK'})
doc.saveas(out + '.dxf')
# ---------------- PDF A1 landscape
xs = [q['x'] for q in rows if q['x'] is not None]; ys = [q['y'] for q in rows if q['y'] is not None]
W, H = 33.11, 23.39
with PdfPages(out + '.pdf') as pdf:
    fig = plt.figure(figsize=(W, H)); ax = fig.add_axes([0.03, 0.06, 0.70, 0.88])
    marks = sorted({q['mark'] for q in rows}, key=lambda m: int(m[1:]))
    cmap = plt.get_cmap('tab20'); col = {m: cmap(i % 20) for i, m in enumerate(marks)}
    for q in rows:
        if q['x'] is None:
            continue
        X, Y = q['x'], q['y']
        c = col[q['mark']]
        if q['shape'] == 'circ':
            ax.add_patch(Circle((X, Y), q['b'] / 2000, fc=c, ec='k', lw=0.6))
        else:
            ax.add_patch(Rectangle((X - q['h'] / 2000, Y - q['b'] / 2000), q['h'] / 1000, q['b'] / 1000, fc=c, ec='k', lw=0.6))
        dxr = (q['b'] if q['shape'] == 'circ' else q['h']) / 2000 + 0.15
        ax.text(X + dxr, Y + 0.05, q['mark'], ha='left', va='bottom', fontsize=8, weight='bold', color='#b3261e')
        ax.text(X + dxr, Y - 0.05, q['label'], ha='left', va='top', fontsize=6.5)
        if q['status'] != 'OK' or q['xy_from'] != story:
            ax.add_patch(Circle((X, Y), max(q['b'], q['h']) / 1000 * 0.9, fc='none', ec='#8e24aa', lw=1.2, ls='--'))
    ax.set_xlim(min(xs) - 3, max(xs) + 3); ax.set_ylim(min(ys) - 3, max(ys) + 3); ax.set_aspect('equal')
    ax.grid(True, lw=0.3, color='#ddd'); ax.set_xlabel('X (m)'); ax.set_ylabel('Y (m)')
    ax.set_title(f"{R['config']['project'].get('job', '')} – COLUMN MARKS AT {story} (ETABS story {story} = column below level {story})", fontsize=14, weight='bold', loc='left')
    # legend table
    tx = fig.add_axes([0.75, 0.06, 0.23, 0.88]); tx.axis('off')
    lines = collections.OrderedDict()
    for q in sorted(rows, key=lambda q: (int(q['mark'][1:]), int(q['label'][1:]))):
        sec = f"Ø{q['b']:.0f}" if q['shape'] == 'circ' else f"{q['b']:.0f}×{q['h']:.0f}"
        lines.setdefault(q['mark'], [sec, q['bars'], []])[2].append(q['label'])
    y0 = 0.99
    tx.text(0, y0, f'MARK   SECTION (b×h)   BARS    LABELS at {story}', fontsize=9, weight='bold', family='monospace'); y0 -= 0.018
    for m, (sec, bars, labs) in lines.items():
        tx.add_patch(Rectangle((0, y0 - 0.004), 0.03, 0.012, fc=col[m], ec='k', lw=0.4, transform=tx.transAxes))
        txt = f'{m:<5} {sec:<11} {bars:<9} ' + ', '.join(labs)
        for k in range(0, len(txt), 48):
            tx.text(0.04, y0, txt[k:k + 48], fontsize=7.2, family='monospace'); y0 -= 0.014
        y0 -= 0.004
    tx.text(0, 0.03, 'b = t2, h = t3 (mm). ASSUMPTION: local axis angle 0 – h (t3) along global X, b (t2) along global Y;\n'
                     'export "Frame Assignments - Local Axes" to confirm rotated columns.\n'
                     'Dashed circle: status not OK (ACCEPTED / ASK_RHO) or XY taken from another story.\nDRAFT – for check',
            fontsize=7, color='#555')
    pdf.savefig(fig); plt.close(fig)
print(len(rows), sum(1 for q in rows if q['x'] is None), [q['label'] for q in rows if q['xy_from'] != story])
