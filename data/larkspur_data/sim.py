"""Larkspur's operating model. Shared by the seeded history and the live world so both
produce the same company: master data, shipment timelines and the contacts they cause."""
from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from . import contacts as ct
from . import freight as fr
from . import geo
from . import names as nm

WEEKDAY_FACTOR = [1.14, 1.06, 1.0, 0.98, 0.92, 0.04, 0.0]  # Mon..Sun, Saturday is a trickle
CATEGORIES = ["status", "pickup", "invoice", "reweigh", "pod", "claim", "appointment", "other"]
CLAIMS_STAFF = ["tkessler", "jlarue", "mbeck"]
AGENTS = nm.AGENTS + ["pwhitman", "ebrooks", "vsantos", "gholt", "nreyes", "ofarah", "lpratt", "dkim", "sbarnes", "rquinn", "tfoster", "acole"]


def day_rng(seed: int, d: date, salt: str = "") -> random.Random:
    h = hashlib.sha256(f"{seed}:{d.isoformat()}:{salt}".encode()).hexdigest()
    return random.Random(int(h[:16], 16))


def add_business_days(d: date, n: int) -> date:
    while n > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


def at(d: date, hour: float) -> datetime:
    return datetime.combine(d, time(0)) + timedelta(seconds=int(hour * 3600))


@dataclass
class Customer:
    cusno: str
    name: str
    terminal: str
    city: str
    state: str
    zip: str
    addr: str
    weight: float
    edi: bool = False
    edi_broken: bool = False
    restricted: bool = False
    discount: float = 0.0
    contacts: list = field(default_factory=list)  # (first, last, email, phone)


class Master:
    """Terminals, customers, EDI partners and contracts, fixed by the seed."""

    def __init__(self, scen: dict):
        self.scen = scen
        rng = random.Random(scen["seed"])
        used: set = set()
        special = {
            "Meridian Home Goods": ("CMH", scen["key_accounts"]["Meridian Home Goods"]["share"]),
            "Hartwell Appliance Distributors": ("LOU", scen["key_accounts"]["Hartwell Appliance Distributors"]["share"]),
            "Northside Hardware Co": ("PIA", scen["key_accounts"]["Northside Hardware Co"]["share"]),
        }
        for n in scen["restricted"]["contract_flag"]:
            special.setdefault(n, (rng.choice(geo.TERMINAL_CODES), 0.003))
        used.update(special)
        n_cust = scen["volume"]["customers"]
        raw = [1.0 / (i + 1) ** 1.05 for i in range(n_cust - len(special))]
        total_special = sum(v[1] for v in special.values())
        scale = (1 - total_special) / sum(raw)
        self.customers: list[Customer] = []
        for i, w in enumerate(raw):
            self.customers.append(self._make(rng, nm.company_name(rng, used), rng.choice(geo.TERMINAL_CODES), w * scale, 100000 + i * 7))
        for j, (n, (trm, share)) in enumerate(special.items()):
            self.customers.append(self._make(rng, n, trm, share, 300000 + j * 11))
        # EDI: bigger customers are more likely to trade 214s
        by_vol = sorted(self.customers, key=lambda c: -c.weight)
        for rank, c in enumerate(by_vol):
            c.edi = rng.random() < (0.85 if rank < 150 else 0.45 if rank < 600 else 0.12)
        broken = [c for c in by_vol[15:200] if c.edi and c.name not in special][:: 2][: scen["edi_broken"]["count"]]
        for c in broken:
            c.edi_broken = True
        for c in self.customers:
            c.restricted = c.name in scen["restricted"]["contract_flag"]
        self.by_name = {c.name: c for c in self.customers}
        self.by_no = {c.cusno: c for c in self.customers}
        self.cum = []
        acc = 0.0
        for c in self.customers:
            acc += c.weight
            self.cum.append(acc)
        self.total_weight = acc

    def _make(self, rng, name, trm, weight, num) -> Customer:
        city, st, zips = rng.choice(geo.SERVICE[trm])
        dom = nm.email_domain(name)
        people = []
        for _ in range(rng.randint(1, 4)):
            f, l = nm.person(rng)
            people.append((f, l, f"{f[0].lower()}{l.lower()}@{dom}", f"({rng.randint(219, 989)}) 555-{rng.randint(1000, 9999)}"))
        return Customer(cusno=f"{num:08d}"[-8:], name=name, terminal=trm, city=city, state=st, zip=rng.choice(zips),
                        addr=f"{rng.randint(100, 9999)} {rng.choice(geo.STREETS)}", weight=weight,
                        discount=round(rng.uniform(45, 72), 2), contacts=people)

    def pick_customer(self, rng) -> Customer:
        import bisect
        return self.customers[min(bisect.bisect_left(self.cum, rng.random() * self.total_weight), len(self.customers) - 1)]


@dataclass
class Plan:
    """One shipment with everything that will happen to it."""
    row: dict
    timeline: list  # (datetime, kind, dict)
    weights: dict   # contact category -> weight


class ProCounter:
    def __init__(self):
        self.next = {t: (int(f"{i + 1:02d}") * 1000000) + 1 for i, t in enumerate(c[0] for c in geo.TERMINALS)}

    def take(self, trm: str) -> str:
        base = self.next[trm]
        self.next[trm] += 1
        return fr.pro_number(base)


def modifiers(scen: dict, d: date) -> dict:
    """Incident and drift effects active on a given day."""
    mods = {"storm": {}, "dimensioner": None, "outage": [], "slowdown": None, "edi_down": None}
    dim = scen["dimensioner"]
    if d >= date.fromisoformat(dim["start"]):
        mods["dimensioner"] = dim
    for inc in scen.get("incidents", []):
        if inc["type"] == "storm":
            s = date.fromisoformat(inc["start"])
            if s <= d < s + timedelta(days=inc["days"]):
                for t in inc["terminals"]:
                    mods["storm"][t] = inc["delay_rate"]
        elif inc["type"] == "freightcore_outage":
            mods["outage"].append((datetime.fromisoformat(inc["start"]), datetime.fromisoformat(inc["end"])))
        elif inc["type"] == "soap_slowdown":
            s = date.fromisoformat(inc["start"])
            if s <= d < s + timedelta(days=inc["days"]):
                mods["slowdown"] = inc["latency_ms"]
        elif inc["type"] == "edi_partner_down":
            s = date.fromisoformat(inc["start"])
            if s <= d < s + timedelta(days=inc["days"]):
                mods["edi_down"] = inc["partner"]
    return mods


def plan_shipment(rng: random.Random, d: date, m: Master, pros: ProCounter, seq: int) -> Plan:
    scen, rates = m.scen, m.scen["rates"]
    shipper = m.pick_customer(rng)
    org = shipper.terminal
    dst = rng.choice([t for t in geo.TERMINAL_CODES])
    # consignee: sometimes another customer, usually a business that isn't one
    if rng.random() < 0.18:
        cons = m.pick_customer(rng)
        cname, ccity, cst, czip, caddr, ccus = cons.name, cons.city, cons.state, cons.zip, cons.addr, cons.cusno
        dst = cons.terminal
    else:
        ccity, cst, zips = rng.choice(geo.SERVICE[dst])
        cname = nm.company_name(rng, set())
        czip, caddr, ccus = rng.choice(zips), f"{rng.randint(100, 9999)} {rng.choice(geo.STREETS)}", ""
    frt = rng.choices(["PP", "CC", "TP"], [0.72, 0.18, 0.10])[0]
    bto = shipper.cusno if frt == "PP" else (ccus or shipper.cusno) if frt == "CC" else m.pick_customer(rng).cusno
    pcs = rng.choices([1, 2, 3, 4, 5, 6, 8], [30, 24, 16, 12, 8, 6, 4])[0]
    l, w, h = 48, 40, rng.choice([36, 42, 48, 50, 54, 60, 72])
    density = rng.lognormvariate(math.log(11), 0.55)
    cuft = fr.cubic_feet(l, w, h, pcs)
    wgt = max(80, int(cuft * density / 10) * 10)
    cls = fr.density_class(wgt, cuft)
    acc = [a for a, p in [("LG", 0.12), ("RS", 0.05), ("AP", 0.18), ("ID", 0.03), ("NT", 0.06), ("LA", 0.04)] if rng.random() < p]
    hz = rng.random() < 0.02
    if hz:
        acc.append("HZ")
    zn = geo.zone(org, dst)
    net, acc_amt, fsc = fr.rate(wgt, cls, zn, shipper.discount, acc)
    pro = pros.take(org)
    bol = f"{rng.randint(10, 99)}{seq:06d}{rng.randint(0, 9)}"
    po = f"{rng.choice(['PO', '', '4500', 'SO'])}{rng.randint(100000, 9999999)}"
    eta = add_business_days(d, geo.transit_days(org, dst))
    mods = modifiers(scen, d)
    row = dict(shppro=pro, shpbol=bol, shppo=po, shpdt=d, shporg=org, shpdst=dst, shpshp=shipper.cusno,
               shpcnm=cname, shpcad=caddr, shpcct=ccity, shpcst=cst, shpczp=czip, shpcon=ccus, shpbto=bto, shpfrt=frt,
               shppcs=pcs, shpwgt=wgt, shpcuf=cuft, shpcls=cls, shphzm="Y" if hz else "N", shpacc=",".join(acc),
               shpchg=round(net + acc_amt + fsc, 2), shpstscd=None, shpstsdt=None, shptrm=org, shpeta=eta, shpapt=None,
               shpdlvdt=None, shppod=None, shpexc="N", shpupd=None, shpusr="FCBATCH")
    tl: list = []
    usr = lambda: rng.choice(["DOCK" + str(rng.randint(1, 9)), "SCAN" + org, "LHDISP", "CITYDSP"])
    pu = at(d, rng.uniform(13.0, 17.5))
    tl.append((pu, "evt", dict(cd="PU", trm=org, usr="DRV" + str(rng.randint(100, 999)))))
    tl.append((pu + timedelta(hours=rng.uniform(1.5, 3.5)), "evt", dict(cd="AR", trm=org, usr=usr())))
    lh = at(d, rng.uniform(21.0, 23.8))
    tl.append((lh, "evt", dict(cd="LH", trm=org, usr="LHDISP")))
    via = geo.via_breakbulk(org, dst)
    dims = mods["dimensioner"]
    reweigh_rate = rates["reweigh"]
    t = lh
    if via:
        t = lh + timedelta(hours=rng.uniform(3, 6))
        tl.append((t, "evt", dict(cd="BB", trm="IND", usr=usr())))
        if dims and dims["terminal"] == "IND":
            reweigh_rate = dims["reweigh_rate"]
        if rng.random() < reweigh_rate:
            tl.append((t + timedelta(minutes=40), "rwg", _reweigh(rng, row, "IND", dims if dims and dims["terminal"] == "IND" else None, zn, shipper.discount)))
        t = t + timedelta(hours=rng.uniform(6, 14))
        tl.append((t, "evt", dict(cd="LH", trm="IND", usr="LHDISP")))
    elif rng.random() < rates["reweigh"]:
        tl.append((lh - timedelta(hours=2), "rwg", _reweigh(rng, row, org, None, zn, shipper.discount)))
    # arrive destination terminal the evening before delivery
    dlv_day = eta
    delayed, reason = False, None
    storm = mods["storm"].get(dst) or mods["storm"].get(org)
    delay_p = rates["delay"] if not storm else storm
    if rng.random() < delay_p:
        delayed = True
        reason = "AO" if storm else rng.choices(["AI", "B1", "A2", "BK", "AO"], [3, 3, 2, 1, 1])[0]
        dlv_day = add_business_days(eta, rng.choice([1, 1, 2]))
    arrive = at(add_business_days(dlv_day, -1) if dlv_day > d else d, rng.uniform(1.0, 5.0)) if org != dst else at(dlv_day, 5.5)
    arrive = max(arrive, t + timedelta(hours=2))
    tl.append((arrive, "evt", dict(cd="AD", trm=dst, usr=usr())))
    if delayed:
        tl.append((at(eta, rng.uniform(6, 9)), "evt", dict(cd="DY", trm=dst, rsn=reason, usr="CITYDSP")))
    if "AP" in acc:
        tl.append((arrive + timedelta(hours=3), "evt", dict(cd="AP", trm=dst, usr="APPTDSK")))
    od = at(dlv_day, rng.uniform(6.5, 8.5))
    tl.append((od, "evt", dict(cd="OD", trm=dst, usr="CITYDSP")))
    dl = od + timedelta(hours=rng.uniform(1.0, 7.5))
    r = rng.random()
    if r < rates["refused"]:
        tl.append((dl, "evt", dict(cd="RF", trm=dst, rsn="BS", usr="DRV")))
    else:
        osd = None
        if r < rates["refused"] + rates["damage"]:
            osd = "D"
        elif r < rates["refused"] + rates["damage"] + rates["shortage"]:
            osd = "S"
        concealed = osd == "D" and rng.random() < 0.3
        code = "DX" if osd and not concealed else "DL"
        f, l_ = nm.person(rng)
        tl.append((dl, "dlv", dict(cd=code, trm=dst, pod=f"{f[0]}. {l_}".upper(), usr="DRV" + str(rng.randint(100, 999)))))
        if osd:
            od_day = (dl + timedelta(days=rng.randint(1, 4))).date() if concealed else dl.date()
            tl.append((at(od_day, 15) if concealed else dl + timedelta(minutes=5), "osd", dict(typ=osd, trm=dst, pcs=max(1, pcs // rng.choice([1, 2, 3])), con="C" if concealed else "")))
            if rng.random() < rates["claim_file_given_osd"]:
                filed = dl + timedelta(days=max(1, int(rng.lognormvariate(math.log(9), 0.7))))
                amt = round(rng.uniform(180, 6500), 2)
                tl.append((filed, "claim", dict(typ=osd, amt=amt)))
        tl.append((at(add_business_days(dl.date(), 1), 4.0), "inv", {}))
    late = dlv_day > eta
    w = {
        "status": 1.0 + 6.0 * delayed + 2.0 * late + (5.0 if shipper.edi_broken else 0.0),
        "pickup": 1.0,
        "invoice": 1.0 + 1.5 * bool(acc) + 0.8 * (frt != "PP"),
        "reweigh": 0.0,
        "pod": 1.0,
        "claim": 0.0,
        "appointment": 4.0 if "AP" in acc else 0.25,
    }
    for ts, kind, data in tl:
        if kind == "rwg":
            w["reweigh"] = 1.0 + (3.0 if data["src"] == "D" and data.get("biased") else 0.0)
        if kind == "osd":
            w["pod"] += 3.0
        if kind == "claim":
            w["claim"] = 1.0
    # the terminal mapping bug: OD sent as D1 for EDI customers at affected terminals
    xb = m.scen["xref_bug"]
    if dst in xb["terminals"] and shipper.edi and not shipper.edi_broken:
        w["status"] += 8.0
    tl.sort(key=lambda x: x[0])
    return Plan(row=row, timeline=tl, weights=w)


def _reweigh(rng, row, trm, dims, zn, discount):
    """Dock scale or dimensioner correction. A biased dimensioner reads volume high."""
    src = "D" if rng.random() < 0.7 else "S"
    ow, ocf, ocl = row["shpwgt"], row["shpcuf"], row["shpcls"]
    nw, ncf = ow, ocf
    biased = False
    if src == "D":
        bias = dims["volume_bias"] if dims else 0.0
        biased = bool(dims)
        ncf = round(ocf * (1 + bias + rng.uniform(-0.02, 0.12)), 1)
    else:
        nw = int(ow * (1 + rng.uniform(0.03, 0.18)) / 10) * 10
    ncl = fr.density_class(nw, ncf)
    return dict(src=src, trm=trm, ow=ow, nw=nw, ocf=ocf, ncf=ncf, ocl=ocl, ncl=ncl, biased=biased)


def contact_time(rng, kind: str, plan: Plan) -> datetime | None:
    """When a customer would write about this shipment."""
    row = plan.row
    evts = {k: ts for ts, k2, dd in plan.timeline for k in [dd.get("cd", k2)]}
    def biz(d: date) -> datetime:
        hour = rng.choices([rng.uniform(7.5, 17.5), rng.uniform(17.5, 22)], [0.86, 0.14])[0]
        if d.weekday() >= 5:
            d = add_business_days(d, 1)
        return at(d, hour)
    if kind == "status":
        base = evts.get("DY") or at(row["shpeta"], 10)
        return biz((base + timedelta(days=rng.choice([0, 0, 1, 1, 2]))).date())
    if kind == "pickup":
        return at(row["shpdt"], rng.uniform(7.0, 13.0))
    if kind in ("invoice", "reweigh"):
        inv = next((ts for ts, k, _ in plan.timeline if k == "inv"), None)
        return biz((inv + timedelta(days=rng.randint(2, 14))).date()) if inv else None
    if kind == "pod":
        dl = next((ts for ts, k, _ in plan.timeline if k == "dlv"), None)
        return biz((dl + timedelta(days=rng.randint(0, 6))).date()) if dl else None
    if kind == "claim":
        c = next((ts for ts, k, _ in plan.timeline if k == "claim"), None)
        return biz((c + timedelta(days=rng.choice([0, 0, 20, 35, 50]))).date()) if c else None
    if kind == "appointment":
        return biz((at(row["shpeta"], 9) - timedelta(days=1)).date())
    return None


def contact_slots(rng, plan: Plan, m: Master, kind: str) -> dict:
    row = plan.row
    s = dict(pro=row["shppro"], bol=row["shpbol"], po=row["shppo"], city=row["shpcct"], orgcity=geo.TERM[row["shporg"]][2],
             cons=row["shpcnm"], pcs=row["shppcs"], wgt=row["shpwgt"], cls=row["shpcls"],
             eta_txt=row["shpeta"].strftime("%A"), addr=m.by_no[row["shpshp"]].addr)
    for ts, k, d in plan.timeline:
        if k == "rwg":
            s.update(nw=d["nw"], ow=d["ow"], ocl=d["ocl"], ncl=d["ncl"])
    return s


def sender_for(rng, m: Master, plan: Plan, kind: str) -> dict:
    row = plan.row
    cusno = row["shpbto"] if kind in ("invoice", "reweigh") else row["shpshp"]
    c = m.by_no.get(cusno) or m.by_no[row["shpshp"]]
    f, l, e, p = rng.choice(c.contacts)
    return dict(first=f, last=l, email=e, phone=p, company=c.name, cusno=c.cusno)
