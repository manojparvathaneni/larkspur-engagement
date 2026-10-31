"""Invented business and person names. Combinations are generated, not taken from real companies."""

PREFIX = ["Bluegate", "Northside", "Prairie", "Lakeshore", "Ironwood", "Summit", "Riverbend", "Keystone", "Maple Ridge", "Cedar Point", "Great Lakes", "Heartland", "Tri County", "Westbrook", "Fairview", "Granite", "Sterling", "Oakmont", "Redline", "Harbor", "Pinecrest", "Midstate", "Crossroads", "Silverline", "Cornerstone", "Brightwater", "Eastfield", "Kestrel", "Wolf Creek", "Copperleaf", "Valley", "Pioneer", "Lincolnway", "Old Mill", "Stonebridge", "Clearwater", "Highpoint", "Union", "Frontier", "Bayside", "Elm Street", "Kingsbury", "Larchmont", "Mapleton", "Northgate", "Parkside", "Quarry", "Rockport", "Sawyer", "Thornapple"]
CORE = ["Hardware", "Industrial Supply", "Plastics", "Fasteners", "Packaging", "Foods", "Auto Parts", "Electrical", "Paper Products", "Furniture", "Steel", "Chemical", "Beverage", "Pet Supply", "Building Products", "Lighting", "HVAC Supply", "Tool", "Appliance", "Tire", "Restaurant Supply", "Pharmacy Supply", "Garden Center", "Printing", "Machine Works", "Pump", "Flooring", "Cabinet", "Medical Supply", "Office Products", "Farm Supply", "Bearing", "Rubber", "Glass", "Textile", "Coatings", "Wire", "Filter", "Valve", "Display"]
SUFFIX = ["Co", "Inc", "LLC", "Corp", "Distributors", "Group", "Supply", "Company", "Wholesale", "Mfg"]

FIRST = ["Karen", "Mike", "Jen", "Dave", "Lisa", "Tom", "Angela", "Brian", "Megan", "Steve", "Rachel", "Chris", "Amanda", "Kevin", "Nicole", "Jason", "Heather", "Mark", "Laura", "Dan", "Tasha", "Luis", "Priyanka", "Marcus", "Hannah", "Omar", "Beth", "Raj", "Kim", "Derek", "Sofia", "Tyler", "Monica", "Greg", "Aisha", "Pete", "Wendy", "Andre", "Carla", "Jim", "Maria", "Ken", "Deb", "Ravi", "Shawna", "Alex", "Gina", "Rob", "Yolanda", "Nate"]
LAST = ["Miller", "Johnson", "Schultz", "Nguyen", "Patel", "Kowalski", "Brown", "Garcia", "Hoffman", "Davis", "Wilson", "Anderson", "Meyer", "Thomas", "Jackson", "Martinez", "Lee", "Walker", "Young", "King", "Wright", "Lopez", "Hill", "Scott", "Green", "Adams", "Baker", "Nelson", "Carter", "Mitchell", "Roberts", "Turner", "Phillips", "Campbell", "Parker", "Evans", "Edwards", "Collins", "Stewart", "Morris", "Rogers", "Reed", "Cook", "Morgan", "Bell", "Murphy", "Bailey", "Rivera", "Cooper", "Howard"]

# Larkspur's own people who appear in data
AGENTS = ["kmorales", "tbriggs", "ljensen", "rdelgado", "apatel", "dwhite", "sgreen", "mchu", "jortiz", "bnovak", "cwells", "hkaur"]


def company_name(rng, used: set) -> str:
    while True:
        n = f"{rng.choice(PREFIX)} {rng.choice(CORE)} {rng.choice(SUFFIX)}"
        if n not in used:
            used.add(n)
            return n


def person(rng) -> tuple[str, str]:
    return rng.choice(FIRST), rng.choice(LAST)


def email_domain(company: str) -> str:
    base = company.lower()
    for s in [" co", " inc", " llc", " corp", " distributors", " group", " supply", " company", " wholesale", " mfg"]:
        if base.endswith(s):
            base = base[: -len(s)]
            break
    return base.replace(" ", "").replace("'", "") + ".example"
