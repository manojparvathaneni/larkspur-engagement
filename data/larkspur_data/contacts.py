"""Customer contact text. Templates with slots, tone, missing references, typos and threads,
so the words vary the way real support email does."""
import random

GREET = ["Hi,", "Hello,", "Good morning,", "Hi team,", "Hello Larkspur,", "To whom it may concern,", "Hey,", "", "Morning,"]
CLOSE = ["Thanks,", "Thank you,", "Thanks!", "Regards,", "Best,", "Appreciate it,", "Thx", ""]
URGENT = ["This is urgent.", "We need an answer today.", "Customer is waiting on this.", "Third time asking.", "Please escalate.", ""]


def _ref(rng, s):
    """Pick how a customer refers to the shipment; sometimes they give nothing useful."""
    r = rng.random()
    if r < 0.55:
        return f"PRO {s['pro']}"
    if r < 0.72:
        return f"BOL {s['bol']}"
    if r < 0.84:
        return f"our PO {s['po']}"
    if r < 0.92:
        return f"pro# {s['pro'][:4]}-{s['pro'][4:]}"
    return "the shipment we sent out " + rng.choice(["last week", "Tuesday", "a few days ago", "on the 14th"])


def _typo(rng, text):
    if rng.random() > 0.15:
        return text
    swaps = [("the", "teh"), ("shipment", "shipmnet"), ("delivery", "delievery"), ("received", "recieved"), ("please", "pls"), ("tomorrow", "tomorow")]
    a, b = rng.choice(swaps)
    return text.replace(a, b, 1)


STATUS = [
    "Can you tell me where {ref} is? It was supposed to deliver {eta}.",
    "Checking on {ref} going to {city}. Tracking hasn't updated since {lastday}.",
    "{ref} still shows in transit. Our customer {cons} says they don't have it.",
    "Your website says {ref} was delivered but {cons} says nothing arrived. Please check.",
    "Need an ETA on {ref}. {urgent}",
    "Status please on {ref}.",
    "Where is my freight? {ref}, shipped from {orgcity} to {city}.",
    "We haven't received 214 updates for any of our loads this week. Can someone give me status on {ref} at least?",
    "Following up again on {ref}. No one has called me back.",
    "Could you confirm delivery for {ref} and send the signed POD if it's delivered?",
]
PICKUP = [
    "Please schedule a pickup for {pickday}. {pcs} pallets, about {wgt} lbs, ready at {ready}, dock closes at {close}.",
    "Need a pickup today if possible. {pcs} skids, {wgt}#. We close at {close}.",
    "Can we get a driver out {pickday}? {pcs} pallets going to {city}, {wgt} lbs total.",
    "Pickup request: {company}, {addr}. {pcs} pcs / {wgt} lbs / class {cls}. Ready {ready}.",
    "Driver never showed up yesterday for our pickup. Please reschedule for {pickday}, same freight, {pcs} pallets.",
    "We have {pcs} pallets ready. Liftgate needed at pickup. Ready by {ready}.",
]
INVOICE = [
    "We were billed {amt} on invoice {inv} for {ref}. Our quote was lower. Please explain.",
    "Requesting a copy of invoice {inv}.",
    "Invoice {inv} shows a residential charge but this was a business delivery.",
    "Why was a liftgate fee added on {ref}? We did not request one.",
    "We paid invoice {inv} on the {day}. Please remove the past due notice.",
    "Please send all open invoices for account {cusno}.",
]
REWEIGH = [
    "We were rebilled on {ref}. Your reweigh says {nw} lbs but our scale says {ow}. Attaching the packing list.",
    "Disputing the reclass on {ref}. You changed it from class {ocl} to {ncl}. The product specs haven't changed.",
    "Third reclass this month on freight out of our {orgcity} plant. Every one of them went through Indianapolis. What is going on?",
    "Corrected invoice {inv} for {ref} increased by {diff}. Please provide the dimensioner record.",
    "We dispute the inspection fee on {ref}. Weight on the BOL is accurate.",
]
POD = [
    "Please send the POD for {ref}.",
    "Need signed delivery receipt for {ref}, our customer is disputing.",
    "Can I get PODs for the attached list of PROs? Starting with {ref}.",
    "Who signed for {ref}? Need the name and time.",
]
CLAIM = [
    "{ref} delivered damaged. {pcs_d} of {pcs} pallets crushed. How do we file a claim?",
    "Filing a claim on {ref} for {amt}. Shortage of {pcs_d} carton(s). Invoice and BOL attached.",
    "We found concealed damage on {ref} after unwrapping. Delivered {dlvday}. Photos attached.",
    "Checking status of claim {clm} on {ref}. Filed {filed}. We have not even had an acknowledgment.",
    "Claim {clm} has been open over 60 days. Please give me a decision.",
]
APPT = [
    "Please set a delivery appointment for {ref} with {cons}. They receive 7am to 2pm.",
    "Consignee on {ref} needs the delivery moved to {pickday}.",
    "Can you call ahead before delivering {ref}? Receiver requires notification.",
]
OTHER = [
    "Do you deliver to {city}? Looking for a quote.",
    "Please update our billing address on account {cusno}.",
    "Can you add me to the email list for tracking updates?",
    "Who is our sales rep now?",
    "Do you service Canada?",
]

TEMPLATES = {"status": STATUS, "pickup": PICKUP, "invoice": INVOICE, "reweigh": REWEIGH, "pod": POD, "claim": CLAIM, "appointment": APPT, "other": OTHER}
SUBJECTS = {
    "status": ["Status", "Where is my shipment", "Tracking", "RE: delivery", "{ref}", "ETA?", "Missing freight", "Shipment status {ref}"],
    "pickup": ["Pickup request", "PU {pickday}", "Need a pickup", "Pickup", "Missed pickup"],
    "invoice": ["Invoice question", "Billing", "Inv {inv}", "Overcharge", "Invoice copy"],
    "reweigh": ["Reweigh dispute", "Reclass", "Corrected invoice {inv}", "Inspection fee", "Rebill"],
    "pod": ["POD request", "Delivery receipt", "POD {ref}"],
    "claim": ["Damage claim", "Claim {clm}", "Shortage", "Concealed damage", "Claim status"],
    "appointment": ["Delivery appointment", "Appt", "Call ahead"],
    "other": ["Question", "Quote", "Account update", "Info"],
}


def render(rng: random.Random, category: str, s: dict, sender: dict) -> tuple[str, str]:
    """Return subject and body for one contact."""
    ref = _ref(rng, s)
    slots = {
        "ref": ref, "eta": s.get("eta_txt", "yesterday"), "city": s.get("city", ""), "orgcity": s.get("orgcity", ""),
        "lastday": rng.choice(["Monday", "Tuesday", "two days ago", "yesterday", "last week"]),
        "cons": s.get("cons", "our customer"), "urgent": rng.choice(URGENT),
        "pickday": rng.choice(["tomorrow", "Monday", "Thursday", "today", "Friday morning"]),
        "pcs": s.get("pcs", rng.randint(1, 6)), "pcs_d": max(1, s.get("pcs", 2) // 2), "wgt": s.get("wgt", rng.randint(300, 4000)),
        "ready": rng.choice(["9am", "10:00", "11:30", "1pm", "2:00 pm"]), "close": rng.choice(["3pm", "4:00", "4:30", "5pm"]),
        "company": sender.get("company", ""), "addr": s.get("addr", ""), "cls": s.get("cls", 70),
        "amt": s.get("amt", "$412.18"), "inv": s.get("inv", "LF" + str(rng.randint(10000000, 99999999))),
        "cusno": sender.get("cusno", ""), "day": rng.randint(1, 28), "nw": s.get("nw", 0), "ow": s.get("ow", 0),
        "ocl": s.get("ocl", 70), "ncl": s.get("ncl", 85), "diff": s.get("diff", "$96.40"),
        "clm": s.get("clm", "C" + str(rng.randint(1000000, 9999999))), "filed": s.get("filed", "last month"),
        "dlvday": s.get("dlvday", "Monday"),
    }
    body_t = rng.choice(TEMPLATES[category])
    body = body_t.format(**slots)
    if category == "status" and s.get("multi") and rng.random() < 0.5:
        body += f" Also need status on PRO {s['multi']}."
    greet, close = rng.choice(GREET), rng.choice(CLOSE)
    sig = f"{sender['first']} {sender['last']}\n{sender.get('company', '')}"
    if rng.random() < 0.3:
        sig += f"\n{sender.get('phone', '')}"
    parts = [p for p in [greet, _typo(rng, body), close, sig] if p]
    text = "\n\n".join(parts)
    if rng.random() < 0.12:
        text += f"\n\n-----Original Message-----\nFrom: {rng.choice(['Shipping', 'Receiving', 'Customer Service'])}\nSent: {rng.choice(['Monday', 'Tuesday', 'Wednesday'])}\nSubject: {rng.choice(['delivery', 'order'])}\n\nIs the freight there yet?"
    subj = rng.choice(SUBJECTS[category]).format(**slots)
    if rng.random() < 0.1:
        subj = subj.upper()
    return subj, text


def phone_note(rng: random.Random, category: str, s: dict, sender: dict) -> tuple[str, str]:
    """Phone contacts arrive as agent notes, terse and abbreviated."""
    short = {
        "status": f"Cust called re {s['pro']} status. Advised per FC. Wants callback if not dlvd by EOD.",
        "pickup": f"PU req {sender.get('company','')} {s.get('pcs',2)} plts {s.get('wgt',1000)}#, rdy {rng.choice(['10','1','2'])}p.",
        "invoice": f"Billing q on {s['pro']}, cust says overbilled. Sent to AR.",
        "reweigh": f"Disputes reweigh {s['pro']}. Says BOL wt correct. Needs dimensioner rec.",
        "pod": f"POD req {s['pro']}. Emailed from imaging.",
        "claim": f"Damage reported {s['pro']}. Gave claims email. Cust upset about prior claim no response.",
        "appointment": f"Appt req {s['pro']}, consignee wants AM.",
        "other": "General q, answered.",
    }[category]
    return f"Phone: {category}", short
