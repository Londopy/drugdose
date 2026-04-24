"""
Core dose calculation engine.

Public API:
    calculate_dose(drug_name, patient, route, concentration_mg_ml) -> DoseResult
"""

from __future__ import annotations

from typing import Optional

from .checker import full_safety_check
from .db import get_drug
from .exceptions import (
    ConcentrationError,
    DrugNotFoundError,
    InvalidRouteError,
    WeightError,
)
from .models.drug import RouteConfig
from .models.patient import Patient
from .models.result import DoseResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mcg_to_mg(value: float) -> float:
    return value / 1000.0


def _mg_to_mcg(value: float) -> float:
    return value * 1000.0


def _compute_dose_mg(
    rc: RouteConfig,
    weight_kg: float,
    dose_fraction: float = 1.0,
) -> tuple[float, float]:
    """
    Compute raw calculated dose in mg (and in display units).

    Parameters
    ----------
    rc:
        RouteConfig for the chosen route.
    weight_kg:
        Patient weight in kilograms.
    dose_fraction:
        0.0 → min dose, 1.0 → max dose, 0.5 → mid dose (default = max).

    Returns
    -------
    (dose_mg, dose_display)
        dose_mg in milligrams, dose_display in the route's native unit.
    """
    # Interpolate between min and max
    dose_value = rc.dose_min + (rc.dose_max - rc.dose_min) * dose_fraction

    # Apply weight if per-kg
    if rc.per_kg:
        dose_value *= weight_kg

    dose_display = dose_value  # display unit (may be mcg or mg)

    # Convert to mg for internal use
    if rc.is_mcg:
        dose_mg = _mcg_to_mg(dose_value)
    else:
        dose_mg = dose_value

    return dose_mg, dose_display


def _apply_caps(
    dose_mg: float,
    rc: RouteConfig,
    is_pediatric: bool,
) -> tuple[float, bool, bool]:
    """
    Apply max dose caps.

    Returns
    -------
    (capped_dose_mg, pediatric_cap_applied, max_dose_exceeded)
    """
    pediatric_cap_applied = False
    max_dose_exceeded = False

    cap = rc.max_single_dose_mg
    ped_cap = rc.pediatric_max_dose_mg

    # Pediatric cap takes priority for peds patients
    if is_pediatric and ped_cap is not None:
        if dose_mg > ped_cap:
            dose_mg = ped_cap
            pediatric_cap_applied = True
    elif cap is not None:
        if dose_mg > cap:
            max_dose_exceeded = True
            dose_mg = cap

    return dose_mg, pediatric_cap_applied, max_dose_exceeded


def _compute_volume(dose_mg: float, concentration_mg_ml: float) -> float:
    """Calculate volume in mL from dose (mg) and concentration (mg/mL)."""
    if concentration_mg_ml <= 0:
        raise ConcentrationError(
            f"Concentration must be > 0 mg/mL, got {concentration_mg_ml}."
        )
    return dose_mg / concentration_mg_ml


# ---------------------------------------------------------------------------
# Main public function
# ---------------------------------------------------------------------------


def calculate_dose(
    drug_name: str,
    patient: Patient,
    route: str = "IV",
    concentration_mg_ml: Optional[float] = None,
    dose_fraction: float = 1.0,
) -> DoseResult:
    """
    Calculate a weight-based drug dose for a patient.

    Parameters
    ----------
    drug_name:
        Generic name, brand name, or partial name of the drug.
    patient:
        A fully constructed Patient object.
    route:
        Administration route (e.g. 'IV', 'IM', 'IN', 'SQ', 'ETT', 'PR').
    concentration_mg_ml:
        Stock concentration in mg/mL. If None, the database default is used.
        Required when database has no default.
    dose_fraction:
        Float 0.0–1.0 selecting within the dose range.
        0.0 = minimum dose, 1.0 = maximum dose (default), 0.5 = mid-range.

    Returns
    -------
    DoseResult
        Full structured result including dose, volume, safety flags.

    Raises
    ------
    DrugNotFoundError
        Drug not in the database.
    InvalidRouteError
        Route not available for this drug.
    WeightError
        Patient weight is missing or invalid.
    ConcentrationError
        No concentration provided and none in the database.
    """
    if patient.weight_kg <= 0:
        raise WeightError("Patient weight must be > 0 kg.")

    # ------------------------------------------------------------------ #
    # 1. Resolve drug                                                       #
    # ------------------------------------------------------------------ #
    drug = get_drug(drug_name)
    if drug is None:
        raise DrugNotFoundError(drug_name)

    # ------------------------------------------------------------------ #
    # 2. Resolve route                                                     #
    # ------------------------------------------------------------------ #
    rc = drug.get_route(route)
    if rc is None:
        raise InvalidRouteError(drug.display_name, route, drug.available_routes)

    # ------------------------------------------------------------------ #
    # 3. Concentration                                                     #
    # ------------------------------------------------------------------ #
    conc = concentration_mg_ml if concentration_mg_ml is not None else rc.standard_concentration_mg_ml

    # ------------------------------------------------------------------ #
    # 4. Dose calculation — MAX dose                                       #
    # ------------------------------------------------------------------ #
    dose_mg, dose_display = _compute_dose_mg(rc, patient.weight_kg, dose_fraction)
    dose_mg, ped_cap, max_exceeded = _apply_caps(dose_mg, rc, patient.is_pediatric)

    # Recalculate display value after capping (convert back to native units)
    if rc.is_mcg:
        dose_display = _mg_to_mcg(dose_mg)
    else:
        dose_display = dose_mg

    # ------------------------------------------------------------------ #
    # 5. MIN/MAX range values (for reference)                             #
    # ------------------------------------------------------------------ #
    dose_min_mg, dose_min_display = _compute_dose_mg(rc, patient.weight_kg, 0.0)
    dose_max_mg, dose_max_display = _compute_dose_mg(rc, patient.weight_kg, 1.0)

    # Apply caps to range boundaries too
    dose_min_mg, _, _ = _apply_caps(dose_min_mg, rc, patient.is_pediatric)
    dose_max_mg, _, _ = _apply_caps(dose_max_mg, rc, patient.is_pediatric)

    if rc.is_mcg:
        dose_min_display = _mg_to_mcg(dose_min_mg)
        dose_max_display = _mg_to_mcg(dose_max_mg)
    else:
        dose_min_display = dose_min_mg
        dose_max_display = dose_max_mg

    # ------------------------------------------------------------------ #
    # 6. Volume calculation                                                 #
    # ------------------------------------------------------------------ #
    volume_ml: Optional[float] = None
    if conc is not None:
        volume_ml = _compute_volume(dose_mg, conc)

    # ------------------------------------------------------------------ #
    # 7. Safety checks                                                      #
    # ------------------------------------------------------------------ #
    ci_flags, ix_flags = full_safety_check(drug, patient, route)
    is_contraindicated = any(f.absolute for f in ci_flags)

    # ------------------------------------------------------------------ #
    # 8. Assemble warnings                                                  #
    # ------------------------------------------------------------------ #
    warnings: list[str] = []

    if max_exceeded:
        warnings.append(
            f"Calculated dose exceeded the maximum single dose ({rc.max_single_dose_mg} mg). "
            "Dose has been capped."
        )

    if ped_cap:
        warnings.append(
            f"Pediatric maximum dose applied ({rc.pediatric_max_dose_mg} mg). "
            "Dose capped for this patient."
        )

    if volume_ml is not None and volume_ml > 20:
        warnings.append(
            f"Large volume ({volume_ml:.1f} mL) for single dose. Consider higher concentration or dose division."
        )

    if patient.is_neonate:
        warnings.append(
            "Neonatal patient: exercise extreme caution. Verify all doses independently."
        )
    elif patient.is_infant:
        warnings.append(
            "Infant patient: double-check all doses with age-appropriate references."
        )

    if drug.controlled_substance:
        warnings.append(
            f"Controlled substance ({drug.controlled_substance}). Requires proper documentation."
        )

    if drug.reversal_agent:
        warnings.append(
            f"Reversal agent available: {drug.reversal_agent.title()}. Ensure it is accessible."
        )

    if rc.continuous_infusion:
        warnings.append(
            "Continuous infusion route selected. Use calculate_drip() for pump rate calculation."
        )

    if conc is None:
        warnings.append(
            "No concentration available in database or provided. Volume cannot be calculated."
        )

    # ------------------------------------------------------------------ #
    # 9. Build result                                                       #
    # ------------------------------------------------------------------ #
    return DoseResult(
        drug_name=drug.name,
        display_name=drug.display_name,
        route=route.upper(),
        dose_unit=rc.dose_unit,
        dose_mg=dose_mg,
        dose_display=dose_display,
        volume_ml=volume_ml,
        concentration_mg_ml=conc,
        max_single_dose_mg=rc.max_single_dose_mg,
        pediatric_max_dose_mg=rc.pediatric_max_dose_mg,
        pediatric_cap_applied=ped_cap,
        max_dose_exceeded=max_exceeded,
        dose_min_mg=dose_min_mg,
        dose_max_mg=dose_max_mg,
        dose_min_display=dose_min_display,
        dose_max_display=dose_max_display,
        warnings=warnings,
        contraindications=ci_flags,
        interactions=ix_flags,
        is_contraindicated=is_contraindicated,
        frequency=rc.frequency,
        onset_min=rc.onset_min,
        duration_min=rc.duration_min,
        notes=rc.notes,
        reversal_agent=drug.reversal_agent,
        controlled_substance=drug.controlled_substance,
    )


def calculate_range(
    drug_name: str,
    patient: Patient,
    route: str = "IV",
    concentration_mg_ml: Optional[float] = None,
) -> tuple[DoseResult, DoseResult]:
    """
    Calculate both the minimum and maximum dose for the given patient.

    Returns
    -------
    (min_result, max_result)
    """
    min_result = calculate_dose(
        drug_name, patient, route, concentration_mg_ml, dose_fraction=0.0
    )
    max_result = calculate_dose(
        drug_name, patient, route, concentration_mg_ml, dose_fraction=1.0
    )
    return min_result, max_result
