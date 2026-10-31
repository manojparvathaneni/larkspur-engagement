# NIGHTLY - shipment + invoice extracts for finance and the customer portal
# fixed width per layouts/SHPEXT.TXT and layouts/INVEXT.TXT. DO NOT change widths, finance macro reads by position
# portal reads SHPEXT so portal tracking is as of last night (known, ticket 4471 closed wontfix)
import os
import sys
from datetime import datetime, timedelta

import psycopg

DSN = os.environ.get("DATABASE_URL", "postgresql:///larkspur")
OUT = os.environ.get("EXTRACT_DIR", "/srv/larkspur/extracts")


def f(v, n, num=False):
    s = "" if v is None else str(v)
    return s[:n].rjust(n, "0") if num else s[:n].ljust(n)


def run(now=None):
    now = now or datetime.now()
    os.makedirs(OUT, exist_ok=True)
    since = now - timedelta(days=14)
    n_s = n_i = 0
    with psycopg.connect(DSN) as c:
        with open(f"{OUT}/SHPEXT.{now:%Y%m%d}", "w") as out:
            for r in c.execute("select shppro, shpbol, shppo, shpdt, shporg, shpdst, shpshp, shpcnm, shpcct, shpcst, shpczp, shpbto, shppcs, shpwgt, shpcls, shpchg, shpstscd, shpstsdt, shpeta, shpdlvdt, shppod "
                               "from fc.shpmst where coalesce(shpupd, shpdt) >= %s order by shppro", (since,)):
                pro, bol, po, dt, org, dst, shp, cnm, cct, cst, czp, bto, pcs, wgt, cls, chg, sts, stsdt, eta, dlv, pod = r
                out.write("".join([f(pro, 9), f(bol, 15), f(po, 15), f(dt.strftime("%Y%m%d") if dt else "", 8), f(org, 3), f(dst, 3), f(shp, 8),
                                   f(cnm, 30), f(cct, 20), f(cst, 2), f(czp, 5), f(bto, 8), f(pcs, 4, True), f(wgt, 6, True),
                                   f(int(float(cls) * 10) if cls else 0, 4, True), f(int(float(chg or 0) * 100), 9, True), f(sts, 2),
                                   f(stsdt.strftime("%Y%m%d%H%M") if stsdt else "", 12), f(eta.strftime("%Y%m%d") if eta else "", 8),
                                   f(dlv.strftime("%Y%m%d%H%M") if dlv else "", 12), f(pod, 20)]) + "\n")
                n_s += 1
        with open(f"{OUT}/INVEXT.{now:%Y%m%d}", "w") as out:
            for r in c.execute("select invno, invpro, invbto, invdt, invamt, invfsc, invsts, invrbl from fc.invhdr where invupd >= %s order by invno", (since,)):
                invno, pro, bto, dt, amt, fsc, sts, rbl = r
                out.write("".join([f(invno, 10), f(pro, 9), f(bto, 8), f(dt.strftime("%Y%m%d"), 8), f(int(float(amt) * 100), 9, True),
                                   f(int(float(fsc) * 100), 7, True), f(sts, 1), f(rbl, 1)]) + "\n")
                n_i += 1
        c.execute("insert into fc.sysctl values ('BATCH_LAST', %s, now()) on conflict (ctlkey) do update set ctlval=excluded.ctlval, ctlupd=now()", (now.date().isoformat(),))
        c.commit()
    return n_s, n_i


if __name__ == "__main__":
    print(run(datetime.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else None))
