# rating - copied from FC400 RTG01 logic 2009, cwt by class and zone
# zip -> terminal from terminal service file (svc.dat), see 2019 note in fcws.py

import math

CLASSES = [50.0, 55.0, 60.0, 65.0, 70.0, 77.5, 85.0, 92.5, 100.0, 110.0, 125.0, 150.0, 175.0, 200.0, 250.0, 300.0, 400.0, 500.0]
ACC = {"LG": 145.00, "RS": 165.00, "AP": 25.00, "ID": 140.00, "LA": 155.00, "NT": 45.00, "HZ": 65.00}
FSC = 0.285
TARIFF_DISC = 55.0  # list quote discount, accounts get theirs on invoice

TRM = {  # code: lat, lon
    "FWA": (41.0793, -85.1394), "IND": (39.7684, -86.1581), "TOL": (41.6528, -83.5379), "CMH": (39.9612, -82.9988),
    "CLE": (41.4993, -81.6944), "CIN": (39.1031, -84.5120), "GRY": (41.5934, -87.3464), "CHI": (41.8781, -87.6298),
    "PIA": (40.6936, -89.5890), "DET": (42.3314, -83.0458), "GRR": (42.9634, -85.6681), "LOU": (38.2527, -85.7585),
    "MKE": (43.0389, -87.9065),
}
SVC = {}  # zip5 -> terminal, loaded from svc.dat
try:
    import os
    for line in open(os.path.join(os.path.dirname(__file__), "svc.dat")):
        if line.strip() and not line.startswith("*"):
            z, t = line[:5], line[6:9]
            SVC[z] = t
except IOError:
    pass


def terminal_for_zip(z):
    return SVC.get(z)


def zone(o, d):
    if o == d:
        return 1
    a, b = TRM[o], TRM[d]
    dist = math.hypot((a[0] - b[0]) * 69, (a[1] - b[1]) * 52)
    if dist < 150:
        return 2
    elif dist < 250:
        return 3
    elif dist < 350:
        return 4
    return 5


def quote(o, d, cls, wgt, acc):
    zn = zone(o, d)
    cwt = round((18.0 + 6.5 * zn) * (cls / 100.0) ** 0.85, 2)
    net = max(cwt * wgt / 100.0 * (1 - TARIFF_DISC / 100.0), 95.0 + 15 * zn)
    a = sum(ACC.get(c, 0) for c in acc)
    fsc = round(net * FSC, 2)
    transit = {1: 1, 2: 1, 3: 2, 4: 2, 5: 3}[zn]
    return {"net": round(net, 2), "acc": a, "fsc": fsc, "total": round(net + a + fsc, 2), "transit": transit}
