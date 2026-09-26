"""Blocket search-filter codes and value normalizers.

Filter codes are the ones Blocket's own car search sends (FINN/Vend platform
taxonomy). Source: the open-source `blocket-api` package v0.5.2 (WTFPL licence),
https://pypi.org/project/blocket-api/ — cross-checked against its CarModel enum.
"""
from __future__ import annotations

import re

# Display name -> Blocket `make` filter code.
MAKE_CODES: dict[str, str] = {
    "Abarth": "0.8093", "AC": "0.200673", "Acura": "0.200674", "Aiways": "0.200681",
    "Alfa Romeo": "0.3233", "Alpina": "0.8092", "AMC": "0.8103", "Ariel": "0.8110",
    "Armstrong Siddeley": "0.1156", "Aston Martin": "0.6733", "Audi": "0.744",
    "Austin": "0.8076", "Austin-Healey": "0.200688", "Auto Union": "0.200689",
    "Autobianchi": "0.200690", "Bedford": "0.200693", "Bentley": "0.7166", "BMW": "0.749",
    "Bugatti": "0.8111", "Buick": "0.750", "BYD": "0.8101", "Cadillac": "0.752",
    "Caterham": "0.200704", "Chevrolet": "0.753", "Chrysler": "0.754", "Citroën": "0.757",
    "Cupra": "0.8106", "Dacia": "0.8079", "Daewoo": "0.760", "DAF": "0.8090",
    "Daihatsu": "0.762", "Daimler": "0.200711", "Datsun": "0.8089", "De Tomaso": "0.8069",
    "DeLorean": "0.8085", "DeSoto": "0.200715", "DFSK": "0.2174", "DKW": "0.200718",
    "Dodge": "0.764", "DS": "0.8091", "Edsel": "0.200723", "Erskine": "0.200726",
    "Excalibur": "0.200727", "Ferrari": "0.2999", "Fiat": "0.766", "Fisker": "0.8073",
    "Ford": "0.767", "Fordson": "0.200730", "GAZ": "0.200734", "Ginetta": "0.200738",
    "GMC": "0.7547", "Heinkel": "0.200745", "Hillman": "0.200746", "Holden": "0.200747",
    "Honda": "0.771", "Hongqi": "0.8107", "Hudson": "0.200748", "Humber": "0.200749",
    "Hummer": "0.7672", "Hyundai": "0.772", "Ineos": "0.2000665", "Infiniti": "0.8065",
    "International": "0.1160", "Isuzu": "0.7179", "Iveco": "0.7280", "JAC": "0.8114",
    "Jaguar": "0.775", "Jeep": "0.776", "Jensen": "0.774", "Kaiser Jeep": "0.1162",
    "KGM": "0.2000649", "Kia": "0.777", "KTM": "0.200761", "Lada": "0.779",
    "Lamborghini": "0.6731", "Lancia": "0.780", "Land Rover": "0.781", "LEVC": "0.200764",
    "Lexus": "0.782", "Leyland": "0.200765", "Lincoln": "0.7153", "Lotus": "0.7191",
    "Lynk & Co": "0.200769", "MAN": "0.8097", "Maserati": "0.3001", "Maxus": "0.8096",
    "Mazda": "0.784", "McLaren": "0.8087", "Mercedes-Benz": "0.785", "Mercury": "0.7554",
    "Messerschmitt": "0.200774", "MG": "0.786", "MINI": "0.7147", "Mini Marcos": "0.200775",
    "Mitsubishi": "0.787", "Morgan": "0.788", "Morris": "0.789", "NIO": "0.8109",
    "Nissan": "0.792", "Oldsmobile": "0.794", "Opel": "0.795", "Packard": "0.8077",
    "Peugeot": "0.796", "Plymouth": "0.797", "Polestar": "0.8102", "Pontiac": "0.800",
    "Porsche": "0.801", "Pro Sport": "0.200792", "Radical": "0.8088", "RAM": "0.8100",
    "Renault": "0.804", "Rolls-Royce": "0.7170", "Rover": "0.805", "Saab": "0.806",
    "Scion": "0.822", "Seat": "0.807", "Seres": "0.8108", "Shelby": "0.1142",
    "Simca": "0.200807", "Skoda": "0.808", "Smart": "0.7137", "SsangYong": "0.7190",
    "Standard": "0.200812", "Studebaker": "0.200815", "Subaru": "0.810", "Suzuki": "0.811",
    "Tesla": "0.8078", "Toyota": "0.813", "Trabant": "0.200824", "Triumph": "0.814",
    "TVR": "0.820", "Vauxhall": "0.200827", "Volkswagen": "0.817", "Volvo": "0.818",
    "Willys": "0.200834", "XPeng": "0.8104", "Zeekr": "0.200841", "Zimmer": "0.200844",
    "Övriga": "0.2252",
}

TRANSMISSION_CODES = {"Manuell": "1", "Automat": "2"}
WHEEL_DRIVE_CODES = {"RWD": "1", "AWD": "2", "FWD": "3"}
SALES_FORM = {"used": 1, "new": 2, "leasing": 5}
SORT_OPTIONS = (
    "RELEVANCE", "PUBLISHED_DESC", "PUBLISHED_ASC", "PRICE_ASC", "PRICE_DESC",
    "MILEAGE_ASC", "MILEAGE_DESC", "YEAR_ASC", "YEAR_DESC", "MODEL",
)


def _k(text: str) -> str:
    return re.sub(r"[\s\-_&.]+", "", str(text).strip().lower())


_BRAND_BY_KEY = {_k(name): name for name in MAKE_CODES}
_BRAND_BY_KEY.update({
    "vw": "Volkswagen", "mercedes": "Mercedes-Benz", "mb": "Mercedes-Benz",
    "citroen": "Citroën", "škoda": "Skoda", "alfa": "Alfa Romeo", "landrover": "Land Rover",
    "rollsroyce": "Rolls-Royce", "lynkco": "Lynk & Co", "ssang yong": "SsangYong",
})


def canonical_brand(make: str | None) -> str | None:
    """'VOLVO' / 'volvo' -> 'Volvo', 'vw' -> 'Volkswagen', unknown -> tidy title case."""
    if not make or not str(make).strip():
        return None
    hit = _BRAND_BY_KEY.get(_k(make))
    if hit:
        return hit
    text = str(make).strip()
    return text if (text.isupper() and len(text) <= 4) else text.title()


def make_code(brand: str) -> str | None:
    name = canonical_brand(brand)
    return MAKE_CODES.get(name) if name else None


def canonical_fuel(value: str | None) -> str | None:
    """Map Blocket fuel labels to: Bensin | Diesel | El | Hybrid | Laddhybrid | Etanol | Gas | Vätgas."""
    if not value:
        return None
    v = str(value).strip().lower()
    if any(t in v for t in ("ladd", "plug", "phev")):
        return "Laddhybrid"
    if "hybrid" in v:
        return "Hybrid"
    if "diesel" in v:
        return "Diesel"
    if "bensin" in v or "petrol" in v:
        return "Bensin"
    if "etanol" in v or "e85" in v:
        return "Etanol"
    if "vätgas" in v or "hydrogen" in v:
        return "Vätgas"
    if "gas" in v:
        return "Gas"
    if re.search(r"\b(el|elbil|elektrisk|electric|ev)\b", v):
        return "El"
    return str(value).strip()


def canonical_gearbox(value: str | None) -> str | None:
    if not value:
        return None
    v = str(value).strip().lower()
    if v.startswith("auto"):
        return "Automat"
    if v.startswith("manu"):
        return "Manuell"
    return str(value).strip()


def canonical_drivetrain(value: str | None) -> str | None:
    if not value:
        return None
    v = str(value).strip().lower()
    if any(t in v for t in ("fyrhjul", "4wd", "awd", "4x4", "all")):
        return "AWD"
    if "fram" in v or "fwd" in v:
        return "FWD"
    if "bak" in v or "rwd" in v:
        return "RWD"
    return None


_AWD_PATTERN = re.compile(
    r"\b(awd|4x4|4wd|quattro|xdrive|4motion|all4|4matic\+?|awd-i|e-four|allgrip|"
    r"dual motor|twin motor|twin engine)\b",
    re.IGNORECASE,
)


def drivetrain_from_text(*texts: str | None, brand: str | None = None) -> str | None:
    """Positive AWD detection from a heading/model spec. Never guesses FWD/RWD."""
    blob = " ".join(t for t in texts if t)
    if not blob:
        return None
    if _AWD_PATTERN.search(blob):
        return "AWD"
    if (brand or "").lower() == "volvo" and re.search(r"\bt8\b", blob, re.IGNORECASE):
        return "AWD"   # every Volvo T8 plug-in hybrid is AWD
    return None


def power_hp_from_text(*texts: str | None) -> int | None:
    """'D4 190hk' -> 190, '150 kW' -> 204. Returns None when no plausible figure."""
    blob = " ".join(t for t in texts if t)
    m = re.search(r"(\d{2,4})\s?(?:hk|hp|hästkrafter)\b", blob, re.IGNORECASE)
    if m and 40 <= int(m.group(1)) <= 1200:
        return int(m.group(1))
    m = re.search(r"(\d{2,3})\s?kw\b", blob, re.IGNORECASE)
    if m and 30 <= int(m.group(1)) <= 900:
        return int(round(int(m.group(1)) * 1.36))
    return None


_REGNR = re.compile(r"^[A-Z]{3}\d{2}[A-Z0-9]$")


def canonical_regnr(value: str | None) -> str | None:
    """Swedish plate 'abc 12d' -> 'ABC12D'; None if it isn't a valid plate format."""
    if not value:
        return None
    plate = re.sub(r"[\s\-]", "", str(value)).upper()
    return plate if _REGNR.match(plate) else None


def canonical_seller(dealer_segment=None, flags=None, organisation_name=None) -> str | None:
    seg = str(dealer_segment or "").strip().lower()
    if seg.startswith("priv"):
        return "private"
    if seg and any(t in seg for t in ("före", "fore", "handl", "dealer", "company", "bil")):
        return "dealer"
    flag_text = " ".join(str(f).lower() for f in (flags or []))
    if "private" in flag_text or "privat" in flag_text:
        return "private"
    if any(t in flag_text for t in ("dealer", "company", "företag")):
        return "dealer"
    if organisation_name:
        return "dealer"
    return None
