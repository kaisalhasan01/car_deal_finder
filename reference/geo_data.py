"""Swedish geography reference: all 290 municipalities (kommuner) -> 21 counties (län).

Blocket listings carry a free-text location (usually the municipality or a
locality), but no county. Counties are what Power BI map/slicer visuals need,
so we resolve location -> municipality -> county here.

Also holds Blocket's county filter codes (the `location` search parameter),
taken from the open-source blocket-api package (WTFPL), v0.5.2.
"""
from __future__ import annotations

import re
import unicodedata

MUNICIPALITIES_BY_COUNTY: dict[str, list[str]] = {
    "Stockholms län": [
        "Botkyrka", "Danderyd", "Ekerö", "Haninge", "Huddinge", "Järfälla", "Lidingö",
        "Nacka", "Norrtälje", "Nykvarn", "Nynäshamn", "Salem", "Sigtuna", "Sollentuna",
        "Solna", "Stockholm", "Sundbyberg", "Södertälje", "Tyresö", "Täby",
        "Upplands Väsby", "Upplands-Bro", "Vallentuna", "Vaxholm", "Värmdö", "Österåker",
    ],
    "Uppsala län": [
        "Enköping", "Heby", "Håbo", "Knivsta", "Tierp", "Uppsala", "Älvkarleby", "Östhammar",
    ],
    "Södermanlands län": [
        "Eskilstuna", "Flen", "Gnesta", "Katrineholm", "Nyköping", "Oxelösund", "Strängnäs",
        "Trosa", "Vingåker",
    ],
    "Östergötlands län": [
        "Boxholm", "Finspång", "Kinda", "Linköping", "Mjölby", "Motala", "Norrköping",
        "Söderköping", "Vadstena", "Valdemarsvik", "Ydre", "Åtvidaberg", "Ödeshög",
    ],
    "Jönköpings län": [
        "Aneby", "Eksjö", "Gislaved", "Gnosjö", "Habo", "Jönköping", "Mullsjö", "Nässjö",
        "Sävsjö", "Tranås", "Vaggeryd", "Vetlanda", "Värnamo",
    ],
    "Kronobergs län": [
        "Alvesta", "Lessebo", "Ljungby", "Markaryd", "Tingsryd", "Uppvidinge", "Växjö", "Älmhult",
    ],
    "Kalmar län": [
        "Borgholm", "Emmaboda", "Hultsfred", "Högsby", "Kalmar", "Mönsterås", "Mörbylånga",
        "Nybro", "Oskarshamn", "Torsås", "Vimmerby", "Västervik",
    ],
    "Gotlands län": ["Gotland"],
    "Blekinge län": ["Karlshamn", "Karlskrona", "Olofström", "Ronneby", "Sölvesborg"],
    "Skåne län": [
        "Bjuv", "Bromölla", "Burlöv", "Båstad", "Eslöv", "Helsingborg", "Hässleholm",
        "Höganäs", "Hörby", "Höör", "Klippan", "Kristianstad", "Kävlinge", "Landskrona",
        "Lomma", "Lund", "Malmö", "Osby", "Perstorp", "Simrishamn", "Sjöbo", "Skurup",
        "Staffanstorp", "Svalöv", "Svedala", "Tomelilla", "Trelleborg", "Vellinge", "Ystad",
        "Åstorp", "Ängelholm", "Örkelljunga", "Östra Göinge",
    ],
    "Hallands län": ["Falkenberg", "Halmstad", "Hylte", "Kungsbacka", "Laholm", "Varberg"],
    "Västra Götalands län": [
        "Ale", "Alingsås", "Bengtsfors", "Bollebygd", "Borås", "Dals-Ed", "Essunga",
        "Falköping", "Färgelanda", "Grästorp", "Gullspång", "Göteborg", "Götene",
        "Herrljunga", "Hjo", "Härryda", "Karlsborg", "Kungälv", "Lerum", "Lidköping",
        "Lilla Edet", "Lysekil", "Mariestad", "Mark", "Mellerud", "Munkedal", "Mölndal",
        "Orust", "Partille", "Skara", "Skövde", "Sotenäs", "Stenungsund", "Strömstad",
        "Svenljunga", "Tanum", "Tibro", "Tidaholm", "Tjörn", "Tranemo", "Trollhättan",
        "Töreboda", "Uddevalla", "Ulricehamn", "Vara", "Vårgårda", "Vänersborg", "Åmål",
        "Öckerö",
    ],
    "Värmlands län": [
        "Arvika", "Eda", "Filipstad", "Forshaga", "Grums", "Hagfors", "Hammarö", "Karlstad",
        "Kil", "Kristinehamn", "Munkfors", "Storfors", "Sunne", "Säffle", "Torsby", "Årjäng",
    ],
    "Örebro län": [
        "Askersund", "Degerfors", "Hallsberg", "Hällefors", "Karlskoga", "Kumla", "Laxå",
        "Lekeberg", "Lindesberg", "Ljusnarsberg", "Nora", "Örebro",
    ],
    "Västmanlands län": [
        "Arboga", "Fagersta", "Hallstahammar", "Kungsör", "Köping", "Norberg", "Sala",
        "Skinnskatteberg", "Surahammar", "Västerås",
    ],
    "Dalarnas län": [
        "Avesta", "Borlänge", "Falun", "Gagnef", "Hedemora", "Leksand", "Ludvika",
        "Malung-Sälen", "Mora", "Orsa", "Rättvik", "Smedjebacken", "Säter", "Vansbro",
        "Älvdalen",
    ],
    "Gävleborgs län": [
        "Bollnäs", "Gävle", "Hofors", "Hudiksvall", "Ljusdal", "Nordanstig", "Ockelbo",
        "Ovanåker", "Sandviken", "Söderhamn",
    ],
    "Västernorrlands län": [
        "Härnösand", "Kramfors", "Sollefteå", "Sundsvall", "Timrå", "Ånge", "Örnsköldsvik",
    ],
    "Jämtlands län": [
        "Berg", "Bräcke", "Härjedalen", "Krokom", "Ragunda", "Strömsund", "Åre", "Östersund",
    ],
    "Västerbottens län": [
        "Bjurholm", "Dorotea", "Lycksele", "Malå", "Nordmaling", "Norsjö", "Robertsfors",
        "Skellefteå", "Sorsele", "Storuman", "Umeå", "Vilhelmina", "Vindeln", "Vännäs", "Åsele",
    ],
    "Norrbottens län": [
        "Arjeplog", "Arvidsjaur", "Boden", "Gällivare", "Haparanda", "Jokkmokk", "Kalix",
        "Kiruna", "Luleå", "Pajala", "Piteå", "Älvsbyn", "Överkalix", "Övertorneå",
    ],
}

# Common localities / city districts that are not municipality names themselves.
LOCALITY_TO_MUNICIPALITY: dict[str, str] = {
    "Åkersberga": "Österåker", "Märsta": "Sigtuna", "Tumba": "Botkyrka", "Tullinge": "Botkyrka",
    "Handen": "Haninge", "Jordbro": "Haninge", "Rotebro": "Sollentuna", "Arninge": "Täby",
    "Kungsängen": "Upplands-Bro", "Bro": "Upplands-Bro", "Gustavsberg": "Värmdö",
    "Saltsjöbaden": "Nacka", "Saltsjö-Boo": "Nacka", "Bromma": "Stockholm",
    "Hägersten": "Stockholm", "Spånga": "Stockholm", "Kista": "Stockholm",
    "Skärholmen": "Stockholm", "Farsta": "Stockholm", "Vällingby": "Stockholm",
    "Enskede": "Stockholm", "Johanneshov": "Stockholm", "Sundbyberg": "Sundbyberg",
    "Mölnlycke": "Härryda", "Kållered": "Mölndal", "Västra Frölunda": "Göteborg",
    "Hisings Backa": "Göteborg", "Torslanda": "Göteborg", "Angered": "Göteborg",
    "Visby": "Gotland", "Arlöv": "Burlöv", "Åkarp": "Burlöv", "Limhamn": "Malmö",
    "Höllviken": "Vellinge", "Löddeköpinge": "Kävlinge", "Mariefred": "Strängnäs",
    "Sälen": "Malung-Sälen", "Malung": "Malung-Sälen", "Ljungskile": "Uddevalla",
    "Sveg": "Härjedalen", "Järpen": "Åre", "Färjestaden": "Mörbylånga",
    "Kinna": "Mark", "Skene": "Mark", "Ed": "Dals-Ed", "Stenungsund": "Stenungsund",
    "Nödinge": "Ale", "Älvängen": "Ale", "Surte": "Ale", "Sävedalen": "Partille",
    "Landvetter": "Härryda", "Frövi": "Lindesberg", "Kopparberg": "Ljusnarsberg",
    "Storvik": "Sandviken", "Iggesund": "Hudiksvall", "Bergsjö": "Nordanstig",
    "Hammarstrand": "Ragunda", "Kramfors": "Kramfors", "Bjästa": "Örnsköldsvik",
}

# Blocket's `location` search-filter codes, one per county.
BLOCKET_COUNTY_CODES: dict[str, str] = {
    "Blekinge län": "0.300010", "Dalarnas län": "0.300020", "Gotlands län": "0.300009",
    "Gävleborgs län": "0.300021", "Hallands län": "0.300013", "Jämtlands län": "0.300023",
    "Jönköpings län": "0.300006", "Kalmar län": "0.300008", "Kronobergs län": "0.300007",
    "Norrbottens län": "0.300025", "Skåne län": "0.300012", "Stockholms län": "0.300001",
    "Södermanlands län": "0.300004", "Uppsala län": "0.300003", "Värmlands län": "0.300017",
    "Västerbottens län": "0.300024", "Västernorrlands län": "0.300022",
    "Västmanlands län": "0.300019", "Västra Götalands län": "0.300014",
    "Örebro län": "0.300018", "Östergötlands län": "0.300005",
}


def _key(text: str) -> str:
    """Case-, whitespace- and hyphen-insensitive key (keeps å/ä/ö distinct)."""
    text = unicodedata.normalize("NFC", str(text)).strip().lower()
    text = re.sub(r"\s+kommun$|\s+stad$", "", text)
    return re.sub(r"[\s\-]+", " ", text)


_MUNICIPALITY_TO_COUNTY = {
    _key(m): county for county, ms in MUNICIPALITIES_BY_COUNTY.items() for m in ms
}
_MUNICIPALITY_CANONICAL = {_key(m): m for ms in MUNICIPALITIES_BY_COUNTY.values() for m in ms}
_LOCALITY_KEYS = {_key(a): m for a, m in LOCALITY_TO_MUNICIPALITY.items()}
_COUNTY_CANONICAL = {_key(c): c for c in MUNICIPALITIES_BY_COUNTY}
# Short county names ("Skåne", "Stockholms", "Västra Götaland") -> canonical county.
for _c in list(MUNICIPALITIES_BY_COUNTY):
    _short = _key(_c[:-4]) if _c.endswith(" län") else _key(_c)
    _COUNTY_CANONICAL.setdefault(_short, _c)
    _COUNTY_CANONICAL.setdefault(_short.rstrip("s"), _c)


def resolve_location(location: str | None) -> tuple[str | None, str | None]:
    """Map a Blocket location string to (municipality, county).

    Tries every comma/slash-separated part, so "Solna, Stockholm" and
    "Stockholms län" both resolve. Returns (None, None) when nothing matches.
    """
    if not location:
        return None, None
    municipality = county = None
    for part in re.split(r"[,/|]", str(location)):
        k = _key(part)
        if not k:
            continue
        if k in _MUNICIPALITY_TO_COUNTY and municipality is None:
            municipality = _MUNICIPALITY_CANONICAL[k]
            county = county or _MUNICIPALITY_TO_COUNTY[k]
        elif k in _LOCALITY_KEYS and municipality is None:
            municipality = _LOCALITY_KEYS[k]
            county = county or _MUNICIPALITY_TO_COUNTY[_key(municipality)]
        elif k in _COUNTY_CANONICAL:
            county = county or _COUNTY_CANONICAL[k]
    return municipality, county


def county_for(location: str | None) -> str | None:
    return resolve_location(location)[1]
