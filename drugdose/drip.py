"""
IV drip rate calculator.

Converts a desired dose (in weight-based or absolute rate units) into
a pump rate in mL/hr, given an infusion bag concentration.
"""

from __future__ import annotations

from typing import Optional

from .db import get_drug
from .exceptions import ConcentrationError, DrugNotFoundError, InvalidRouteError
from .models.patient import Patient
from .models.result import DripResult


# ---------------------------------------------------------------------------
# Unit parsing helpers
# ---------------------------------------------------------------------------


def _normalize_dose_to_mg_per_min(
    ordered_dose: float,
    dose_unit: str,
    weight_kg: float,
) -> float:
    """
    Convert any supported dose rate unit into mg/min absolute.

    Supported dose_unit values
    --------------------------
    'mcg/kg/min' | 'mcg/kg/hr'
    'mg/kg/min'  | 'mg/kg/hr'
    'mcg/min'    | 'mcg/hr'
    'mg/min'     | 'mg/hr'
    'units/min'  | 'units/hr'   (treated as mg=unit for simplicity)
    'g/hr'                       (grams/hr)
    """
    u = dose_unit.lower().strip()

    if "mcg" in u:
        factor = 1 / 1000.0  # mcg → mg
    elif "g/hr" in u and "mcg" not in u and "mg" not in u:
        factor = 1000.0       # g → mg
    else:
        factor = 1.0          # mg stays mg / units stay as-is

    if "kg" in u:
        dose_mg_rate = ordered_dose * factor * weight_kg
    else:
        dose_mg_rate = ordered_dose * factor

    # Now normalise to /min
    if "/hr" in u:
        dose_mg_rate /= 60.0

    return dose_mg_rate  # mg/min


# ---------------------------------------------------------------------------
# Main public function
# ---------------------------------------------------------------------------


def calculate_drip(
    drug_name: str,
    patient: Patient,
    ordered_dose: float,
    dose_unit: str,
    concentration_mg_ml: Optional[float] = None,
    bag_volume_ml: float = 250.0,
) -> DripResult:
    """
    Calculate IV infusion pump rate for a continuous drip.

    Parameters
    ----------
    drug_name:
        Drug name or brand name.
    patient:
        Patient object with weight.
    ordered_dose:
        Desired dose in *dose_unit* (e.g. 5.0 for 5 mcg/kg/min).
    dose_unit:
        Rate unit string. Supported: 'mcg/kg/min', 'mcg/kg/hr', 'mg/kg/min',
        'mg/kg/hr', 'mcg/min', 'mcg/hr', 'mg/min', 'mg/hr', 'g/hr',
        'units/min', 'units/hr', 'units/kg/hr'.
    concentration_mg_ml:
        Drug concentration in the IV bag (mg/mL). Uses database default if None.
    bag_volume_ml:
        Total volume of the infusion bag in mL (default 250 mL).

    Returns
    -------
    DripResult
        Pump rate in mL/hr and mL/min, duration, and safety warnings.
    """
    drug = get_drug(drug_name)
    if drug is None:
        raise DrugNotFoundError(drug_name)

    # Find a continuous infusion route config for reference data
    drip_routes = [
        rc for rc in drug.routes
        if rc.continuous_infusion or rc.route.upper() in ("IV_DRIP", "DRIP", "INFUSION")
    ]
    rc = drip_routes[0] if drip_routes else None

    # Concentration
    if concentration_mg_ml is None:
        if rc and rc.standard_concentration_mg_ml:
            concentration_mg_ml = rc.standard_concentration_mg_ml
        else:
            raise ConcentrationError(
                f"No concentration provided and no default found for {drug.display_name}. "
                "Please supply concentration_mg_ml."
            )

    # ------------------------------------------------------------------ #
    # Core calculation                                                      #
    # ------------------------------------------------------------------ #
    dose_mg_per_min = _normalize_dose_to_mg_per_min(
        ordered_dose, dose_unit, patient.weight_kg
    )
    rate_ml_per_min = dose_mg_per_min / concentration_mg_ml
    rate_ml_per_hr = rate_ml_per_min * 60.0
    duration_hr = bag_volume_ml / rate_ml_per_hr if rate_ml_per_hr > 0 else None

    # ------------------------------------------------------------------ #
    # Safety checks                                                         #
    # ------------------------------------------------------------------ #
    warnings: list[str] = []
    rate_exceeded = False
    max_rate: Optional[float] = None

    # Check if ordered dose exceeds the drug's documented maximum
    if rc is not None:
        dose_in_native = ordered_dose
        # Convert ordered dose to the same units as the RouteConfig for comparison
        if rc.is_per_min and "/hr" in dose_unit.lower():
            dose_in_native = ordered_dose / 60.0
        elif not rc.is_per_min and "/min" in dose_unit.lower():
            dose_in_native = ordered_dose * 60.0

        if dose_in_native > rc.dose_max and rc.dose_max > 0:
            warnings.append(
                f"Ordered dose {ordered_dose} {dose_unit} exceeds documented maximum "
                f"{rc.dose_max} {rc.dose_unit} for {drug.display_name}."
            )
            rate_exceeded = True

    if rate_ml_per_hr < 0.1:
        warnings.append(
            f"Very low infusion rate ({rate_ml_per_hr:.3f} mL/hr). "
            "Verify dose and concentration — risk of inadequate delivery."
        )

    if rate_ml_per_hr > 999:
        warnings.append(
            f"Extremely high rate ({rate_ml_per_hr:.1f} mL/hr). "
            "Recheck concentration and dose calculation."
        )

    if drug.controlled_substance:
        warnings.append(
            f"Controlled substance ({drug.controlled_substance}). "
            "Document infusion in controlled substance log."
        )

    if duration_hr is not None and duration_hr < 1:
        warnings.append(
            f"Bag ({bag_volume_ml} mL) will empty in {duration_hr * 60:.0f} minutes at this rate. "
            "Prepare replacement bag in advance."
        )

    return DripResult(
        drug_name=drug.name,
        display_name=drug.display_name,
        route="IV_DRIP",
        ordered_dose=ordered_dose,
        dose_unit=dose_unit,
        patient_weight_kg=patient.weight_kg,
        concentration_mg_ml=concentration_mg_ml,
        bag_volume_ml=bag_volume_ml,
        dose_mg_per_min=dose_mg_per_min,
        rate_ml_per_hr=rate_ml_per_hr,
        rate_ml_per_min=rate_ml_per_min,
        duration_hr=duration_hr,
        warnings=warnings,
        max_rate_ml_per_hr=max_rate,
        rate_exceeded=rate_exceeded,
    )


def standard_mixture(
    drug_name: str,
    total_drug_mg: float,
    bag_volume_ml: float = 250.0,
) -> float:
    """
    Return the standard concentration (mg/mL) for a custom mixture.

    Parameters
    ----------
    drug_name:
        Drug name (informational only — used for display).
    total_drug_mg:
        Total milligrams added to the bag.
    bag_volume_ml:
        Total bag volume in mL.

    Returns
    -------
    float
        Concentration in mg/mL.
    """
    if bag_volume_ml <= 0:
        raise ValueError("Bag volume must be > 0 mL.")
    return total_drug_mg / bag_volume_ml
