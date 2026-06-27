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
