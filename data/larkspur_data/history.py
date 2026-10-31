"""Materializes a date range of Larkspur's operations into table rows."""
from __future__ import annotations

import math
import random
from collections import defaultdict
from datetime import date, datetime, timedelta

from . import contacts as ct
from . import freight as fr
from . import geo
from . import sim

STSXRF = [  # trm, internal code, edi code, reason, description
    ("***", "PU", "AF", "NS", "PICKED UP"),
    ("***", "AR", "X6", "NS", "AT ORIGIN TERMINAL"),
    ("***", "LH", "X6", "NS", "LINEHAUL DEPARTED"),
    ("***", "BB", "X6", "NS", "AT BREAKBULK"),
    ("***", "AD", "AV", "NS", "AT DEST TERMINAL"),
    ("***", "OD", "X6", "NS", "OUT FOR DLV"),
    ("***", "DL", "D1", "NS", "DELIVERED"),
    ("***", "DX", "D1", "NS", "DLVD W/EXCEPTION"),
    ("***", "DY", "SD", "", "DELAYED"),
    ("***", "AP", "AG", "BK", "APPT SET"),
    ("***", "RF", "SD", "BS", "REFUSED"),
    ("***", "RW", "", "", "REWEIGHED"),
    ("***", "HL", "SD", "BB", "HELD"),
    ("***", "CN", "", "", "CANCELLED"),
    ("***", "Z1", "", "", "OLD FC400 CODE"),
    ("***", "Z9", "", "", "DO NOT USE"),
]

AGENT_REPLY = {
    "status": ["Hi {f}, {pro} is {sts}. {eta}", "Thanks {f}. I checked {pro}: {sts}. {eta}", "{f}, sorry for the trouble. {pro} is {sts}. {eta}"],
    "pickup": ["Hi {f}, pickup is scheduled, confirmation {conf}.", "Pickup booked for you, conf# {conf}. Driver will arrive before close."],
    "invoice": ["Hi {f}, I've forwarded this to our billing team, they'll reply within 2 business days.", "Attached is the invoice copy you asked for."],
    "reweigh": ["Hi {f}, the reweigh on {pro} was done at our terminal. I've asked billing to review and send the inspection record.", "Your dispute on {pro} has been sent to billing for review."],
    "pod": ["Hi {f}, the POD for {pro} is attached.", "Attached. Signed by {pod}."],
    "claim": ["Hi {f}, please send claims to claims@larkspurfreight.example with the BOL, invoice and photos.", "Your claim has been forwarded to our claims department."],
    "appointment": ["Appointment set for {pro}.", "Hi {f}, the terminal will call the consignee to set the appointment."],
    "other": ["Hi {f}, thanks for reaching out. I've passed this to the right team.", "Our sales team will contact you."],
}
STS_TXT = {"PU": "picked up", "AR": "at our origin terminal", "LH": "in transit", "BB": "at our Indianapolis hub", "AD": "at the delivering terminal",
           "OD": "out for delivery today", "DL": "delivered", "DX": "delivered", "DY": "delayed", "AP": "scheduled for an appointment", "RF": "refused by the consignee"}


class Rows:
    def __init__(self):
        self.t = defaultdict(list)

    def add(self, table, row):
        self.t[table].append(row)


def materialize(plan: sim.Plan, m: sim.Master, until: datetime, rows: Rows, claim_seq: list, inv_seq: list, rng: random.Random):
    """Apply every timeline item up to `until`; return the shipment's final state row."""
    row = dict(plan.row)
    scen = m.scen
    rwg = None
    for ts, kind, d in plan.timeline:
        if ts > until:
            break
        if kind in ("evt", "dlv"):
            rows.add("shpevt", (row["shppro"], d["cd"], d.get("rsn") or "", d["trm"], ts, d.get("usr", "")))
            row.update(shpstscd=d["cd"], shpstsdt=ts, shptrm=d["trm"], shpupd=ts)
            if d["cd"] == "AP":
                row["shpapt"] = sim.at(row["shpeta"], 10)
            if kind == "dlv":
                row.update(shpdlvdt=ts, shppod=d["pod"], shpexc="Y" if d["cd"] == "DX" else "N")
        elif kind == "rwg":
            rwg = d
            rows.add("rwglog", (row["shppro"], d["trm"], d["src"], d["ow"], d["nw"], d["ocf"], d["ncf"], d["ocl"], d["ncl"], ts))
            rows.add("shpevt", (row["shppro"], "RW", "", d["trm"], ts, "DIM" + d["trm"] if d["src"] == "D" else "SCALE"))
            row.update(shpwgt=d["nw"], shpcuf=d["ncf"], shpcls=d["ncl"])
        elif kind == "osd":
            rows.add("osdrec", (row["shppro"], d["typ"], d["trm"], ts.date(), d["pcs"], d["con"], "CONCEALED DMG RPTD BY CONS" if d["con"] else ("DMG AT DLV" if d["typ"] == "D" else "SHORT AT DLV")))
        elif kind == "claim":
            claim_seq[0] += 1
            clmno = f"C{claim_seq[0]:07d}"
            filed = ts.date()
            recent = filed >= date(2026, 9, 1)
            late_p = scen["claims"]["ack_late_rate_recent"] if recent else scen["claims"]["ack_late_rate"]
            ack = filed + timedelta(days=rng.randint(31, 58) if rng.random() < late_p else rng.randint(2, 27))
            res_days = max(20, int(rng.lognormvariate(math.log(scen["claims"]["mean_resolution_days"]) - 0.08, 0.4)))
            resd = filed + timedelta(days=res_days)
            u = until.date()
            if resd <= u:
                outcome = rng.choices(["P", "D", "S"], [0.55, 0.2, 0.25])[0]
                paid = d["amt"] if outcome == "P" else round(d["amt"] * rng.uniform(0.4, 0.8), 2) if outcome == "S" else 0
                sts, ack_v, res_v = outcome, ack, resd
            else:
                paid, res_v = None, None
                ack_v = ack if ack <= u else None
                sts = "I" if ack_v else "N"
            rows.add("clmmst", (clmno, row["shppro"], row["shpshp"], d["typ"], filed, d["amt"], sts, ack_v, res_v, paid, until))
            n_notes = rng.randint(0, 4)
            for k in range(n_notes):
                nts = sim.at(filed + timedelta(days=rng.randint(0, max(1, (min(u, resd) - filed).days))), rng.uniform(8, 16))
                if nts <= until:
                    rows.add("clmnote", (clmno, nts, rng.choice(sim.CLAIMS_STAFF).upper(), rng.choice(["RCVD CLM PKT", "REQ INSP RPT FROM TRM", "CUST CALLED STATUS", "PHOTOS REC'D", "WAITING ON INVOICE COPY", "SENT TO INS CO", "DECLINE RECOMMENDED CLEAN DR", "OFFER 60% SALVAGE"])))
            row["_claim"] = clmno
        elif kind == "inv":
            inv_seq[0] += 1
            invno = f"LF{inv_seq[0]:08d}"
            cus = m.by_no.get(row["shpbto"]) or m.by_no[row["shpshp"]]
            acc = [a for a in row["shpacc"].split(",") if a]
            net, acc_amt, fsc = fr.rate(row["shpwgt"], row["shpcls"], geo.zone(row["shporg"], row["shpdst"]), cus.discount, acc)
            fee = fr.REWEIGH_FEE if rwg else 0.0
            amt = round(net + acc_amt + fsc + fee, 2)
            sts = "P" if ts.date() < until.date() - timedelta(days=30) and rng.random() < 0.9 else "O"
            rows.add("invhdr", (invno, row["shppro"], row["shpbto"], ts.date(), amt, fsc, sts, "Y" if rwg else "N", ts))
            rows.add("invdtl", (invno, 1, "LH", net))
            ln = 2
            for a in acc:
                rows.add("invdtl", (invno, ln, a, fr.ACCESSORIALS[a][1])); ln += 1
            rows.add("invdtl", (invno, ln, "FSC", fsc)); ln += 1
            if fee:
                rows.add("invdtl", (invno, ln, "RWFE", fee))
            row["_inv"] = invno
            row["shpchg"] = amt
    return row


def build(m: sim.Master, start: date, end: date, scale: float = 1.0, seed: int | None = None):
    scen = m.scen
    seed = seed or scen["seed"]
    until = datetime.combine(end, datetime.max.time()).replace(microsecond=0)
    pros = sim.ProCounter()
    rows = Rows()
    plans: list[sim.Plan] = []
    d = start
    seq = 0
    while d <= end:
        rng = sim.day_rng(seed, d, "ship")
        n = int(round(scen["volume"]["shipments_per_weekday"] * sim.WEEKDAY_FACTOR[d.weekday()] * scale))
        for _ in range(n):
            seq += 1
            plans.append(sim.plan_shipment(rng, d, m, pros, seq))
        d += timedelta(days=1)
    rng = random.Random(seed + 7)
    claim_seq, inv_seq = [0], [0]
    finals = []
    for p in plans:
        finals.append(materialize(p, m, until, rows, claim_seq, inv_seq, rng))
    tickets = make_contacts(m, plans, finals, start, until, scale, rng)
    return plans, finals, rows, tickets, pros


def make_contacts(m, plans, finals, start, until, scale, rng):
    scen = m.scen
    weeks = ((until.date() - start).days + 1) / 7
    total = int(scen["volume"]["contacts_per_week"] * weeks * scale)
    tickets = []
    calib = {}
    for cat, share in scen["contact_mix"].items():
        want = int(total * share)
        if cat == "other":
            while sum(1 for t in tickets if t["cat"] == "other") < want:
                c = m.pick_customer(rng)
                f, l, e, p = rng.choice(c.contacts)
                sender = dict(first=f, last=l, email=e, phone=p, company=c.name, cusno=c.cusno)
                day = start + timedelta(days=rng.randint(0, (until.date() - start).days))
                if day.weekday() >= 5:
                    continue
                created = sim.at(day, rng.uniform(8, 17))
                subj, body = ct.render(rng, "other", dict(pro="", bol="", po="", city=rng.choice(geo.SERVICE[rng.choice(geo.TERMINAL_CODES)])[0]), sender)
                tickets.append(_ticket(rng, "other", None, sender, created, until, subj, body, None))
            continue
        weights = [p.weights.get(cat, 0.0) for p in plans]
        calib[cat] = want / max(1e-9, sum(weights))
        if not sum(weights):
            continue
        import bisect, itertools
        cum = list(itertools.accumulate(weights))
        made, tries = 0, 0
        while made < want and tries < want * 8:
            tries += 1
            i = min(bisect.bisect_left(cum, rng.random() * cum[-1]), len(plans) - 1)
            p, fin = plans[i], finals[i]
            created = sim.contact_time(rng, cat, p)
            if not created or created > until or created.date() < start:
                continue
            sender = sim.sender_for(rng, m, p, cat)
            slots = sim.contact_slots(rng, p, m, cat)
            slots.update(inv=fin.get("_inv", ""), clm=fin.get("_claim", ""))
            tickets.append(_ticket(rng, cat, p, sender, created, until, None, None, slots, fin))
            made += 1
    calib_daily = {k: v for k, v in calib.items()}
    return tickets, calib_daily


def _ticket(rng, cat, plan, sender, created, until, subj, body, slots, fin=None):
    channel = rng.choices(["email", "phone", "portal"], [0.7, 0.2, 0.1])[0]
    if subj is None:
        if channel == "phone":
            subj, body = ct.phone_note(rng, cat, slots, sender)
        else:
            subj, body = ct.render(rng, cat, slots, sender)
    agent = rng.choice(sim.AGENTS)
    if channel == "phone":
        first = created
    else:
        first = created + timedelta(hours=min(96, rng.lognormvariate(math.log(9), 0.9)))
    age = (until - created).total_seconds() / 86400
    msgs = [("customer" if channel != "phone" else "agent", sender["first"] + " " + sender["last"] if channel != "phone" else agent, body, created)]
    status, solved, reopened = "new", None, 0
    if first <= until:
        fin = fin or {}
        reply = rng.choice(AGENT_REPLY[cat]).format(
            f=sender["first"], pro=(plan.row["shppro"] if plan else ""), sts=STS_TXT.get(fin.get("shpstscd") or "", "in our system"),
            eta=("Estimated delivery " + plan.row["shpeta"].strftime("%b %d") + ".") if plan else "",
            conf=f"P{rng.randint(1000000, 9999999)}", pod=fin.get("shppod") or "the receiver")
        if channel != "phone":
            msgs.append(("agent", agent, reply, first))
        status = "open"
        if age > 3:
            solved = first + timedelta(hours=rng.uniform(0.1, 30))
            status = "solved" if age < 10 else "closed"
            if rng.random() < 0.08:
                reopened = 1
                msgs.append(("customer", sender["first"] + " " + sender["last"], rng.choice(["This still isn't resolved.", "Following up, no update yet.", "Freight still not here.", "The invoice is still wrong."]), solved + timedelta(hours=rng.uniform(4, 60))))
        elif rng.random() < 0.4:
            status = "pending"
    tags = [cat] if rng.random() < 0.55 else []  # agents tag about half the time
    return dict(channel=channel, email=sender["email"], name=sender["first"] + " " + sender["last"], company=sender["company"],
                subject=subj, status=status, assignee=agent if first <= until else None, tags=tags, created=created,
                first=first if first <= until else None, solved=solved if solved and solved <= until else None,
                reopened=reopened, msgs=[mm for mm in msgs if mm[3] <= until], cat=cat,
                pro=plan.row["shppro"] if plan else None)
