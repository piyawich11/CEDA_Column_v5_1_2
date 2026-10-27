"""Biaxial P-Mx-My interaction surface for RC columns (strain compatibility, ACI stress block).

Units: kg, cm; moments returned in kg-m. Compression positive.
Axes: x along b (section width), y along h (section depth).
  Mx = moment about the x-axis (bending that uses h, "strong" when h > b)  -> ETABS M3 when h = t3
  My = moment about the y-axis (bending that uses b)                      -> ETABS M2 when b = t2

phi (กฎกระทรวง พ.ศ. 2566 ข้อ 8 วรรคสอง, quality-controlled column):
  compression tied 0.70 / spiral 0.75, flexure/tension 0.90;
  transition by extreme tension steel strain εt (ACI 318-19 21.2.2): φc when εt <= εy, 0.90 when εt >= εy + 0.003.
phiPn,max = alpha * phi_c * Po, alpha = 0.80 tied / 0.85 spiral (ACI 318-19 22.4.2.1).
"""
import math
import numpy as np
from scipy.spatial import ConvexHull


class Section:
    def __init__(self, b, h, bars, fc, fy, Es=2.04e6, phi_c=0.70, alpha=0.80, phi_t=0.90, ecu=0.003,
                 shape='rect', nfib=30):
        """b, h (cm). shape 'rect' or 'circ' (circular: diameter = b = h).
        bars: list of (x, y, area_cm2) with origin at the lower-left corner of the bounding box."""
        self.shape = shape
        if shape == 'circ':
            h = b
        self.b, self.h, self.fc, self.fy, self.Es = float(b), float(h), float(fc), float(fy), float(Es)
        self.phi_c, self.alpha, self.phi_t, self.ecu = phi_c, alpha, phi_t, ecu
        bars = np.array(bars, float)
        self.bx = bars[:, 0] - b / 2
        self.by = bars[:, 1] - h / 2
        self.bA = bars[:, 2]
        self.As = float(self.bA.sum())
        self.beta1 = float(np.clip(0.85 - 0.05 * (fc - 280) / 70, 0.65, 0.85))
        nx = nfib
        ny = max(nfib, int(nfib * h / b))
        xs = (np.arange(nx) + 0.5) / nx * b - b / 2
        ys = (np.arange(ny) + 0.5) / ny * h - h / 2
        X, Y = np.meshgrid(xs, ys)
        cx, cy = X.ravel(), Y.ravel()
        dA = b * h / (nx * ny)
        if shape == 'circ':
            keep = cx ** 2 + cy ** 2 <= (b / 2) ** 2
            cx, cy = cx[keep], cy[keep]
            self.Ag = math.pi * b ** 2 / 4
            dA = self.Ag / keep.sum()          # exact gross area
        else:
            self.Ag = b * h
        self.cx, self.cy = cx, cy
        self.cA = np.full(cx.size, dA)
        self.Po = 0.85 * fc * (self.Ag - self.As) + fy * self.As
        self.phiPnmax = alpha * phi_c * self.Po
        self.ety = fy / Es

    # ------------------------------------------------------------------ one strain state
    def umax(self, ux, uy):
        if self.shape == 'circ':
            return self.b / 2
        return abs(ux) * self.b / 2 + abs(uy) * self.h / 2

    def phi_of(self, et):
        if et <= self.ety:
            return self.phi_c
        if et >= self.ety + 0.003:
            return self.phi_t
        return self.phi_c + (self.phi_t - self.phi_c) * (et - self.ety) / 0.003

    def point(self, theta, c, detail=False):
        """theta: direction (rad) of the unit vector u normal to the NA pointing to the compression side.
        c: NA depth measured along u from the extreme compression fibre (cm).
        Returns Pn (kg), Mx, My (kg-m), phi."""
        ux, uy = math.cos(theta), math.sin(theta)
        um = self.umax(ux, uy)
        dc = um - (self.cx * ux + self.cy * uy)
        ds = um - (self.bx * ux + self.by * uy)
        a = self.beta1 * c
        Cc = 0.85 * self.fc * self.cA * (dc <= a)
        es = self.ecu * (c - ds) / c
        fs = np.clip(es * self.Es, -self.fy, self.fy)
        Fs = (fs - 0.85 * self.fc * (ds <= a)) * self.bA
        Pn = Cc.sum() + Fs.sum()
        Mx = (Cc * self.cy).sum() + (Fs * self.by).sum()
        My = -((Cc * self.cx).sum() + (Fs * self.bx).sum())
        et = max(-es.min(), 0.0)
        phi = self.phi_of(et)
        if detail:
            return dict(Pn=Pn, Mx=Mx / 100, My=My / 100, phi=phi, et=et, es=es, fs=fs, Fs=Fs, ds=ds, Cc=Cc.sum(), a=a)
        return Pn, Mx / 100.0, My / 100.0, phi

    # ------------------------------------------------------------------ surface
    def _scale(self):
        return np.array([self.phiPnmax, self.phiPnmax * self.h / 100 / 4, self.phiPnmax * self.b / 100 / 4])

    def surface(self, nth=72, nc=60):
        D = math.hypot(self.b, self.h)
        cs = np.concatenate([np.geomspace(0.02 * D, 0.5 * D, nc // 2), np.linspace(0.5 * D, 6 * D, nc // 2)])
        pts = []
        for th in np.linspace(0, 2 * np.pi, nth, endpoint=False):
            for c in cs:
                Pn, Mx, My, phi = self.point(th, c)
                pts.append((phi * Pn, phi * Mx, phi * My))
        pts.append((-self.phi_t * self.fy * self.As, 0.0, 0.0))
        pts = np.array(pts)
        cap = self.phiPnmax
        pts[pts[:, 0] > cap, 0] = cap
        pts = np.vstack([pts, [cap, 0, 0]])
        self.pts = pts
        self.hull = ConvexHull(pts / self._scale())
        return pts

    def dc(self, P, Mx, My):
        """Radial demand/capacity from the origin through (P, Mx, My) to the capped surface."""
        if not hasattr(self, 'hull'):
            self.surface()
        v = np.array([P, Mx, My]) / self._scale()
        if not np.any(v):
            return 0.0
        n, d = self.hull.equations[:, :3], self.hull.equations[:, 3]
        nv = n @ v
        with np.errstate(divide='ignore'):
            t = np.where(nv > 1e-12, -d / nv, np.inf)
        return float(1.0 / t.min())

    def uniaxial(self, axis='x', n=120):
        th = math.pi / 2 if axis == 'x' else 0.0
        D = self.h if axis == 'x' else self.b
        cs = np.concatenate([np.geomspace(0.005 * D, D, n // 2), np.linspace(D, 10 * D, n // 2)])[::-1]
        pts = []
        for c in cs:
            Pn, Mx, My, phi = self.point(th, c)
            pts.append((phi * Pn, abs(Mx if axis == 'x' else My) * phi))
        pts = np.array(pts)
        cap = self.phiPnmax
        k = int(np.argmax(pts[:, 0] <= cap))
        if k > 0:
            p1, p2 = pts[k - 1], pts[k]
            t = (cap - p2[0]) / (p1[0] - p2[0])
            Mi = p2[1] + t * (p1[1] - p2[1])
            pts = np.vstack([[cap, 0.0], [cap, Mi], pts[k:]])
        return np.vstack([pts, [-self.phi_t * self.fy * self.As, 0.0]])

    def nominal_M(self, P, axis='x'):
        """Nominal moment strength (phi = 1) at axial load P (kg) for uniaxial bending – used for IMF Ve."""
        th = math.pi / 2 if axis == 'x' else 0.0
        D = self.h if axis == 'x' else self.b
        lo, hi = 0.01 * D, 20 * D
        for _ in range(80):
            mid = math.sqrt(lo * hi)
            Pn = self.point(th, mid)[0]
            if Pn > P:
                hi = mid
            else:
                lo = mid
        _, Mx, My, _ = self.point(th, math.sqrt(lo * hi))
        return abs(Mx if axis == 'x' else My)

    def contour(self, P):
        s = self._scale()
        p = P / s[0]
        V = self.hull.points
        segs = []
        for simp in self.hull.simplices:
            tri = V[simp]
            for i in range(3):
                a, b = tri[i], tri[(i + 1) % 3]
                if (a[0] - p) * (b[0] - p) < 0:
                    t = (p - a[0]) / (b[0] - a[0])
                    segs.append((a + t * (b - a))[1:] * s[1:])
        if not segs:
            return np.zeros((0, 2))
        Q = np.array(segs)
        Q = Q[np.argsort(np.arctan2(Q[:, 1], Q[:, 0]))]
        return np.vstack([Q, Q[:1]])


def _ray_poly(C, ang):
    d = np.array([math.cos(ang), math.sin(ang)])
    best = 0.0
    for i in range(len(C) - 1):
        a, b = C[i], C[i + 1]
        M = np.array([d, a - b]).T
        if abs(np.linalg.det(M)) < 1e-12:
            continue
        t, s = np.linalg.solve(M, a)
        if t > 0 and -1e-9 <= s <= 1 + 1e-9:
            best = max(best, t)
    return best


def meridian(S, ang, n=60):
    """phiPn - phiMn curve in moment direction ang (rad from +Mx)."""
    Pmin = -S.phi_t * S.fy * S.As
    out = [(Pmin, 0.0)]
    for P in np.linspace(Pmin * 0.999, S.phiPnmax * 0.999, n):
        C = S.contour(P)
        out.append((P, _ray_poly(C, ang) if len(C) > 3 else 0.0))
    out.append((S.phiPnmax, 0.0))
    return np.array(out)
