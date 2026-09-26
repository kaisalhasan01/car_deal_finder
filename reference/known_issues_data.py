"""Curated 'vanliga fel' knowledge base — the buyer-advisor's domain knowledge.

Each entry: a well-known fault for a model+year-range, what to check at viewing,
and an indicative negotiation leverage (≈ typical repair cost in SEK) you can use
to haggle. Year range is inclusive; None = open-ended.

DISCLAIMER: these are indicative, community-known issues to help you ask the
right questions — NOT a substitute for a professional inspection / test drive.
Always verify on the specific car. Severity: low | medium | high.
"""

ISSUES = [
    # --- Audi A4 (B8) — the classic 2.0 TFSI oil burner -----------------------
    {"brand": "Audi", "model": "A4", "year_from": 2008, "year_to": 2012,
     "engine": "2.0 TFSI", "category": "Motor", "severity": "high",
     "issue": "Hög oljeförbrukning (slitna kolvringar/oljeavskiljare)",
     "what_to_check": "Be om servicebok och oljeförbruknings-historik. Kolla om kolvringar/block åtgärdats enligt Audis bulletin. Mät oljenivå.",
     "negotiation_leverage_sek": 15000},
    {"brand": "Audi", "model": "A4", "year_from": 2008, "year_to": 2015,
     "engine": None, "category": "Motor", "severity": "medium",
     "issue": "Kamkedjesträckare kan slitas (rassel vid kallstart)",
     "what_to_check": "Lyssna efter rassel de första sekunderna vid kallstart. Fråga om uppdaterad sträckare monterats.",
     "negotiation_leverage_sek": 12000},

    # --- BMW 3-serie — N47 diesel timing chain -------------------------------
    {"brand": "BMW", "model": "3-serie", "year_from": 2007, "year_to": 2014,
     "engine": "N47 diesel", "category": "Motor", "severity": "high",
     "issue": "Kamkedja kan sträckas/haverera (sitter baktill på motorn)",
     "what_to_check": "Lyssna efter rassel/skrammel från kamkedjan vid kallstart. Dyrt jobb då kedjan sitter mot växellådan.",
     "negotiation_leverage_sek": 25000},

    # --- Volvo V60 / XC60 diesel — DPF/EGR ------------------------------------
    {"brand": "Volvo", "model": "V60", "year_from": 2010, "year_to": 2015,
     "engine": "D-diesel", "category": "Motor", "severity": "medium",
     "issue": "Partikelfilter (DPF) sätts igen vid mest stadskörning",
     "what_to_check": "Fråga om bilen mest körts kort-/stadssträcka. Be om felfri regenerering och kolla DPF-status.",
     "negotiation_leverage_sek": 12000},
    {"brand": "Volvo", "model": "XC60", "year_from": 2009, "year_to": 2017,
     "engine": "D-diesel", "category": "Motor", "severity": "medium",
     "issue": "EGR-kylare kan läcka (vit rök, kylvätskeförlust)",
     "what_to_check": "Kolla kylvätskenivå och vit rök vid kallstart. Fråga om EGR-kylare bytts.",
     "negotiation_leverage_sek": 10000},

    # --- VW / Skoda — 1.4 TSI chain tensioner + DSG ---------------------------
    {"brand": "Volkswagen", "model": "Golf", "year_from": 2008, "year_to": 2013,
     "engine": "1.4 TSI (EA111)", "category": "Motor", "severity": "high",
     "issue": "Kamkedjesträckare kan haverera → motorskada",
     "what_to_check": "Kolla att uppdaterad sträckare monterats. Lyssna efter rassel vid kallstart/varv.",
     "negotiation_leverage_sek": 20000},
    {"brand": "Volkswagen", "model": "Golf", "year_from": 2008, "year_to": 2016,
     "engine": "DSG (DQ200)", "category": "Växellåda", "severity": "medium",
     "issue": "DSG-mekatronik/koppling kan strula",
     "what_to_check": "Provkör för ryck eller glapp vid växling. Fråga om DSG-oljebyte gjorts (~var 6:e år).",
     "negotiation_leverage_sek": 15000},
    {"brand": "Skoda", "model": "Octavia", "year_from": 2013, "year_to": 2020,
     "engine": "1.4/1.8 TSI", "category": "Motor", "severity": "medium",
     "issue": "Oljeförbrukning på vissa TSI-årsmodeller",
     "what_to_check": "Mät oljenivå mellan servicar. Fråga om kolvringsåtgärd gjorts.",
     "negotiation_leverage_sek": 12000},
    {"brand": "Skoda", "model": "Octavia", "year_from": 2013, "year_to": 2020,
     "engine": "DSG (DQ200)", "category": "Växellåda", "severity": "medium",
     "issue": "DSG-mekatronik kan ge ryckiga växlingar",
     "what_to_check": "Provkör i låga farter. Fråga om DSG-service.",
     "negotiation_leverage_sek": 15000},

    # --- VW Passat — diesel SCR/DPF + DSG -------------------------------------
    {"brand": "Volkswagen", "model": "Passat", "year_from": 2015, "year_to": 2023,
     "engine": "2.0 TDI", "category": "Motor", "severity": "medium",
     "issue": "AdBlue/SCR och DPF kan ge dyra fel",
     "what_to_check": "Kontrollera felfri AdBlue-doserare och DPF-status. Kolla felkoder.",
     "negotiation_leverage_sek": 12000},

    # --- Toyota Corolla — very reliable (selling point) -----------------------
    {"brand": "Toyota", "model": "Corolla", "year_from": 2013, "year_to": 2022,
     "engine": "Hybrid", "category": "El/Hybrid", "severity": "low",
     "issue": "Hybridbatteriets hälsa på äldre exemplar",
     "what_to_check": "Be om hybridbatteri-hälsotest hos Toyota. I övrigt mycket pålitlig modell.",
     "negotiation_leverage_sek": 8000},

    # --- Kia Ceed -------------------------------------------------------------
    {"brand": "Kia", "model": "Ceed", "year_from": 2012, "year_to": 2018,
     "engine": None, "category": "Motor", "severity": "low",
     "issue": "Kamrem-/kamkedjeintervall på vissa motorer",
     "what_to_check": "Fråga om kamrem bytts enligt intervall. Kolla att nybilsgarantin (7 år) ev. gäller.",
     "negotiation_leverage_sek": 7000},

    # --- Tesla Model 3 --------------------------------------------------------
    {"brand": "Tesla", "model": "Model 3", "year_from": 2019, "year_to": 2021,
     "engine": None, "category": "Chassi", "severity": "low",
     "issue": "Tidiga ex: länkarmar/bussningar kan slamra fram",
     "what_to_check": "Lyssna efter slammer fram på ojämn väg. Fråga om länkarmar bytts på garanti.",
     "negotiation_leverage_sek": 6000},
    {"brand": "Tesla", "model": "Model 3", "year_from": 2019, "year_to": 2022,
     "engine": None, "category": "El", "severity": "low",
     "issue": "12V-batteri och skärm/MCU kan behöva åtgärd; ojämnt däckslitage",
     "what_to_check": "Kontrollera skärm och mjukvaruversion, 12V-batteristatus och däckslitage/hjulinställning.",
     "negotiation_leverage_sek": 5000},
]

# ---------------------------------------------------------------------------
# Added 2026-09-26: well-documented faults for the most common models on the
# Swedish used market. Same rules: prompts to verify, not diagnoses.
# ---------------------------------------------------------------------------
_PURETECH = {
    "engine": "1.2 PureTech (EB2)", "category": "Motor", "severity": "high",
    "issue": "Kamremmen går i olja och kan brytas ned → skräp i oljesystemet, motorskada",
    "what_to_check": ("Fråga när kamremmen senast byttes (tillverkaren har kortat intervallet). "
                      "Kolla oljeförbrukning och att inga varningslampor lyst. Begär kvitto."),
    "negotiation_leverage_sek": 15000,
}
_ECOBOOST = {
    "engine": "1.0 EcoBoost", "category": "Motor", "severity": "high",
    "issue": "Kylvätskeläckage/överhettning kan skada topplocket",
    "what_to_check": ("Kontrollera kylvätskenivån och fråga om kylslangar/termostat åtgärdats. "
                      "Undvik bilar som gått varma. Be om servicehistorik."),
    "negotiation_leverage_sek": 15000,
}
_DQ200 = {
    "engine": "DSG (DQ200)", "category": "Växellåda", "severity": "medium",
    "issue": "DSG-mekatronik/koppling kan strula",
    "what_to_check": "Provkör i låga farter och kö: ryck eller glapp vid växling? Fråga om DSG-service.",
    "negotiation_leverage_sek": 15000,
}
_EA189 = {
    "engine": "2.0/1.6 TDI (EA189)", "category": "Motor", "severity": "low",
    "issue": "Dieselgate-uppdatering: vissa får EGR/DPF-problem efter mjukvaruåtgärden",
    "what_to_check": "Kontrollera att åtgärden gjorts och fråga om EGR-/DPF-historik efteråt.",
    "negotiation_leverage_sek": 8000,
}
_N47 = {
    "engine": "N47 diesel", "category": "Motor", "severity": "high",
    "issue": "Kamkedja kan sträckas/haverera (sitter baktill på motorn)",
    "what_to_check": "Lyssna efter rassel vid kallstart. Fråga om kedjan bytts.",
    "negotiation_leverage_sek": 25000,
}
_HYBRID_BATTERY = {
    "engine": "Hybrid", "category": "El/Hybrid", "severity": "low",
    "issue": "Hybridbatteriets hälsa på äldre exemplar",
    "what_to_check": "Be om hybridbatteri-hälsotest hos märkesverkstad. I övrigt mycket pålitlig.",
    "negotiation_leverage_sek": 8000,
}

ISSUES += [
    {"brand": "Peugeot", "model": "308", "year_from": 2014, "year_to": 2022, **_PURETECH},
    {"brand": "Peugeot", "model": "3008", "year_from": 2016, "year_to": 2022, **_PURETECH},
    {"brand": "Peugeot", "model": "208", "year_from": 2014, "year_to": 2022, **_PURETECH},
    {"brand": "Ford", "model": "Focus", "year_from": 2012, "year_to": 2018, **_ECOBOOST},
    {"brand": "Ford", "model": "Fiesta", "year_from": 2012, "year_to": 2018, **_ECOBOOST},
    {"brand": "Ford", "model": "Focus", "year_from": 2011, "year_to": 2016,
     "engine": "PowerShift (DPS6)", "category": "Växellåda", "severity": "medium",
     "issue": "PowerShift-automatlåda kan rycka/slira (torrkoppling)",
     "what_to_check": "Provkör i stadstrafik: skakningar vid start? Fråga om kopplingsbyte/programvara.",
     "negotiation_leverage_sek": 12000},
    {"brand": "BMW", "model": "3-serie", "year_from": 2012, "year_to": 2015,
     "engine": "N20 bensin", "category": "Motor", "severity": "high",
     "issue": "Kamkedjans styrningar kan slitas (N20 2.0 bensin)",
     "what_to_check": "Lyssna efter visslande/rasslande ljud. Fråga om kedjesats bytts.",
     "negotiation_leverage_sek": 20000},
    {"brand": "BMW", "model": "X1", "year_from": 2009, "year_to": 2014, **_N47},
    {"brand": "BMW", "model": "X3", "year_from": 2010, "year_to": 2014, **_N47},
    {"brand": "BMW", "model": "5-serie", "year_from": 2010, "year_to": 2014, **_N47},
    {"brand": "Nissan", "model": "Leaf", "year_from": 2011, "year_to": 2017,
     "engine": None, "category": "El/Batteri", "severity": "high",
     "issue": "Batterikapaciteten minskar (ingen aktiv batterikylning) → kortare räckvidd",
     "what_to_check": "Be om batterihälsa (SOH) från verkstad eller app. Räkna kapacitetsstaplarna.",
     "negotiation_leverage_sek": 30000},
    {"brand": "Mitsubishi", "model": "Outlander", "year_from": 2013, "year_to": 2020,
     "engine": "PHEV", "category": "El/Batteri", "severity": "medium",
     "issue": "Batterikapacitet och elräckvidd sjunker med åren",
     "what_to_check": "Ladda fullt och kontrollera elräckvidden. Be om batteritest.",
     "negotiation_leverage_sek": 15000},
    {"brand": "Volvo", "model": "XC90", "year_from": 2015, "year_to": 2018,
     "engine": "T5/T6 Drive-E bensin", "category": "Motor", "severity": "medium",
     "issue": "Oljeförbrukning på vissa bensinmotorer (kolvringar)",
     "what_to_check": "Fråga om oljeförbrukning och om åtgärd gjorts. Kolla oljenivån.",
     "negotiation_leverage_sek": 15000},
    {"brand": "Volvo", "model": "V60", "year_from": 2015, "year_to": 2018,
     "engine": "T5/T6 Drive-E bensin", "category": "Motor", "severity": "medium",
     "issue": "Oljeförbrukning på vissa bensinmotorer (kolvringar)",
     "what_to_check": "Fråga om oljeförbrukning och om åtgärd gjorts. Kolla oljenivån.",
     "negotiation_leverage_sek": 15000},
    {"brand": "Volkswagen", "model": "Passat", "year_from": 2009, "year_to": 2015, **_EA189},
    {"brand": "Volkswagen", "model": "Golf", "year_from": 2009, "year_to": 2015, **_EA189},
    {"brand": "Volkswagen", "model": "Tiguan", "year_from": 2009, "year_to": 2015, **_EA189},
    {"brand": "Skoda", "model": "Octavia", "year_from": 2009, "year_to": 2015, **_EA189},
    {"brand": "Volkswagen", "model": "Polo", "year_from": 2010, "year_to": 2016, **_DQ200},
    {"brand": "Audi", "model": "A3", "year_from": 2008, "year_to": 2016, **_DQ200},
    {"brand": "Seat", "model": "Leon", "year_from": 2008, "year_to": 2016, **_DQ200},
    {"brand": "Mercedes-Benz", "model": "C-Klass", "year_from": 2008, "year_to": 2015,
     "engine": "OM651 diesel", "category": "Motor", "severity": "medium",
     "issue": "Insprutare och kamkedja kan ge problem (OM651)",
     "what_to_check": "Ojämn tomgång eller rassel vid kallstart? Fråga om insprutare bytts.",
     "negotiation_leverage_sek": 15000},
    {"brand": "Mercedes-Benz", "model": "E-Klass", "year_from": 2009, "year_to": 2015,
     "engine": "OM651 diesel", "category": "Motor", "severity": "medium",
     "issue": "Insprutare och kamkedja kan ge problem (OM651)",
     "what_to_check": "Ojämn tomgång eller rassel vid kallstart? Fråga om insprutare bytts.",
     "negotiation_leverage_sek": 15000},
    {"brand": "Renault", "model": "Clio", "year_from": 2012, "year_to": 2016,
     "engine": "1.2 TCe (H5Ft)", "category": "Motor", "severity": "high",
     "issue": "Oljeförbrukning kan leda till motorskada (1.2 TCe)",
     "what_to_check": "Mät oljenivån, fråga om oljeförbrukning och tillverkarens åtgärd.",
     "negotiation_leverage_sek": 20000},
    {"brand": "Renault", "model": "Captur", "year_from": 2013, "year_to": 2016,
     "engine": "1.2 TCe (H5Ft)", "category": "Motor", "severity": "high",
     "issue": "Oljeförbrukning kan leda till motorskada (1.2 TCe)",
     "what_to_check": "Mät oljenivån, fråga om oljeförbrukning och tillverkarens åtgärd.",
     "negotiation_leverage_sek": 20000},
    {"brand": "Nissan", "model": "Qashqai", "year_from": 2014, "year_to": 2017,
     "engine": "1.2 DIG-T", "category": "Motor", "severity": "medium",
     "issue": "Oljeförbrukning/kamkedja på 1.2 DIG-T",
     "what_to_check": "Kolla oljenivå, lyssna efter kedjerassel vid kallstart.",
     "negotiation_leverage_sek": 12000},
    {"brand": "Mazda", "model": "6", "year_from": 2012, "year_to": 2017,
     "engine": "2.2 Skyactiv-D", "category": "Motor", "severity": "medium",
     "issue": "Oljeutspädning och sotning vid mycket kortkörning (2.2 diesel)",
     "what_to_check": "Oljenivå som stiger är varningstecken. Fråga om körmönster och DPF.",
     "negotiation_leverage_sek": 12000},
    {"brand": "Mazda", "model": "CX-5", "year_from": 2012, "year_to": 2017,
     "engine": "2.2 Skyactiv-D", "category": "Motor", "severity": "medium",
     "issue": "Oljeutspädning och sotning vid mycket kortkörning (2.2 diesel)",
     "what_to_check": "Oljenivå som stiger är varningstecken. Fråga om körmönster och DPF.",
     "negotiation_leverage_sek": 12000},
    {"brand": "Hyundai", "model": "Kona", "year_from": 2018, "year_to": 2020,
     "engine": "Electric", "category": "El/Batteri", "severity": "medium",
     "issue": "Återkallelse av batteripaket på Kona Electric (brandrisk)",
     "what_to_check": "Kontrollera hos märkesverkstad att återkallelsen är åtgärdad.",
     "negotiation_leverage_sek": 5000},
    {"brand": "Tesla", "model": "Model S", "year_from": 2012, "year_to": 2018,
     "engine": None, "category": "El", "severity": "medium",
     "issue": "Skärmens minne (MCU/eMMC) kan haverera; dörrhandtag kan krångla",
     "what_to_check": "Kontrollera att skärmen är snabb och att MCU-åtgärd gjorts. Testa alla handtag.",
     "negotiation_leverage_sek": 10000},
    {"brand": "Audi", "model": "Q5", "year_from": 2008, "year_to": 2012,
     "engine": "2.0 TFSI", "category": "Motor", "severity": "high",
     "issue": "Hög oljeförbrukning (slitna kolvringar) på 2.0 TFSI",
     "what_to_check": "Be om oljeförbruknings-historik och om kolvringsåtgärd gjorts.",
     "negotiation_leverage_sek": 15000},
    {"brand": "Toyota", "model": "Auris", "year_from": 2010, "year_to": 2018, **_HYBRID_BATTERY},
    {"brand": "Toyota", "model": "Prius", "year_from": 2004, "year_to": 2015, **_HYBRID_BATTERY},
]
