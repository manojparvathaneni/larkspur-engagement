"""Deskline, the SaaS helpdesk Larkspur's customer service team has used since 2021.

A small stand in with the shape of a real helpdesk API: bearer tokens, pagination,
rate limits, and a webhook on new tickets.
"""
import os
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone

import httpx
import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from psycopg.rows import dict_row
from pydantic import BaseModel

DSN = os.environ.get("DATABASE_URL", "postgresql:///larkspur")
WEBHOOK = os.environ.get("DESKLINE_WEBHOOK_URL")
RATE = int(os.environ.get("DESKLINE_RATE_PER_MIN", "200"))

app = FastAPI(title="Deskline API", version="2.4.1", docs_url="/api/docs", openapi_url="/api/openapi.json")
_hits: dict[str, deque] = defaultdict(deque)
_lock = threading.Lock()


def db():
    return psycopg.connect(DSN, autocommit=True, row_factory=dict_row)


def auth(authorization: str = Header(default="")) -> str:
    token = authorization.removeprefix("Bearer ").strip()
    with db() as c:
        if not token or not c.execute("select 1 from hd.api_tokens where token=%s", (token,)).fetchone():
            raise HTTPException(401, "invalid or missing API token")
    now = time.time()
    with _lock:
        q = _hits[token]
        while q and q[0] < now - 60:
            q.popleft()
        if len(q) >= RATE:
            raise HTTPException(429, "rate limit exceeded", headers={"Retry-After": str(int(60 - (now - q[0])) + 1)})
        q.append(now)
    return token


def _ticket(c, tid: int, with_messages=True):
    t = c.execute("select * from hd.tickets where id=%s", (tid,)).fetchone()
    if not t:
        raise HTTPException(404, "ticket not found")
    if with_messages:
        t["messages"] = c.execute("select id, author_type, author_name, body, created_at from hd.messages where ticket_id=%s order by created_at", (tid,)).fetchall()
    return t


@app.get("/api/v2/tickets")
def list_tickets(status: str | None = None, updated_since: datetime | None = None, created_since: datetime | None = None,
                 page: int = Query(1, ge=1), per_page: int = Query(25, ge=1, le=100), _=Depends(auth)):
    where, args = [], []
    if status:
        where.append("status = any(%s)"); args.append(status.split(","))
    if updated_since:
        where.append("updated_at >= %s"); args.append(updated_since)
    if created_since:
        where.append("created_at >= %s"); args.append(created_since)
    w = ("where " + " and ".join(where)) if where else ""
    with db() as c:
        total = c.execute(f"select count(*) n from hd.tickets {w}", args).fetchone()["n"]
        rows = c.execute(f"select id, channel, requester_email, requester_name, requester_company, subject, status, priority, assignee, tags, created_at, updated_at "
                         f"from hd.tickets {w} order by created_at desc limit %s offset %s", args + [per_page, (page - 1) * per_page]).fetchall()
    return {"tickets": rows, "page": page, "per_page": per_page, "total": total,
            "next_page": page + 1 if page * per_page < total else None}


@app.get("/api/v2/tickets/{tid}")
def get_ticket(tid: int, _=Depends(auth)):
    with db() as c:
        return _ticket(c, tid)


class NewTicket(BaseModel):
    channel: str = "email"
    requester_email: str
    requester_name: str | None = None
    requester_company: str | None = None
    subject: str
    body: str
    created_at: datetime | None = None


@app.post("/api/v2/tickets", status_code=201)
def create_ticket(t: NewTicket, _=Depends(auth)):
    ts = t.created_at or datetime.now(timezone.utc)
    with db() as c:
        tid = c.execute("insert into hd.tickets (channel, requester_email, requester_name, requester_company, subject, status, created_at, updated_at) "
                        "values (%s,%s,%s,%s,%s,'new',%s,%s) returning id", (t.channel, t.requester_email, t.requester_name, t.requester_company, t.subject, ts, ts)).fetchone()["id"]
        c.execute("insert into hd.messages (ticket_id, author_type, author_name, body, created_at) values (%s,'customer',%s,%s,%s)", (tid, t.requester_name, t.body, ts))
        ticket = _ticket(c, tid)
    if WEBHOOK:
        try:
            httpx.post(WEBHOOK, json={"event": "ticket.created", "ticket_id": tid, "created_at": ts.isoformat()}, timeout=3)
        except Exception:
            pass  # Deskline drops failed webhooks after one try, like the real thing on the basic plan
    return ticket


class NewMessage(BaseModel):
    body: str
    author_name: str = "Larkspur Support"
    public: bool = True


@app.post("/api/v2/tickets/{tid}/messages", status_code=201)
def add_message(tid: int, m: NewMessage, _=Depends(auth)):
    now = datetime.now(timezone.utc)
    with db() as c:
        t = _ticket(c, tid, with_messages=False)
        c.execute("insert into hd.messages (ticket_id, author_type, author_name, body, created_at) values (%s,%s,%s,%s,%s)",
                  (tid, "agent" if m.public else "internal", m.author_name, m.body, now))
        c.execute("update hd.tickets set updated_at=%s, first_response_at=coalesce(first_response_at, %s), status=case when status in ('new','open') then 'pending' else status end where id=%s",
                  (now, now if m.public else None, tid))
        return _ticket(c, tid)


class Patch(BaseModel):
    status: str | None = None
    assignee: str | None = None
    tags: list[str] | None = None
    priority: str | None = None


@app.patch("/api/v2/tickets/{tid}")
def update_ticket(tid: int, p: Patch, _=Depends(auth)):
    now = datetime.now(timezone.utc)
    sets, args = ["updated_at=%s"], [now]
    for k in ("status", "assignee", "tags", "priority"):
        v = getattr(p, k)
        if v is not None:
            sets.append(f"{k}=%s"); args.append(v)
    if p.status == "solved":
        sets.append("solved_at=%s"); args.append(now)
    with db() as c:
        _ticket(c, tid, with_messages=False)
        c.execute(f"update hd.tickets set {', '.join(sets)} where id=%s", args + [tid])
        return _ticket(c, tid)


@app.get("/api/v2/search")
def search(q: str, per_page: int = Query(25, le=100), _=Depends(auth)):
    with db() as c:
        rows = c.execute("select distinct t.id, t.subject, t.status, t.created_at from hd.tickets t join hd.messages m on m.ticket_id=t.id "
                         "where t.subject ilike %s or m.body ilike %s order by t.created_at desc limit %s", (f"%{q}%", f"%{q}%", per_page)).fetchall()
    return {"results": rows}


@app.get("/")
def ui():
    return FileResponse(os.path.join(os.path.dirname(__file__), "index.html"))
