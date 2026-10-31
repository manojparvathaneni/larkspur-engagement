"""PRO numbers, density classes and rating, following published LTL practice."""

# NMFC density sub scale effective July 19, 2025: lower bound pcf -> class
DENSITY_BANDS = [(50, 50.0), (35, 55.0), (30, 60.0), (22.5, 65.0), (15, 70.0), (12, 85.0),
                 (10, 92.5), (8, 100.0), (6, 125.0), (4, 175.0), (2, 250.0), (1, 300.0), (0, 400.0)]
CLASSES = [50.0, 55.0, 60.0, 65.0, 70.0, 77.5, 85.0, 92.5, 100.0, 110.0, 125.0, 150.0, 175.0, 200.0, 250.0, 300.0, 400.0, 500.0]

ACCESSORIALS = {  # code: (description, charge)
    "LG": ("Liftgate", 145.00),
    "RS": ("Residential", 165.00),
    "AP": ("Appointment", 25.00),
    "ID": ("Inside delivery", 140.00),
    "LA": ("Limited access", 155.00),
    "NT": ("Notify before delivery", 45.00),
    "HZ": ("Hazmat", 65.00),
}
FUEL_SURCHARGE = 0.285
REWEIGH_FEE = 30.00


def check_digit(base8: int) -> int:
    return base8 % 7


def pro_number(base8: int) -> str:
    return f"{base8:08d}{check_digit(base8)}"


def pro_valid(pro: str) -> bool:
    return len(pro) == 9 and pro.isdigit() and int(pro[:8]) % 7 == int(pro[8])


def density_class(weight_lb: float, cubic_ft: float) -> float:
    pcf = weight_lb / cubic_ft if cubic_ft else 0
    for low, cls in DENSITY_BANDS:
        if pcf >= low:
            return cls
    return 400.0


def cubic_feet(l_in: float, w_in: float, h_in: float, pieces: int = 1) -> float:
    return round(l_in * w_in * h_in / 1728.0 * pieces, 1)


def rate_cwt(cls: float, zn: int) -> float:
    """Tariff rate per hundredweight before discount."""
    base = 18.0 + 6.5 * zn
    return round(base * (cls / 100.0) ** 0.85, 2)


def minimum_charge(zn: int) -> float:
    return 95.0 + 15 * zn


def rate(weight_lb: int, cls: float, zn: int, discount_pct: float, accessorials: list[str]) -> tuple[float, float, float]:
    """Return linehaul net, accessorial total, fuel surcharge."""
    gross = rate_cwt(cls, zn) * weight_lb / 100.0
    net = max(gross * (1 - discount_pct / 100.0), minimum_charge(zn))
    acc = sum(ACCESSORIALS[a][1] for a in accessorials if a in ACCESSORIALS)
    fsc = round(net * FUEL_SURCHARGE, 2)
    return round(net, 2), round(acc, 2), fsc
