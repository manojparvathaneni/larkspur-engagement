"""Larkspur's terminals and the cities each one serves.

City names are real Midwest places so addresses look right. ZIP codes are real
prefixes for those cities. No real business is referenced.
"""

# code, name, city, state, zip, type, lat, lon
TERMINALS = [
    ("FWA", "FORT WAYNE", "Fort Wayne", "IN", "46803", "T", 41.0793, -85.1394),
    ("IND", "INDIANAPOLIS BB", "Indianapolis", "IN", "46241", "B", 39.7684, -86.1581),
    ("TOL", "TOLEDO", "Toledo", "OH", "43605", "T", 41.6528, -83.5379),
    ("CMH", "COLUMBUS", "Columbus", "OH", "43207", "T", 39.9612, -82.9988),
    ("CLE", "CLEVELAND", "Cleveland", "OH", "44135", "T", 41.4993, -81.6944),
    ("CIN", "CINCINNATI", "Cincinnati", "OH", "45215", "T", 39.1031, -84.5120),
    ("GRY", "GARY", "Gary", "IN", "46406", "T", 41.5934, -87.3464),
    ("CHI", "CHICAGO", "Chicago", "IL", "60638", "T", 41.8781, -87.6298),
    ("PIA", "PEORIA", "Peoria", "IL", "61602", "T", 40.6936, -89.5890),
    ("DET", "DETROIT", "Detroit", "MI", "48209", "T", 42.3314, -83.0458),
    ("GRR", "GRAND RAPIDS", "Grand Rapids", "MI", "49548", "T", 42.9634, -85.6681),
    ("LOU", "LOUISVILLE", "Louisville", "KY", "40213", "T", 38.2527, -85.7585),
    ("MKE", "MILWAUKEE", "Milwaukee", "WI", "53207", "T", 43.0389, -87.9065),
]
TERMINAL_CODES = [t[0] for t in TERMINALS if t[5] == "T"]
BREAKBULK = "IND"
TERM = {t[0]: t for t in TERMINALS}

# cities each terminal delivers to: (city, state, zip prefixes)
SERVICE = {
    "FWA": [("Fort Wayne", "IN", ["46802", "46804", "46805", "46808", "46818", "46825"]), ("Auburn", "IN", ["46706"]), ("Huntington", "IN", ["46750"]), ("Warsaw", "IN", ["46580", "46582"]), ("Lima", "OH", ["45801", "45805"])],
    "IND": [("Indianapolis", "IN", ["46201", "46204", "46219", "46222", "46241", "46268"]), ("Carmel", "IN", ["46032"]), ("Anderson", "IN", ["46013", "46016"]), ("Muncie", "IN", ["47302", "47304"]), ("Lafayette", "IN", ["47901", "47905"]), ("Bloomington", "IN", ["47401", "47404"])],
    "TOL": [("Toledo", "OH", ["43604", "43605", "43612", "43615"]), ("Findlay", "OH", ["45840"]), ("Bowling Green", "OH", ["43402"]), ("Monroe", "MI", ["48161"]), ("Sandusky", "OH", ["44870"])],
    "CMH": [("Columbus", "OH", ["43204", "43207", "43215", "43228", "43232"]), ("Newark", "OH", ["43055"]), ("Marion", "OH", ["43302"]), ("Lancaster", "OH", ["43130"]), ("Zanesville", "OH", ["43701"])],
    "CLE": [("Cleveland", "OH", ["44102", "44105", "44114", "44135"]), ("Akron", "OH", ["44301", "44310"]), ("Lorain", "OH", ["44052"]), ("Canton", "OH", ["44702", "44707"]), ("Mentor", "OH", ["44060"])],
    "CIN": [("Cincinnati", "OH", ["45202", "45215", "45232", "45241"]), ("Dayton", "OH", ["45402", "45414"]), ("Hamilton", "OH", ["45011"]), ("Covington", "KY", ["41011"]), ("Middletown", "OH", ["45042"])],
    "GRY": [("Gary", "IN", ["46402", "46406"]), ("Hammond", "IN", ["46320", "46323"]), ("Merrillville", "IN", ["46410"]), ("Valparaiso", "IN", ["46383"]), ("South Bend", "IN", ["46601", "46619"])],
    "CHI": [("Chicago", "IL", ["60608", "60609", "60632", "60638", "60651"]), ("Elk Grove Village", "IL", ["60007"]), ("Joliet", "IL", ["60431", "60436"]), ("Aurora", "IL", ["60502", "60505"]), ("Waukegan", "IL", ["60085"])],
    "PIA": [("Peoria", "IL", ["61602", "61603", "61615"]), ("Bloomington", "IL", ["61701", "61704"]), ("Springfield", "IL", ["62702", "62703"]), ("Champaign", "IL", ["61820", "61822"]), ("Decatur", "IL", ["62521", "62526"])],
    "DET": [("Detroit", "MI", ["48204", "48209", "48210", "48217"]), ("Dearborn", "MI", ["48120", "48126"]), ("Warren", "MI", ["48089", "48091"]), ("Livonia", "MI", ["48150"]), ("Ann Arbor", "MI", ["48103", "48108"])],
    "GRR": [("Grand Rapids", "MI", ["49503", "49507", "49548"]), ("Kalamazoo", "MI", ["49001", "49007"]), ("Holland", "MI", ["49423"]), ("Lansing", "MI", ["48906", "48910"]), ("Muskegon", "MI", ["49442"])],
    "LOU": [("Louisville", "KY", ["40202", "40209", "40213", "40218"]), ("Lexington", "KY", ["40505", "40511"]), ("Elizabethtown", "KY", ["42701"]), ("Jeffersonville", "IN", ["47130"]), ("Frankfort", "KY", ["40601"])],
    "MKE": [("Milwaukee", "WI", ["53204", "53207", "53214", "53218"]), ("Waukesha", "WI", ["53186"]), ("Racine", "WI", ["53403"]), ("Kenosha", "WI", ["53144"]), ("Madison", "WI", ["53704", "53713"])],
}

STREETS = ["Industrial Pkwy", "Commerce Dr", "Distribution Way", "Main St", "Enterprise Blvd", "Expressway Dr", "Lakeview Rd", "Airport Rd", "Mill St", "Production Dr", "Logistics Ln", "Park Center Dr", "Harrison St", "Washington Ave", "Oak St", "Depot Rd", "Corporate Dr", "Factory St", "Meridian St", "Center Ave"]


def zone(org: str, dst: str) -> int:
    """Rating zone from straight line distance between terminals, 1 to 5."""
    import math
    a, b = TERM[org], TERM[dst]
    d = math.hypot((a[6] - b[6]) * 69, (a[7] - b[7]) * 52)
    if org == dst:
        return 1
    return 2 if d < 150 else 3 if d < 250 else 4 if d < 350 else 5


def transit_days(org: str, dst: str) -> int:
    z = zone(org, dst)
    return {1: 1, 2: 1, 3: 2, 4: 2, 5: 3}[z]


def via_breakbulk(org: str, dst: str) -> bool:
    return org != dst and zone(org, dst) >= 3
