"""Curated technical specs: representative configurations per (brand, model, fuel).

These are the static attributes a buyer filters on (drivetrain, body type, fuel
economy, power, tax, reliability) that a listing doesn't reliably state. Values
are APPROXIMATE and representative of the most common variant of each fuel type
on the Swedish used market. They drive filters and rough running-cost estimates,
not exact figures. What the ad itself states (fuel, AWD, hp) always wins in the
matcher. Refine from car.info as real data shows which variants dominate.

  body_type:   Kombi | Halvkombi | Sedan | SUV | Familjebuss
  drivetrain:  FWD (framhjul) | RWD (bakhjul) | AWD (fyrhjul)
  consumption: real-world mixed driving; PHEVs have both litres and kWh
  tax:         approximate yearly fordonsskatt for a typical model year
  reliability: 1 (poor) .. 5 (excellent), a rough read of Swedish/European
               reliability surveys and known faults. One row per model.
  is_default:  the row used when the ad's fuel doesn't match any variant
"""


def _s(brand, model, body, drive, hp, fuel, l100=None, kwh=None, tax=None, rel=3, default=False):
    return {"brand": brand, "model": model, "body_type": body, "drivetrain": drive,
            "power_hp": hp, "primary_fuel": fuel, "fuel_l_per_100km": l100,
            "energy_kwh_per_100km": kwh, "annual_tax_sek": tax, "reliability": rel,
            "is_default": 1 if default else 0}


SPECS = [
    # --- the original ten (defaults unchanged) ---------------------------------
    _s("Volvo", "V60", "Kombi", "FWD", 150, "Diesel", 4.5, None, 2400, 4, default=True),
    _s("Volvo", "V60", "Kombi", "FWD", 190, "Bensin", 6.8, None, 1800, 4),
    _s("Volvo", "V60", "Kombi", "AWD", 340, "Laddhybrid", 2.5, 12.0, 900, 3),
    _s("Volvo", "XC60", "SUV", "AWD", 190, "Diesel", 5.6, None, 4800, 3, default=True),
    _s("Volvo", "XC60", "SUV", "AWD", 250, "Bensin", 8.0, None, 3000, 3),
    _s("Volvo", "XC60", "SUV", "AWD", 350, "Laddhybrid", 2.8, 14.0, 1000, 3),
    _s("Volkswagen", "Golf", "Halvkombi", "FWD", 125, "Bensin", 5.2, None, 1500, 3, default=True),
    _s("Volkswagen", "Golf", "Halvkombi", "FWD", 115, "Diesel", 4.4, None, 2200, 3),
    _s("Volkswagen", "Golf", "Halvkombi", "FWD", 136, "El", None, 15.0, 360, 3),
    _s("Volkswagen", "Golf", "Halvkombi", "FWD", 204, "Laddhybrid", 2.5, 11.0, 800, 3),
    _s("Volkswagen", "Passat", "Kombi", "FWD", 150, "Diesel", 4.6, None, 3200, 3, default=True),
    _s("Volkswagen", "Passat", "Kombi", "FWD", 150, "Bensin", 6.3, None, 1600, 3),
    _s("Volkswagen", "Passat", "Kombi", "FWD", 218, "Laddhybrid", 2.5, 12.0, 900, 3),
    _s("Audi", "A4", "Kombi", "FWD", 190, "Bensin", 6.4, None, 1700, 3, default=True),
    _s("Audi", "A4", "Kombi", "FWD", 150, "Diesel", 5.0, None, 2600, 3),
    _s("BMW", "3-serie", "Sedan", "RWD", 184, "Diesel", 4.5, None, 3000, 3, default=True),
    _s("BMW", "3-serie", "Sedan", "RWD", 184, "Bensin", 6.5, None, 1600, 3),
    _s("BMW", "3-serie", "Sedan", "RWD", 292, "Laddhybrid", 2.3, 13.0, 900, 3),
    _s("Toyota", "Corolla", "Halvkombi", "FWD", 122, "Hybrid", 4.4, None, 700, 5, default=True),
    _s("Kia", "Ceed", "Halvkombi", "FWD", 120, "Bensin", 5.8, None, 1500, 4, default=True),
    _s("Kia", "Ceed", "Halvkombi", "FWD", 136, "Diesel", 4.8, None, 2000, 4),
    _s("Kia", "Ceed", "Kombi", "FWD", 141, "Laddhybrid", 2.5, 11.0, 800, 4),
    _s("Skoda", "Octavia", "Kombi", "FWD", 150, "Bensin", 5.4, None, 1600, 3, default=True),
    _s("Skoda", "Octavia", "Kombi", "FWD", 150, "Diesel", 4.6, None, 2300, 3),
    _s("Skoda", "Octavia", "Kombi", "FWD", 204, "Laddhybrid", 2.3, 12.0, 800, 3),
    _s("Tesla", "Model 3", "Sedan", "RWD", 283, "El", None, 15.0, 360, 4, default=True),

    # --- Volvo -----------------------------------------------------------------
    _s("Volvo", "V70", "Kombi", "FWD", 163, "Diesel", 5.6, None, 2600, 4, default=True),
    _s("Volvo", "V70", "Kombi", "FWD", 180, "Bensin", 8.0, None, 1900, 4),
    _s("Volvo", "XC70", "Kombi", "AWD", 181, "Diesel", 6.2, None, 3400, 4, default=True),
    _s("Volvo", "V90", "Kombi", "FWD", 190, "Diesel", 5.0, None, 2900, 3, default=True),
    _s("Volvo", "V90", "Kombi", "AWD", 390, "Laddhybrid", 2.8, 15.0, 1000, 3),
    _s("Volvo", "XC90", "SUV", "AWD", 235, "Diesel", 6.5, None, 5500, 3, default=True),
    _s("Volvo", "XC90", "SUV", "AWD", 390, "Laddhybrid", 3.0, 16.0, 1200, 3),
    _s("Volvo", "XC40", "SUV", "FWD", 163, "Bensin", 7.2, None, 2000, 4, default=True),
    _s("Volvo", "XC40", "SUV", "FWD", 262, "Laddhybrid", 2.5, 13.0, 900, 4),
    _s("Volvo", "XC40", "SUV", "AWD", 408, "El", None, 21.0, 360, 3),
    _s("Volvo", "V40", "Halvkombi", "FWD", 120, "Diesel", 4.2, None, 1300, 4, default=True),
    _s("Volvo", "V40", "Halvkombi", "FWD", 152, "Bensin", 6.0, None, 1300, 4),
    _s("Volvo", "S60", "Sedan", "FWD", 190, "Diesel", 4.8, None, 2400, 4, default=True),

    # --- Volkswagen --------------------------------------------------------------
    _s("Volkswagen", "Polo", "Halvkombi", "FWD", 95, "Bensin", 5.3, None, 1100, 3, default=True),
    _s("Volkswagen", "Tiguan", "SUV", "AWD", 150, "Diesel", 6.0, None, 3500, 3, default=True),
    _s("Volkswagen", "Tiguan", "SUV", "FWD", 150, "Bensin", 7.2, None, 1900, 3),
    _s("Volkswagen", "Tiguan", "SUV", "FWD", 245, "Laddhybrid", 2.5, 14.0, 900, 3),
    _s("Volkswagen", "ID.3", "Halvkombi", "RWD", 204, "El", None, 16.0, 360, 3, default=True),
    _s("Volkswagen", "ID.4", "SUV", "RWD", 204, "El", None, 18.5, 360, 3, default=True),
    _s("Volkswagen", "Touran", "Familjebuss", "FWD", 115, "Diesel", 5.0, None, 2300, 3, default=True),

    # --- Audi --------------------------------------------------------------------
    _s("Audi", "A3", "Halvkombi", "FWD", 150, "Bensin", 5.8, None, 1300, 3, default=True),
    _s("Audi", "A3", "Halvkombi", "FWD", 150, "Diesel", 4.5, None, 2200, 3),
    _s("Audi", "A6", "Kombi", "FWD", 190, "Diesel", 5.5, None, 3200, 3, default=True),
    _s("Audi", "Q5", "SUV", "AWD", 190, "Diesel", 6.3, None, 3900, 3, default=True),
    _s("Audi", "Q5", "SUV", "AWD", 367, "Laddhybrid", 2.8, 15.0, 1100, 3),
    _s("Audi", "Q3", "SUV", "FWD", 150, "Bensin", 7.0, None, 1900, 3, default=True),
    _s("Audi", "e-tron", "SUV", "AWD", 408, "El", None, 23.0, 360, 3, default=True),

    # --- BMW ---------------------------------------------------------------------
    _s("BMW", "5-serie", "Sedan", "RWD", 190, "Diesel", 5.0, None, 3000, 3, default=True),
    _s("BMW", "5-serie", "Sedan", "RWD", 252, "Laddhybrid", 2.3, 15.0, 1000, 3),
    _s("BMW", "X1", "SUV", "FWD", 150, "Diesel", 5.0, None, 2600, 3, default=True),
    _s("BMW", "X3", "SUV", "AWD", 190, "Diesel", 5.8, None, 3600, 3, default=True),
    _s("BMW", "i3", "Halvkombi", "RWD", 170, "El", None, 15.0, 360, 4, default=True),

    # --- Mercedes-Benz -------------------------------------------------------------
    _s("Mercedes-Benz", "C-Klass", "Sedan", "RWD", 170, "Diesel", 5.0, None, 2900, 3, default=True),
    _s("Mercedes-Benz", "C-Klass", "Sedan", "RWD", 184, "Bensin", 6.8, None, 1800, 3),
    _s("Mercedes-Benz", "C-Klass", "Sedan", "RWD", 320, "Laddhybrid", 2.2, 14.0, 1000, 3),
    _s("Mercedes-Benz", "E-Klass", "Sedan", "RWD", 194, "Diesel", 5.3, None, 3100, 3, default=True),
    _s("Mercedes-Benz", "A-Klass", "Halvkombi", "FWD", 136, "Bensin", 6.0, None, 1400, 3, default=True),
    _s("Mercedes-Benz", "GLC", "SUV", "AWD", 194, "Diesel", 6.2, None, 3900, 3, default=True),

    # --- Toyota --------------------------------------------------------------------
    _s("Toyota", "Auris", "Halvkombi", "FWD", 136, "Hybrid", 4.4, None, 700, 5, default=True),
    _s("Toyota", "Auris", "Halvkombi", "FWD", 116, "Bensin", 6.0, None, 1200, 5),
    _s("Toyota", "RAV4", "SUV", "AWD", 218, "Hybrid", 5.6, None, 1600, 5, default=True),
    _s("Toyota", "RAV4", "SUV", "AWD", 306, "Laddhybrid", 1.5, 16.0, 900, 5),
    _s("Toyota", "Yaris", "Halvkombi", "FWD", 116, "Hybrid", 4.0, None, 600, 5, default=True),
    _s("Toyota", "C-HR", "SUV", "FWD", 122, "Hybrid", 4.9, None, 900, 5, default=True),
    _s("Toyota", "Prius", "Halvkombi", "FWD", 122, "Hybrid", 4.2, None, 500, 5, default=True),

    # --- Kia / Hyundai -------------------------------------------------------------
    _s("Kia", "Niro", "SUV", "FWD", 141, "Hybrid", 4.8, None, 800, 4, default=True),
    _s("Kia", "Niro", "SUV", "FWD", 141, "Laddhybrid", 2.5, 12.0, 700, 4),
    _s("Kia", "Niro", "SUV", "FWD", 204, "El", None, 16.5, 360, 4),
    _s("Kia", "Sportage", "SUV", "FWD", 136, "Diesel", 6.0, None, 2800, 4, default=True),
    _s("Kia", "Sportage", "SUV", "AWD", 177, "Bensin", 8.0, None, 2200, 4),
    _s("Kia", "Optima", "Kombi", "FWD", 205, "Laddhybrid", 2.5, 12.0, 800, 4, default=True),
    _s("Hyundai", "i30", "Halvkombi", "FWD", 140, "Bensin", 6.0, None, 1400, 4, default=True),
    _s("Hyundai", "i30", "Kombi", "FWD", 136, "Diesel", 4.6, None, 2100, 4),
    _s("Hyundai", "Tucson", "SUV", "FWD", 141, "Diesel", 6.2, None, 2900, 4, default=True),
    _s("Hyundai", "Tucson", "SUV", "AWD", 265, "Laddhybrid", 2.5, 15.0, 900, 4),
    _s("Hyundai", "Kona", "SUV", "FWD", 204, "El", None, 16.0, 360, 4, default=True),
    _s("Hyundai", "Kona", "SUV", "FWD", 120, "Bensin", 6.2, None, 1500, 4),
    _s("Hyundai", "Ioniq", "Halvkombi", "FWD", 141, "Hybrid", 4.0, None, 500, 4, default=True),
    _s("Hyundai", "Ioniq", "Halvkombi", "FWD", 136, "El", None, 13.5, 360, 4),

    # --- Skoda / Seat --------------------------------------------------------------
    _s("Skoda", "Superb", "Kombi", "FWD", 150, "Diesel", 5.2, None, 2800, 3, default=True),
    _s("Skoda", "Superb", "Kombi", "FWD", 218, "Laddhybrid", 2.4, 13.0, 900, 3),
    _s("Skoda", "Fabia", "Halvkombi", "FWD", 95, "Bensin", 5.2, None, 1000, 3, default=True),
    _s("Skoda", "Kodiaq", "SUV", "AWD", 190, "Diesel", 6.5, None, 3800, 3, default=True),
    _s("Seat", "Leon", "Halvkombi", "FWD", 150, "Bensin", 5.8, None, 1300, 3, default=True),

    # --- Tesla / Polestar ------------------------------------------------------------
    _s("Tesla", "Model Y", "SUV", "AWD", 350, "El", None, 17.0, 360, 3, default=True),
    _s("Tesla", "Model S", "Sedan", "AWD", 420, "El", None, 20.0, 360, 3, default=True),
    _s("Polestar", "2", "Halvkombi", "AWD", 408, "El", None, 19.0, 360, 3, default=True),

    # --- Ford ------------------------------------------------------------------------
    _s("Ford", "Focus", "Halvkombi", "FWD", 125, "Bensin", 6.0, None, 1300, 3, default=True),
    _s("Ford", "Focus", "Kombi", "FWD", 120, "Diesel", 4.7, None, 2100, 3),
    _s("Ford", "Kuga", "SUV", "FWD", 150, "Diesel", 6.0, None, 3000, 3, default=True),
    _s("Ford", "Kuga", "SUV", "FWD", 225, "Laddhybrid", 2.0, 15.0, 900, 3),
    _s("Ford", "Mondeo", "Kombi", "FWD", 150, "Diesel", 5.3, None, 2700, 3, default=True),
    _s("Ford", "Fiesta", "Halvkombi", "FWD", 100, "Bensin", 5.5, None, 1100, 3, default=True),

    # --- Peugeot / Renault / Nissan / Opel / Dacia -------------------------------------
    _s("Peugeot", "308", "Halvkombi", "FWD", 130, "Bensin", 5.8, None, 1200, 2, default=True),
    _s("Peugeot", "308", "Kombi", "FWD", 120, "Diesel", 4.3, None, 1900, 3),
    _s("Peugeot", "3008", "SUV", "FWD", 130, "Bensin", 6.5, None, 1500, 3, default=True),
    _s("Peugeot", "3008", "SUV", "FWD", 130, "Diesel", 5.0, None, 2300, 3),
    _s("Peugeot", "208", "Halvkombi", "FWD", 100, "Bensin", 5.5, None, 1100, 3, default=True),
    _s("Peugeot", "208", "Halvkombi", "FWD", 136, "El", None, 16.0, 360, 3),
    _s("Renault", "Clio", "Halvkombi", "FWD", 90, "Bensin", 5.5, None, 1100, 3, default=True),
    _s("Renault", "Megane", "Kombi", "FWD", 110, "Diesel", 4.3, None, 1800, 3, default=True),
    _s("Renault", "Megane", "Halvkombi", "FWD", 130, "Bensin", 6.2, None, 1400, 3),
    _s("Renault", "Zoe", "Halvkombi", "FWD", 135, "El", None, 16.0, 360, 3, default=True),
    _s("Renault", "Captur", "SUV", "FWD", 130, "Bensin", 6.2, None, 1300, 3, default=True),
    _s("Nissan", "Qashqai", "SUV", "FWD", 140, "Bensin", 6.5, None, 1600, 3, default=True),
    _s("Nissan", "Qashqai", "SUV", "FWD", 115, "Diesel", 5.0, None, 2200, 3),
    _s("Nissan", "Leaf", "Halvkombi", "FWD", 150, "El", None, 17.0, 360, 3, default=True),
    _s("Opel", "Astra", "Halvkombi", "FWD", 125, "Bensin", 6.2, None, 1400, 3, default=True),
    _s("Opel", "Astra", "Kombi", "FWD", 136, "Diesel", 4.6, None, 2000, 3),
    _s("Dacia", "Duster", "SUV", "FWD", 130, "Bensin", 6.8, None, 1700, 3, default=True),

    # --- Mazda / Honda / Subaru / Mitsubishi ---------------------------------------------
    _s("Mazda", "3", "Halvkombi", "FWD", 120, "Bensin", 6.2, None, 1500, 5, default=True),
    _s("Mazda", "6", "Kombi", "FWD", 150, "Diesel", 5.2, None, 2600, 4, default=True),
    _s("Mazda", "6", "Kombi", "FWD", 165, "Bensin", 6.8, None, 1800, 4),
    _s("Mazda", "CX-5", "SUV", "FWD", 165, "Bensin", 7.2, None, 2000, 4, default=True),
    _s("Mazda", "CX-5", "SUV", "AWD", 150, "Diesel", 5.8, None, 3100, 4),
    _s("Honda", "CR-V", "SUV", "AWD", 184, "Hybrid", 5.8, None, 1600, 4, default=True),
    _s("Honda", "CR-V", "SUV", "AWD", 173, "Bensin", 7.5, None, 2200, 4),
    _s("Honda", "Civic", "Halvkombi", "FWD", 129, "Bensin", 6.0, None, 1400, 4, default=True),
    _s("Subaru", "Outback", "Kombi", "AWD", 175, "Bensin", 8.2, None, 2300, 4, default=True),
    _s("Mitsubishi", "Outlander", "SUV", "AWD", 200, "Laddhybrid", 2.5, 15.0, 900, 3, default=True),
]
