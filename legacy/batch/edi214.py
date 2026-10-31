# EDI 214 outbound - runs 12:00 and 18:00 (was 4x a day until 2018, translator license)
# builds X12 4010 214s per trading partner from FC events since last run
# map names come from ediprt.edimap; translator only has the maps in /edi/maps
# jw 2019-03 terminal override rows in stsxrf for TOL/GRY new handhelds
import os
import sys
from datetime import datetime

import psycopg

DSN = os.environ.get("DATABASE_URL", "postgresql:///larkspur")
EDI = os.environ.get("EDI_DIR", "/srv/larkspur/edi")
MAPS = {"LKSF214V3"}  # V2 retired in the 2024 translator upgrade
SCAC = "LKSF"


def run(now=None):
    now = now or datetime.now()
    os.makedirs(f"{EDI}/out", exist_ok=True)
    os.makedirs(f"{EDI}/log", exist_ok=True)
    log = open(f"{EDI}/log/translator.log", "a")
    with psycopg.connect(DSN, autocommit=True) as c:
        r = c.execute("select ctlval from fc.sysctl where ctlkey='EDI214_LAST'").fetchone()
        last = datetime.fromisoformat(r[0]) if r else now.replace(hour=0, minute=0)
        xrf = {}
        for t, cd, edi, rsn in c.execute("select xrftrm, xrfcd, xrfedi, xrfrsn from fc.stsxrf"):
            xrf[(t, cd)] = (edi.strip(), rsn.strip())
        down = c.execute("select ctlval from fc.sysctl where ctlkey='EDI_PARTNER_DOWN'").fetchone()
        parts = c.execute("select ediid, edicus, edimap from fc.ediprt where edi214='Y'").fetchall()
        ctrl = int(now.strftime("%y%j%H")) * 10
        sent = 0
        for ediid, cus, emap in parts:
            if emap not in MAPS:
                log.write(f"{now:%Y-%m-%d %H:%M:%S} E0412 MAP {emap} NOT FOUND PARTNER {ediid} SKIPPED\n")
                continue
            if down and down[0] == cus:
                log.write(f"{now:%Y-%m-%d %H:%M:%S} E0207 AS2 CONNECT TIMEOUT PARTNER {ediid}\n")
                continue
            rows = c.execute(
                "select e.evtpro, e.evtcd, e.evtrsn, e.evttrm, e.evtts, s.shpbol, s.shppo, s.shpwgt, s.shppcs, s.shpcnm, s.shpcct, s.shpcst "
                "from fc.shpevt e join fc.shpmst s on s.shppro=e.evtpro where s.shpshp=%s and e.evtts>%s and e.evtts<=%s order by e.evtts",
                (cus, last, now)).fetchall()
            if not rows:
                continue
            ctrl += 1
            segs = []
            for i, (pro, cd, rsn, trm, ts, bol, po, wgt, pcs, cnm, cct, cst) in enumerate(rows, start=1):
                edi, drsn = xrf.get((trm, cd)) or xrf.get(("***", cd)) or ("", "")
                if not edi:
                    continue
                segs += [f"ST*214*{i:04d}~", f"B10*{pro}*{bol}*{SCAC}~", f"L11*{bol}*BM~"]
                if po:
                    segs.append(f"L11*{po}*PO~")
                segs += [f"N1*CN*{cnm}~", f"N4*{cct}*{cst}~", "LX*1~",
                         f"AT7*{edi}*{(rsn or drsn or 'NS').strip()}***{ts:%Y%m%d}*{ts:%H%M}*ET~",
                         f"MS1*{cct}*{cst}*US~", f"AT8*G*L*{wgt}*{pcs}~", f"SE*{10 if po else 9}*{i:04d}~"]
            if not segs:
                continue
            isa = f"ISA*00*          *00*          *02*{SCAC:<15}*ZZ*{ediid:<15}*{now:%y%m%d}*{now:%H%M}*U*00401*{ctrl:09d}*0*P*>~"
            body = "\n".join([isa, f"GS*QM*{SCAC}*{ediid}*{now:%Y%m%d}*{now:%H%M}*{ctrl}*X*004010~"] + segs +
                             [f"GE*{sum(1 for s in segs if s.startswith('ST*'))}*{ctrl}~", f"IEA*1*{ctrl:09d}~"])
            with open(f"{EDI}/out/214_{ediid}_{now:%Y%m%d%H%M}.x12", "w") as f:
                f.write(body + "\n")
            sent += 1
        c.execute("insert into fc.sysctl values ('EDI214_LAST', %s, now()) on conflict (ctlkey) do update set ctlval=excluded.ctlval, ctlupd=now()", (now.isoformat(timespec="minutes"),))
    log.write(f"{now:%Y-%m-%d %H:%M:%S} I0100 214 RUN COMPLETE FILES {sent}\n")
    log.close()
    return sent


if __name__ == "__main__":
    print(run(datetime.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else None))
