"""Curated technical specs — one representative configuration per (brand, model).

These are the static attributes a buyer filters on (drivetrain, body type, fuel
economy, power, tax, reliability) that you can't reliably read off a single
listing. Values are APPROXIMATE and representative of the most common variant;
extend / refine from car.info later. Keyed by (brand, model).

  body_type:  Kombi | Halvkombi | Sedan | SUV | Sportbil ...
  drivetrain: FWD (framhjul) | RWD (bakhjul) | AWD (fyrhjul)
  reliability: 1 (poor) .. 5 (excellent)
"""

SPECS = [
    {"brand": "Volvo", "model": "V60", "body_type": "Kombi", "drivetrain": "FWD",
     "power_hp": 150, "primary_fuel": "Diesel", "fuel_l_per_100km": 4.5,
     "energy_kwh_per_100km": None, "annual_tax_sek": 2400, "reliability": 4},

    {"brand": "Volvo", "model": "XC60", "body_type": "SUV", "drivetrain": "AWD",
     "power_hp": 190, "primary_fuel": "Diesel", "fuel_l_per_100km": 5.6,
     "energy_kwh_per_100km": None, "annual_tax_sek": 4800, "reliability": 3},

    {"brand": "Volkswagen", "model": "Golf", "body_type": "Halvkombi", "drivetrain": "FWD",
     "power_hp": 125, "primary_fuel": "Bensin", "fuel_l_per_100km": 5.2,
     "energy_kwh_per_100km": None, "annual_tax_sek": 1500, "reliability": 3},

    {"brand": "Volkswagen", "model": "Passat", "body_type": "Kombi", "drivetrain": "FWD",
     "power_hp": 150, "primary_fuel": "Diesel", "fuel_l_per_100km": 4.6,
     "energy_kwh_per_100km": None, "annual_tax_sek": 3200, "reliability": 3},

    {"brand": "Audi", "model": "A4", "body_type": "Kombi", "drivetrain": "FWD",
     "power_hp": 190, "primary_fuel": "Bensin", "fuel_l_per_100km": 6.4,
     "energy_kwh_per_100km": None, "annual_tax_sek": 1700, "reliability": 3},

    {"brand": "BMW", "model": "3-serie", "body_type": "Sedan", "drivetrain": "RWD",
     "power_hp": 184, "primary_fuel": "Diesel", "fuel_l_per_100km": 4.5,
     "energy_kwh_per_100km": None, "annual_tax_sek": 3000, "reliability": 3},

    {"brand": "Toyota", "model": "Corolla", "body_type": "Halvkombi", "drivetrain": "FWD",
     "power_hp": 122, "primary_fuel": "Hybrid", "fuel_l_per_100km": 4.4,
     "energy_kwh_per_100km": None, "annual_tax_sek": 700, "reliability": 5},

    {"brand": "Kia", "model": "Ceed", "body_type": "Halvkombi", "drivetrain": "FWD",
     "power_hp": 120, "primary_fuel": "Bensin", "fuel_l_per_100km": 5.8,
     "energy_kwh_per_100km": None, "annual_tax_sek": 1500, "reliability": 4},

    {"brand": "Skoda", "model": "Octavia", "body_type": "Kombi", "drivetrain": "FWD",
     "power_hp": 150, "primary_fuel": "Bensin", "fuel_l_per_100km": 5.4,
     "energy_kwh_per_100km": None, "annual_tax_sek": 1600, "reliability": 3},

    {"brand": "Tesla", "model": "Model 3", "body_type": "Sedan", "drivetrain": "RWD",
     "power_hp": 283, "primary_fuel": "El", "fuel_l_per_100km": None,
     "energy_kwh_per_100km": 15.0, "annual_tax_sek": 360, "reliability": 4},
]
