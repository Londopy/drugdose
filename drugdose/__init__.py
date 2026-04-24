"""
drugdose — EMS & Clinical Drug Dosing Calculator Library
=========================================================

Quick Start
-----------
>>> from drugdose import Patient, calculate_dose, calculate_drip
>>> patient = Patient(weight_kg=70, age_years=35, allergies=["codeine"])
>>> result = calculate_dose("morphine", patient, route="IV")
>>> print(result.summary())
Morphine Sulfate IV: 7.000 mg → 7.00 mL [...]

>>> drip = calculate_drip("dopamine", patient, ordered_dose=5, dose_unit="mcg/kg/min")
>>> print(drip.summary())
Dopamine drip @ 5 mcg/kg/min: 13.13 mL/hr  (bag lasts X hr)

Public API
----------
Models:
    Patient         — patient demographic and clinical profile
    Drug            — drug entry from the database
    DoseResult      — result of calculate_dose()
    DripResult      — result of calculate_drip()
    InteractionFlag — drug-drug interaction detail
    ContraindicationFlag — contraindication detail

Functions:
    calculate_dose()    — weight-based single-dose calculation
    calculate_range()   — compute min & max dose pair
    calculate_drip()    — IV infusion pump-rate calculation
    standard_mixture()  — compute concentration for a custom mix
    get_drug()          — look up a drug by name
    search_drugs()      — full-text search of the database
    get_all_drugs()     — return the full database dict

Exceptions:
    DrugDoseError           — base exception
    DrugNotFoundError
    InvalidRouteError
    InvalidPatientError
    ContraindicatedError
    WeightError
    ConcentrationError
"""

__version__ = "0.1.0"
__author__ = "London Chowdhury"
__email__ = "londonchowdhury.college@gmail.com"
__license__ = "MIT"

# ── Public re-exports ─────────────────────────────────────────────────────
from .calculator import calculate_dose, calculate_range
from .checker import check_contraindications, check_interactions, full_safety_check
from .db import get_all_drugs, get_drug, get_interactions, get_interactions_for, search_drugs
from .drip import calculate_drip, standard_mixture
from .exceptions import (
    ConcentrationError,
    ContraindicatedError,
    DrugDoseError,
    DrugNotFoundError,
    InvalidPatientError,
    InvalidRouteError,
    WeightError,
)
from .models.drug import Drug, RouteConfig
from .models.patient import Patient
from .models.result import ContraindicationFlag, DoseResult, DripResult, InteractionFlag

__all__ = [
    # Version
    "__version__",
    # Core functions
    "calculate_dose",
    "calculate_range",
    "calculate_drip",
    "standard_mixture",
    # Database
    "get_drug",
    "get_all_drugs",
    "search_drugs",
    "get_interactions",
    "get_interactions_for",
    # Safety
    "check_contraindications",
    "check_interactions",
    "full_safety_check",
    # Models
    "Drug",
    "RouteConfig",
    "Patient",
    "DoseResult",
    "DripResult",
    "InteractionFlag",
    "ContraindicationFlag",
    # Exceptions
    "DrugDoseError",
    "DrugNotFoundError",
    "InvalidRouteError",
    "InvalidPatientError",
    "ContraindicatedError",
    "WeightError",
    "ConcentrationError",
]
