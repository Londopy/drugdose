"""
Contraindication and drug-interaction checker.

Raises ContraindicatedError for absolute contraindications,
returns structured flags for relative/conditional contraindications
and drug interactions.
"""

from __future__ import annotations

from typing import Optional

from .db import get_interactions_for
from .models.drug import Drug
from .models.patient import Patient
from .models.result import ContraindicationFlag, InteractionFlag


# ---------------------------------------------------------------------------
# Contraindication checker
# ---------------------------------------------------------------------------


def check_contraindications(
    drug: Drug,
    patient: Patient,
    route: Optional[str] = None,
) -> list[ContraindicationFlag]:
    """
    Evaluate *drug* against *patient* and return all triggered contraindication flags.

    The caller should inspect the returned list and decide whether to raise or warn.
    Absolute contraindications have flag.absolute = True.
    """
    flags: list[ContraindicationFlag] = []

    # ------------------------------------------------------------------ #
    # 1. Allergy check                                                     #
    # ------------------------------------------------------------------ #
    patient_allergies = set(patient.allergies)

    # Direct drug-name allergy
    if drug.name in patient_allergies or drug.display_name.lower() in patient_allergies:
        flags.append(ContraindicationFlag(
            category="allergy",
            detail=f"Patient has documented allergy to {drug.display_name}.",
            absolute=True,
        ))

    # Brand-name allergy
    for bn in drug.brand_names:
        if bn.lower() in patient_allergies:
            flags.append(ContraindicationFlag(
                category="allergy",
                detail=f"Patient has documented allergy to {bn} (brand name of {drug.display_name}).",
                absolute=True,
            ))

    # Cross-reactivity allergy
    for xr in drug.allergy_cross_reactions:
        if xr.lower() in patient_allergies:
            flags.append(ContraindicationFlag(
                category="allergy",
                detail=(
                    f"Patient allergic to '{xr}'. Cross-reactivity risk with {drug.display_name}. "
                    "Proceed only if benefit outweighs risk."
                ),
                absolute=False,
            ))

    # Drug-class allergy (e.g. 'penicillin' allergy triggers ampicillin flag)
    drug_class_lower = drug.drug_class.lower()
    for allergy in patient_allergies:
        if allergy in drug_class_lower and allergy not in ("analgesic", "emergency", "cardiac"):
            flags.append(ContraindicationFlag(
                category="allergy",
                detail=(
                    f"Patient has allergy to '{allergy}' which overlaps with {drug.drug_class}. "
                    f"Verify cross-reactivity before administering {drug.display_name}."
                ),
                absolute=False,
            ))

    # ------------------------------------------------------------------ #
    # 2. Condition contraindications                                        #
    # ------------------------------------------------------------------ #
    patient_conditions = set(patient.conditions)

    for ci in drug.contraindications:
        ci_lower = ci.lower()
        # Strip the "(relative)" suffix for matching
        ci_core = ci_lower.replace("(relative)", "").strip()
        is_relative = "(relative)" in ci_lower

        for cond in patient_conditions:
            # Check if patient condition matches (substring match both ways)
            if ci_core in cond or cond in ci_core:
                flags.append(ContraindicationFlag(
                    category="condition",
                    detail=f"Drug contraindication '{ci}' may apply to patient condition '{cond}'.",
                    absolute=not is_relative,
                ))
                break

    # ------------------------------------------------------------------ #
    # 3. Pregnancy                                                         #
    # ------------------------------------------------------------------ #
    if patient.is_pregnant:
        cat = drug.pregnancy_category.upper()
        if cat == "D":
            flags.append(ContraindicationFlag(
                category="pregnancy",
                detail=(
                    f"{drug.display_name} is FDA Pregnancy Category D. "
                    "Evidence of human fetal risk — use only if benefit outweighs risk."
                ),
                absolute=False,
            ))
        elif cat == "X":
            flags.append(ContraindicationFlag(
                category="pregnancy",
                detail=(
                    f"{drug.display_name} is FDA Pregnancy Category X — ABSOLUTELY CONTRAINDICATED in pregnancy."
                ),
                absolute=True,
            ))

    # ------------------------------------------------------------------ #
    # 4. Age restrictions                                                  #
    # ------------------------------------------------------------------ #
    if patient.age_years is not None:
        if drug.min_age_years is not None and patient.age_years < drug.min_age_years:
            flags.append(ContraindicationFlag(
                category="age",
                detail=(
                    f"{drug.display_name} is not recommended for patients under "
                    f"{drug.min_age_years} years. Patient is {patient.age_years:.1f} years old."
                ),
                absolute=True,
            ))
        if drug.max_age_years is not None and patient.age_years > drug.max_age_years:
            flags.append(ContraindicationFlag(
                category="age",
                detail=(
                    f"{drug.display_name} is not recommended for patients over "
                    f"{drug.max_age_years} years. Patient is {patient.age_years:.1f} years old."
                ),
                absolute=False,
            ))

    # ------------------------------------------------------------------ #
    # 5. Weight restrictions                                               #
    # ------------------------------------------------------------------ #
    if drug.min_weight_kg is not None and patient.weight_kg < drug.min_weight_kg:
        flags.append(ContraindicationFlag(
            category="weight",
            detail=(
                f"{drug.display_name} not recommended under {drug.min_weight_kg} kg. "
                f"Patient weighs {patient.weight_kg} kg."
            ),
            absolute=True,
        ))
    if drug.max_weight_kg is not None and patient.weight_kg > drug.max_weight_kg:
        flags.append(ContraindicationFlag(
            category="weight",
            detail=(
                f"{drug.display_name} not recommended over {drug.max_weight_kg} kg. "
                f"Patient weighs {patient.weight_kg} kg."
            ),
            absolute=False,
        ))

    # ------------------------------------------------------------------ #
    # 6. Renal / hepatic impairment                                        #
    # ------------------------------------------------------------------ #
    if patient.renal_impairment and drug.renal_caution:
        flags.append(ContraindicationFlag(
            category="condition",
            detail=(
                f"Renal impairment: {drug.display_name} requires dose adjustment or careful monitoring "
                "in patients with significant renal dysfunction."
            ),
            absolute=False,
        ))

    if patient.hepatic_impairment and drug.hepatic_caution:
        flags.append(ContraindicationFlag(
            category="condition",
            detail=(
                f"Hepatic impairment: {drug.display_name} is primarily hepatically metabolised. "
                "Dose reduction and careful monitoring required."
            ),
            absolute=False,
        ))

    # ------------------------------------------------------------------ #
    # 7. Controlled substance note                                         #
    # ------------------------------------------------------------------ #
    if drug.controlled_substance:
        flags.append(ContraindicationFlag(
            category="controlled",
            detail=(
                f"{drug.display_name} is a {drug.controlled_substance} controlled substance. "
                "Requires appropriate documentation and dispensing protocols."
            ),
            absolute=False,
        ))

    return flags


# ---------------------------------------------------------------------------
# Drug–drug interaction checker
# ---------------------------------------------------------------------------


def check_interactions(
    drug: Drug,
    patient: Patient,
) -> list[InteractionFlag]:
    """
    Check *drug* against *patient.current_medications* for known interactions.

    Returns a list of InteractionFlag objects sorted by severity (major first).
    """
    severity_order = {"major": 0, "moderate": 1, "minor": 2}
    flags: list[InteractionFlag] = []

    if not patient.current_medications:
        return flags

    drug_name = drug.name
    raw_interactions = get_interactions_for(drug_name)

    patient_meds = set(patient.current_medications)

    for rule in raw_interactions:
        a = rule["drug_a"]
        b = rule["drug_b"]

        # The other drug in the interaction
        other = b if a == drug_name else a

        # Check if patient takes the other drug
        if other in patient_meds or any(other in med for med in patient_meds):
            flags.append(InteractionFlag(
                drug_a=drug_name,
                drug_b=other,
                severity=rule.get("severity", "moderate"),
                description=rule.get("description", ""),
                management=rule.get("management", ""),
            ))

    # Sort by severity
    return sorted(flags, key=lambda f: severity_order.get(f.severity, 99))


# ---------------------------------------------------------------------------
# Convenience wrapper
# ---------------------------------------------------------------------------


def full_safety_check(
    drug: Drug,
    patient: Patient,
    route: Optional[str] = None,
) -> tuple[list[ContraindicationFlag], list[InteractionFlag]]:
    """Run both contraindication and interaction checks in one call."""
    ci_flags = check_contraindications(drug, patient, route)
    ix_flags = check_interactions(drug, patient)
    return ci_flags, ix_flags
