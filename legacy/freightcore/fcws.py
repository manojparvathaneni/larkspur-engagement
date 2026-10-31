# FCWS - FreightCore Web Service
# rk 2014-05 initial (trace, quote) for customer portal + EDI partners
# rk 2014-09 schedulePickup for web pickups
# pm 2016-01 moved off old box, same contract, DO NOT CHANGE WSDL (partners hardcoded it)
# pm 2017-03 limit workers, db kept falling over at month end
# jw 2019-11 quote: use zip3 table not terminal svc file (reverted, see below)
#
# NOTE: status codes returned are FC internal codes. partners map them themselves.

import os
import random
import threading
import time
from datetime import date, datetime, timedelta

import psycopg
from fastapi import FastAPI, Request
from starlette.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, Response
from lxml import etree

import rating

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

DSN = os.environ.get("DATABASE_URL", "postgresql:///larkspur")
FCWS_USER = os.environ.get("FCWS_USER", "LKSFWEB")
FCWS_PASS = os.environ.get("FCWS_PASSWORD", "changeme")
NS = "http://www.larkspurfreight.example/fcws/2014"
SOAPNS = "http://schemas.xmlsoap.org/soap/envelope/"

_workers = threading.BoundedSemaphore(5)  # pm 2017-03 was 20
WSDL = open(os.path.join(os.path.dirname(__file__), "FreightCoreService.wsdl")).read()


def db():
    return psycopg.connect(DSN, autocommit=True)


def ctl(key, default=None):
    try:
        with db() as c:
            r = c.execute("select ctlval from fc.sysctl where ctlkey=%s", (key,)).fetchone()
            return r[0] if r else default
    except Exception:
        return default


def fault(code, msg, http=500):
    body = ('<?xml version="1.0" encoding="UTF-8"?>'
            f'<soap:Envelope xmlns:soap="{SOAPNS}"><soap:Body><soap:Fault>'
            f'<faultcode>soap:Server</faultcode><faultstring>{code} {msg}</faultstring>'
            '</soap:Fault></soap:Body></soap:Envelope>')
    return Response(body, status_code=http, media_type="text/xml; charset=utf-8")


def envelope(inner):
    body = ('<?xml version="1.0" encoding="UTF-8"?>'
            f'<soap:Envelope xmlns:soap="{SOAPNS}" xmlns:fc="{NS}"><soap:Body>{inner}</soap:Body></soap:Envelope>')
    return Response(body, media_type="text/xml; charset=utf-8")


def x(s):
    s = "" if s is None else str(s)
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def txt(node, name):
    el = node.find(f"{{{NS}}}{name}")
    return el.text.strip() if el is not None and el.text else ""


@app.get("/fcws/FreightCoreService")
def wsdl(request: Request):
    if "wsdl" in str(request.url.query).lower():
        return Response(WSDL, media_type="text/xml")
    return HTMLResponse("<html><body><h2>FreightCoreService</h2><p>Hi there, this is a web service!</p></body></html>")


@app.post("/fcws/FreightCoreService")
async def service(request: Request):
    if ctl("FCWS_STATUS", "UP") != "UP":
        return HTMLResponse("<html><head><title>503 Service Unavailable</title></head><body><h1>Service Unavailable</h1>"
                            "<p>The server is temporarily unable to service your request due to maintenance downtime or capacity problems.</p></body></html>", status_code=503)
    raw = await request.body()
    return await run_in_threadpool(_handle, raw)


def _handle(raw):
    # 2017-03 wait for a worker then give up (was 10s then 2s, partners complained about hangs)
    if not _workers.acquire(timeout=1):
        return fault("FC9001", "RESOURCE BUSY TRY LATER")
    try:
        lat = ctl("FCWS_LATENCY_MS")
        time.sleep((int(lat) if lat else random.randint(250, 1300)) / 1000.0)
        try:
            doc = etree.fromstring(raw)
        except Exception:
            return fault("FC0001", "MALFORMED REQUEST")
        hdr = doc.find(f"{{{SOAPNS}}}Header")
        auth = hdr.find(f"{{{NS}}}AuthHeader") if hdr is not None else None
        if auth is None or txt(auth, "UserId") != FCWS_USER or txt(auth, "Password") != FCWS_PASS:
            return fault("FC0401", "NOT AUTHORIZED")
        body = doc.find(f"{{{SOAPNS}}}Body")
        if body is None or len(body) == 0:
            return fault("FC0001", "MALFORMED REQUEST")
        op = body[0]
        name = etree.QName(op).localname
        if name == "Trace":
            return trace(op)
        if name == "GetQuote":
            return get_quote(op)
        if name == "SchedulePickup":
            return schedule_pickup(op)
        return fault("FC0004", "UNKNOWN OPERATION " + name)
    except psycopg.Error:
        return fault("FC9002", "DB ERROR SQLSTATE 57014")
    finally:
        _workers.release()


def trace(op):
    pro = txt(op, "ProNumber").replace("-", "")
    bol = txt(op, "BolNumber")
    with db() as c:
        if pro:
            r = c.execute("select * from fc.shpmst where shppro=%s", (pro,)).fetchone()
        elif bol:
            r = c.execute("select * from fc.shpmst where shpbol=%s order by shpdt desc limit 1", (bol,)).fetchone()
        else:
            return fault("FC0002", "PRO OR BOL REQUIRED")
        if not r:
            return fault("FC0042", "RECORD NOT FOUND")
        cols = [d.name for d in c.execute("select * from fc.shpmst limit 0").description]
        s = dict(zip(cols, r))
        ev = c.execute("select evtcd, evtrsn, evttrm, evtts from fc.shpevt where evtpro=%s order by evtts desc limit 10", (s["shppro"],)).fetchall()
    evx = "".join(f"<fc:Event><fc:Code>{e[0]}</fc:Code><fc:Reason>{x(e[1])}</fc:Reason><fc:Terminal>{e[2]}</fc:Terminal>"
                  f"<fc:Timestamp>{e[3].strftime('%Y-%m-%dT%H:%M:%S')}</fc:Timestamp></fc:Event>" for e in ev)
    # TODO jw: return consignee? partners asked. legal said no (2019)
    inner = (f"<fc:TraceResponse><fc:ProNumber>{s['shppro']}</fc:ProNumber><fc:BolNumber>{x(s['shpbol'])}</fc:BolNumber>"
             f"<fc:PickupDate>{s['shpdt']}</fc:PickupDate><fc:Origin>{s['shporg']}</fc:Origin><fc:Destination>{s['shpdst']}</fc:Destination>"
             f"<fc:Pieces>{s['shppcs']}</fc:Pieces><fc:Weight>{s['shpwgt']}</fc:Weight>"
             f"<fc:StatusCode>{x(s['shpstscd'])}</fc:StatusCode><fc:StatusDate>{s['shpstsdt'].strftime('%Y-%m-%dT%H:%M:%S') if s['shpstsdt'] else ''}</fc:StatusDate>"
             f"<fc:CurrentTerminal>{x(s['shptrm'])}</fc:CurrentTerminal><fc:EstimatedDelivery>{s['shpeta'] or ''}</fc:EstimatedDelivery>"
             f"<fc:DeliveredDate>{s['shpdlvdt'].strftime('%Y-%m-%dT%H:%M:%S') if s['shpdlvdt'] else ''}</fc:DeliveredDate>"
             f"<fc:SignedBy>{x(s['shppod'])}</fc:SignedBy><fc:Events>{evx}</fc:Events></fc:TraceResponse>")
    return envelope(inner)


def get_quote(op):
    try:
        oz, dz = txt(op, "OriginZip")[:5], txt(op, "DestinationZip")[:5]
        cls = float(txt(op, "Class") or 0)
        wgt = int(float(txt(op, "Weight") or 0))
    except ValueError:
        return fault("FC0003", "INVALID NUMERIC FIELD")
    acc = [a.strip().upper() for a in txt(op, "Accessorials").split(",") if a.strip()]
    org, dst = rating.terminal_for_zip(oz), rating.terminal_for_zip(dz)
    if not org or not dst:
        return fault("FC0210", "POINT NOT SERVED")
    if wgt <= 0 or wgt > 20000:
        return fault("FC0112", "WEIGHT OUT OF RANGE")
    if cls not in rating.CLASSES:
        return fault("FC0113", "INVALID CLASS")
    q = rating.quote(org, dst, cls, wgt, acc)
    inner = (f"<fc:GetQuoteResponse><fc:QuoteNumber>Q{random.randint(10000000, 99999999)}</fc:QuoteNumber>"
             f"<fc:OriginTerminal>{org}</fc:OriginTerminal><fc:DestinationTerminal>{dst}</fc:DestinationTerminal>"
             f"<fc:TransitDays>{q['transit']}</fc:TransitDays><fc:Linehaul>{q['net']:.2f}</fc:Linehaul>"
             f"<fc:Accessorials>{q['acc']:.2f}</fc:Accessorials><fc:FuelSurcharge>{q['fsc']:.2f}</fc:FuelSurcharge>"
             f"<fc:Total>{q['total']:.2f}</fc:Total><fc:ValidThrough>{(date.today() + timedelta(days=30)).isoformat()}</fc:ValidThrough></fc:GetQuoteResponse>")
    return envelope(inner)


def schedule_pickup(op):
    acct = txt(op, "AccountNumber").zfill(8)
    try:
        pdate = date.fromisoformat(txt(op, "PickupDate"))
        ready = datetime.strptime(txt(op, "ReadyTime"), "%H:%M").time()
        close = datetime.strptime(txt(op, "CloseTime"), "%H:%M").time()
        pcs, wgt = int(txt(op, "Pieces")), int(txt(op, "Weight"))
    except ValueError:
        return fault("FC0003", "INVALID FIELD FORMAT")
    now = datetime.now()
    if pdate < now.date():
        return fault("FC0105", "PICKUP DATE IN PAST")
    if pdate == now.date() and now.hour >= 16:
        return fault("FC0107", "SAME DAY CUTOFF 1600 PASSED")
    if ready >= close or (datetime.combine(pdate, close) - datetime.combine(pdate, ready)).seconds < 7200:
        return fault("FC0108", "PICKUP WINDOW MIN 2 HRS")
    if wgt > 10000 or pcs > 12:
        return fault("FC0112", "OVER LTL MAX CALL DISPATCH")
    with db() as c:
        if not c.execute("select 1 from fc.cusmst where cusno=%s", (acct,)).fetchone():
            return fault("FC0042", "ACCOUNT NOT FOUND")
        conf = "P" + str(random.randint(1000000, 9999999))
        # no dupe check, dispatch catches dupes (usually)
        c.execute("insert into fc.pkureq (pkuconf, pkucus, pkudt, pkurdy, pkucls, pkupcs, pkuwgt, pkusrc, pkusts, pkucrt) "
                  "values (%s,%s,%s,%s,%s,%s,%s,'S','O',now())", (conf, acct, pdate, ready, close, pcs, wgt))
    return envelope(f"<fc:SchedulePickupResponse><fc:ConfirmationNumber>{conf}</fc:ConfirmationNumber>"
                    f"<fc:PickupDate>{pdate}</fc:PickupDate></fc:SchedulePickupResponse>")
