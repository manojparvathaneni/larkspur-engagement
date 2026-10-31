"""larkspur world: runs Larkspur's business forward on a real clock, Eastern time.

    python -m larkspur_world.engine run            # live, forever
    python -m larkspur_world.engine run --until 2026-11-09T00:00 --fast   # simulate ahead quickly

Each day it plans the day's shipments from a seed derived from the date, then applies
every planned event when its time comes: status scans, reweighs, deliveries, damage,
claims, invoices and the customer emails they cause. Larkspur's own agents answer
tickets at their usual pace. Batch jobs run on schedule, and the sealed incident
calendar switches incidents on and off.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import sys
import time as _time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import psycopg

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "data"), str(ROOT / "legacy" / "batch")]

from larkspur_data import contacts as ct  # noqa: E402
from larkspur_data import freight as fr  # noqa: E402
from larkspur_data import geo, history, scenario, sim  # noqa: E402

ET = ZoneInfo("America/New_York")
DSN = os.environ.get("DATABASE_URL", "postgresql:///larkspur")
DESKLINE = os.environ.get("DESKLINE_URL")
DESKLINE_TOKEN = os.environ.get("DESKLINE_TOKEN")
AGENTS_ON = os.environ.get("WORLD_AGENTS", "on") == "on"


def now_et() -> datetime:
    return datetime.now(ET).replace(tzinfo=None, microsecond=0)


class World:
    def __init__(self, conn):
        self.c = conn
        self.scen = scenario.load()
        self.m = sim.Master(self.scen)
        st = self.c.execute("select v from sim.state where k='world'").fetchone()[0]
        self.st = st
        self.scale = float(os.environ.get("WORLD_SCALE", self.scen["world"]["scale"]))
        self.pros = sim.ProCounter()
        self.pros.next = {k: int(v) for k, v in st["pro_next"].items()}
        self.http = httpx.Client(timeout=5) if DESKLINE and DESKLINE_TOKEN else None

    def save(self):
        self.st["pro_next"] = self.pros.next
        self.c.execute("update sim.state set v=%s where k='world'", (json.dumps(self.st, default=str),))

    # planning ---------------------------------------------------------------
    def plan_day(self, d: date):
        if self.st.get("planned_through", "") >= d.isoformat():
            return 0
        rng = sim.day_rng(self.scen["seed"], d, "world")
        n = int(round(self.scen["volume"]["shipments_per_weekday"] * sim.WEEKDAY_FACTOR[d.weekday()] * self.scale))
        calib = self.st["calib"]
        rows = []
        for _ in range(n):
            self.st["seq"] = self.st.get("seq", 0) + 1
            p = sim.plan_shipment(rng, d, self.m, self.pros, self.st["seq"])
            r = {k: (v.isoformat() if isinstance(v, (date, datetime)) else v) for k, v in p.row.items()}
            rows.append((p.timeline[0][0] - timedelta(minutes=1), "ship", p.row["shppro"], json.dumps(r)))
            for ts, kind, data in p.timeline:
                rows.append((ts, kind, p.row["shppro"], json.dumps(data)))
            for cat, w in p.weights.items():
                if w and rng.random() < min(0.95, w * calib.get(cat, 0)):
                    when = sim.contact_time(rng, cat, p)
                    if when:
                        rows.append((when, "contact", p.row["shppro"], json.dumps(self._contact(rng, cat, p))))
        # contacts with no shipment behind them
        for _ in range(int(self.scen["volume"]["contacts_per_week"] / 5 * self.scen["contact_mix"]["other"] * self.scale * (d.weekday() < 5))):
            c = self.m.pick_customer(rng)
            f, l, e, ph = rng.choice(c.contacts)
            sender = dict(first=f, last=l, email=e, phone=ph, company=c.name, cusno=c.cusno)
            subj, body = ct.render(rng, "other", dict(pro="", bol="", po="", city="Toledo"), sender)
            rows.append((sim.at(d, rng.uniform(8, 17)), "contact", None, json.dumps(dict(cat="other", channel="email", sender=sender, subject=subj, body=body))))
        with self.c.cursor() as cur:
            with cur.copy("copy sim.plan (due, kind, pro, payload) from stdin") as cp:
                for r in rows:
                    cp.write_row(r)
        self.st["planned_through"] = d.isoformat()
        self.save()
        return n

    def _contact(self, rng, cat, p):
        sender = sim.sender_for(rng, self.m, p, cat)
        slots = sim.contact_slots(rng, p, self.m, cat)
        channel = rng.choices(["email", "phone", "portal"], [0.7, 0.2, 0.1])[0]
        subj, body = (ct.phone_note if channel == "phone" else ct.render)(rng, cat, slots, sender)
        return dict(cat=cat, channel=channel, sender=sender, subject=subj, body=body)

    # applying ---------------------------------------------------------------
    def step(self, upto: datetime) -> int:
        items = self.c.execute("select id, due, kind, pro, payload from sim.plan where not done and due <= %s order by due, id limit 5000", (upto,)).fetchall()
        rng = random.Random(int(upto.timestamp()))
        for pid, due, kind, pro, d in items:
            getattr(self, "do_" + kind)(due, pro, d, rng)
            self.c.execute("update sim.plan set done=true where id=%s", (pid,))
        return len(items)

    def do_ship(self, ts, pro, r, rng):
        cols = list(r.keys())
        vals = [r[k] for k in cols]
        for k in ("shpcnm", "shpcad", "shpcct"):
            vals[cols.index(k)] = (r[k] or "").upper()[:40 if k != "shpcct" else 30]
        self.c.execute(f"insert into fc.shpmst ({', '.join(cols)}) values ({', '.join(['%s'] * len(cols))}) on conflict do nothing", vals)
        self.c.execute("insert into fc.pkureq (pkuconf, pkucus, pkudt, pkurdy, pkucls, pkupcs, pkuwgt, pkusrc, pkusts, pkupro, pkucrt) values (%s,%s,%s,'10:00','16:00',%s,%s,%s,'C',%s,%s)",
                       ("P" + str(rng.randint(1000000, 9999999)), r["shpshp"], r["shpdt"], r["shppcs"], r["shpwgt"], rng.choice("WPS"), pro, ts - timedelta(hours=5)))

    def do_evt(self, ts, pro, d, rng):
        self.c.execute("insert into fc.shpevt (evtpro, evtcd, evtrsn, evttrm, evtts, evtusr) values (%s,%s,%s,%s,%s,%s)", (pro, d["cd"], d.get("rsn") or "", d["trm"], ts, d.get("usr", "")))
        extra = ", shpapt=shpeta + time '10:00'" if d["cd"] == "AP" else ""
        self.c.execute(f"update fc.shpmst set shpstscd=%s, shpstsdt=%s, shptrm=%s, shpupd=%s{extra} where shppro=%s", (d["cd"], ts, d["trm"], ts, pro))

    def do_dlv(self, ts, pro, d, rng):
        self.do_evt(ts, pro, d, rng)
        self.c.execute("update fc.shpmst set shpdlvdt=%s, shppod=%s, shpexc=%s where shppro=%s", (ts, d["pod"], "Y" if d["cd"] == "DX" else "N", pro))

    def do_rwg(self, ts, pro, d, rng):
        self.c.execute("insert into fc.rwglog (rwgpro, rwgtrm, rwgsrc, rwgow, rwgnw, rwgocf, rwgncf, rwgocl, rwgncl, rwgts) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                       (pro, d["trm"], d["src"], d["ow"], d["nw"], d["ocf"], d["ncf"], d["ocl"], d["ncl"], ts))
        self.c.execute("insert into fc.shpevt (evtpro, evtcd, evtrsn, evttrm, evtts, evtusr) values (%s,'RW','',%s,%s,%s)", (pro, d["trm"], ts, "DIM" + d["trm"] if d["src"] == "D" else "SCALE"))
        self.c.execute("update fc.shpmst set shpwgt=%s, shpcuf=%s, shpcls=%s, shpupd=%s where shppro=%s", (d["nw"], d["ncf"], d["ncl"], ts, pro))

    def do_osd(self, ts, pro, d, rng):
        self.c.execute("insert into fc.osdrec (osdpro, osdtyp, osdtrm, osddt, osdpcs, osdcon, osdnt) values (%s,%s,%s,%s,%s,%s,%s)",
                       (pro, d["typ"], d["trm"], ts.date(), d["pcs"], d["con"], "CONCEALED DMG RPTD BY CONS" if d["con"] else ("DMG AT DLV" if d["typ"] == "D" else "SHORT AT DLV")))

    def do_claim(self, ts, pro, d, rng):
        self.st["claim_seq"] = self.st.get("claim_seq", 0) + 1
        clmno = f"C{self.st['claim_seq']:07d}"
        cus = self.c.execute("select shpshp from fc.shpmst where shppro=%s", (pro,)).fetchone()
        self.c.execute("insert into fc.clmmst (clmno, clmpro, clmcus, clmtyp, clmfld, clmamt, clmsts, clmupd) values (%s,%s,%s,%s,%s,%s,'N',%s)",
                       (clmno, pro, cus[0] if cus else "", d["typ"], ts.date(), d["amt"], ts))
        late = rng.random() < self.scen["claims"]["ack_late_rate_recent"]
        ack = ts + timedelta(days=rng.randint(31, 58) if late else rng.randint(2, 27))
        res = ts + timedelta(days=max(20, int(rng.lognormvariate(math.log(self.scen["claims"]["mean_resolution_days"]), 0.4))))
        self.c.execute("insert into sim.plan (due, kind, pro, payload) values (%s,'clmupd',%s,%s), (%s,'clmupd',%s,%s)",
                       (ack, pro, json.dumps(dict(clm=clmno, sts="A")), res, pro, json.dumps(dict(clm=clmno, sts=rng.choices("PDS", [55, 20, 25])[0], amt=d["amt"]))))
        self.save()

    def do_clmupd(self, ts, pro, d, rng):
        if d["sts"] == "A":
            self.c.execute("update fc.clmmst set clmsts='I', clmack=%s, clmupd=%s where clmno=%s", (ts.date(), ts, d["clm"]))
        else:
            paid = d["amt"] if d["sts"] == "P" else round(d["amt"] * rng.uniform(0.4, 0.8), 2) if d["sts"] == "S" else 0
            self.c.execute("update fc.clmmst set clmsts=%s, clmrsd=%s, clmpd=%s, clmupd=%s where clmno=%s", (d["sts"], ts.date(), paid, ts, d["clm"]))
        self.c.execute("insert into ops.clmnote (nteclm, ntets, nteusr, ntetxt) values (%s,%s,%s,%s)",
                       (d["clm"], ts, rng.choice(sim.CLAIMS_STAFF).upper(), "ACK LTR SENT" if d["sts"] == "A" else {"P": "PAID IN FULL", "D": "DECLINED CLEAN DR", "S": "SETTLED"}[d["sts"]]))

    def do_inv(self, ts, pro, d, rng):
        s = self.c.execute("select shpbto, shpshp, shpwgt, shpcls, shporg, shpdst, shpacc from fc.shpmst where shppro=%s", (pro,)).fetchone()
        if not s:
            return
        bto, shp, wgt, cls, org, dst, acc = s
        cus = self.m.by_no.get(bto) or self.m.by_no.get(shp)
        accs = [a for a in (acc or "").split(",") if a]
        net, acc_amt, fsc = fr.rate(wgt, float(cls), geo.zone(org, dst), cus.discount if cus else 60, accs)
        rw = self.c.execute("select 1 from fc.rwglog where rwgpro=%s", (pro,)).fetchone()
        fee = fr.REWEIGH_FEE if rw else 0
        self.st["inv_seq"] = self.st.get("inv_seq", 0) + 1
        invno = f"LF{self.st['inv_seq']:08d}"
        self.c.execute("insert into fc.invhdr values (%s,%s,%s,%s,%s,%s,'O',%s,%s)", (invno, pro, bto, ts.date(), round(net + acc_amt + fsc + fee, 2), fsc, "Y" if rw else "N", ts))
        lines = [("LH", net)] + [(a, fr.ACCESSORIALS[a][1]) for a in accs] + [("FSC", fsc)] + ([("RWFE", fee)] if fee else [])
        for i, (cd, amt) in enumerate(lines, start=1):
            self.c.execute("insert into fc.invdtl values (%s,%s,%s,%s)", (invno, i, cd, amt))
        self.c.execute("update fc.shpmst set shpchg=%s, shpupd=%s where shppro=%s", (round(net + acc_amt + fsc + fee, 2), ts, pro))
        self.save()

    def do_contact(self, ts, pro, d, rng):
        s = d["sender"]
        payload = dict(channel=d["channel"], requester_email=s["email"], requester_name=f"{s['first']} {s['last']}",
                       requester_company=s["company"], subject=d["subject"], body=d["body"], created_at=ts.replace(tzinfo=ET).isoformat())
        tid = None
        if self.http:
            try:
                r = self.http.post(f"{DESKLINE}/api/v2/tickets", json=payload, headers={"Authorization": f"Bearer {DESKLINE_TOKEN}"})
                tid = r.json()["id"] if r.status_code == 201 else None
            except Exception:
                tid = None
        if tid is None:
            tsz = ts.replace(tzinfo=ET)
            tid = self.c.execute("insert into hd.tickets (channel, requester_email, requester_name, requester_company, subject, status, created_at, updated_at) values (%s,%s,%s,%s,%s,'new',%s,%s) returning id",
                                 (payload["channel"], payload["requester_email"], payload["requester_name"], payload["requester_company"], payload["subject"], tsz, tsz)).fetchone()[0]
            self.c.execute("insert into hd.messages (ticket_id, author_type, author_name, body, created_at) values (%s,%s,%s,%s,%s)",
                           (tid, "agent" if d["channel"] == "phone" else "customer", payload["requester_name"], d["body"], tsz))
        self.c.execute("insert into sim.truth values (%s,%s,%s) on conflict do nothing", (tid, d["cat"], pro))

    # Larkspur's own agents --------------------------------------------------
    def agents(self, now: datetime):
        """The support team answers at its usual pace, 7am to 10pm on weekdays. Tickets the pilot handles are left alone."""
        if not AGENTS_ON or now.weekday() >= 5 or not (7 <= now.hour < 22):
            return
        nz = now.replace(tzinfo=ET)
        rows = self.c.execute("select id, created_at, requester_name, subject from hd.tickets where status in ('new','open') and first_response_at is null "
                              "and not ('pilot' = any(tags)) and created_at <= %s", (nz,)).fetchall()
        for tid, created, name, subj in rows:
            h = int(hashlib.sha256(str(tid).encode()).hexdigest()[:8], 16)
            wait = min(96.0, random.Random(h).lognormvariate(math.log(7.0), 0.9))
            if (nz - created).total_seconds() / 3600 >= wait:
                truth = self.c.execute("select category from sim.truth where ticket_id=%s", (tid,)).fetchone()
                cat = truth[0] if truth else "other"
                body = random.Random(h).choice(history.AGENT_REPLY[cat]).format(f=(name or "there").split()[0], pro="your shipment", sts="in our system", eta="",
                                                                               conf=f"P{h % 9000000 + 1000000}", pod="the receiver")
                self.c.execute("insert into hd.messages (ticket_id, author_type, author_name, body, created_at) values (%s,'agent',%s,%s,%s)", (tid, sim.AGENTS[h % len(sim.AGENTS)], body, nz))
                self.c.execute("update hd.tickets set first_response_at=%s, updated_at=%s, status='pending', assignee=%s where id=%s", (nz, nz, sim.AGENTS[h % len(sim.AGENTS)], tid))
        # solve pending tickets after a while; some come back
        for tid, upd in self.c.execute("select id, updated_at from hd.tickets where status='pending' and not ('pilot' = any(tags)) and updated_at < %s", (nz - timedelta(hours=20),)).fetchall():
            h = int(hashlib.sha256(f"s{tid}".encode()).hexdigest()[:8], 16)
            if h % 100 < 8 and not self.c.execute("select 1 from hd.tickets where id=%s and reopened_count>0", (tid,)).fetchone():
                self.c.execute("insert into hd.messages (ticket_id, author_type, author_name, body, created_at) values (%s,'customer',null,%s,%s)", (tid, "Following up, this still isn't resolved.", nz))
                self.c.execute("update hd.tickets set status='open', reopened_count=reopened_count+1, updated_at=%s where id=%s", (nz, tid))
            else:
                self.c.execute("update hd.tickets set status='solved', solved_at=%s, updated_at=%s where id=%s", (nz, nz, tid))

    # telematics, batch and incidents ----------------------------------------
    def telematics(self, now: datetime):
        last = self.st.get("tel_last")
        if last and datetime.fromisoformat(last) > now - timedelta(minutes=15):
            return
        rows = self.c.execute("""
            select s.shppro, s.shptrm, e.evtts, p.due, p.payload->>'trm'
            from fc.shpmst s
            join lateral (select evtts from fc.shpevt where evtpro=s.shppro and evtcd='LH' order by evtts desc limit 1) e on true
            join lateral (select due, payload from sim.plan where pro=s.shppro and not done and kind='evt' order by due limit 1) p on true
            where s.shpstscd='LH' limit 400""").fetchall()
        lanes = {}
        for pro, frm, dep, arr, to in rows:
            if to and frm != to:
                lanes.setdefault((frm, to, dep.date()), (dep, arr))
        with self.c.cursor() as cur:
            for i, ((frm, to, dd), (dep, arr)) in enumerate(sorted(lanes.items())):
                a, b = geo.TERM[frm], geo.TERM[to]
                f = max(0.0, min(1.0, (now - dep).total_seconds() / max(1, (arr - dep).total_seconds())))
                trk = f"{200 + (hash((frm, to)) % 300):03d}{geo.TERMINALS.index(a):02d}"[:6]
                cur.execute("insert into tel.posn (trkno, posts, poslat, poslon, posspd, posdrv) values (%s,%s,%s,%s,%s,%s)",
                            (trk, now, round(a[6] + (b[6] - a[6]) * f, 5), round(a[7] + (b[7] - a[7]) * f, 5), 0 if f in (0.0, 1.0) else random.randint(52, 66), "DR" if 0 < f < 1 else "ON"))
        self.st["tel_last"] = now.isoformat()

    def batch(self, now: datetime):
        import edi214
        import nightly
        jobs = self.st.setdefault("jobs", {})
        for hhmm, name, fn in [("12:00", "edi214_noon", edi214.run), ("18:00", "edi214_eve", edi214.run), ("02:00", "nightly", nightly.run)]:
            h, mi = map(int, hhmm.split(":"))
            due = now.replace(hour=h, minute=mi, second=0)
            if now >= due and jobs.get(name) != now.date().isoformat():
                try:
                    fn(due)
                    if name.startswith("edi214"):
                        self.c.execute("update fc.ediprt set edilak=%s where edimap='LKSF214V3'", (due + timedelta(minutes=7),))
                except Exception as e:  # batch failures get logged, nobody gets paged
                    print(f"{now} batch {name} failed: {e}", flush=True)
                jobs[name] = now.date().isoformat()

    def incidents(self, now: datetime):
        mods = sim.modifiers(self.scen, now.date())
        down = any(s <= now < e for s, e in mods["outage"])
        top = sorted(self.m.customers, key=lambda c: -c.weight)
        top_edi = next((c.cusno for c in top if c.edi and not c.edi_broken), "")
        for key, val in [("FCWS_STATUS", "DOWN" if down else "UP"), ("FCWS_LATENCY_MS", str(mods["slowdown"]) if mods["slowdown"] else ""),
                         ("EDI_PARTNER_DOWN", top_edi if mods["edi_down"] else "")]:
            self.c.execute("insert into fc.sysctl values (%s,%s,now()) on conflict (ctlkey) do update set ctlval=excluded.ctlval, ctlupd=now()", (key, val))

    def tick(self, now: datetime):
        self.incidents(now)
        for i in range(0, 2):
            self.plan_day(now.date() + timedelta(days=i))
        n = self.step(now)
        self.telematics(now)
        self.agents(now)
        self.batch(now)
        self.st["clock"] = now.isoformat()
        self.save()
        return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "tick"])
    ap.add_argument("--until", help="simulate up to this local time, then stop")
    ap.add_argument("--fast", action="store_true", help="advance simulated time in 15 minute steps without waiting")
    args = ap.parse_args()
    with psycopg.connect(DSN, autocommit=True) as conn:
        w = World(conn)
        if args.fast and args.until:
            t = datetime.fromisoformat(w.st.get("clock") or w.st["history_end"] + "T23:59")
            end = datetime.fromisoformat(args.until)
            while t < end:
                t = min(end, t + timedelta(minutes=15))
                w.tick(t)
            print(f"simulated to {t}", flush=True)
            return
        if args.cmd == "tick":
            print(w.tick(now_et()))
            return
        while True:
            t = now_et()
            try:
                n = w.tick(t)
                if n:
                    print(f"{t} applied {n}", flush=True)
            except psycopg.Error as e:
                print(f"{t} db error {e}", flush=True)
            _time.sleep(60)


if __name__ == "__main__":
    main()
