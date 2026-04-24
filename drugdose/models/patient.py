"""Patient data model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..exceptions import InvalidPatientError


@dataclass
class Patient:
    """
    Represents a patient for dose calculation.

    Parameters
    ----------
    weight_kg:
        Body weight in kilograms (required for weight-based dosing).
    age_years:
        Age in years. Use fractional values for infants (e.g. 0.5 = 6 months).
    sex:
        'M', 'F', or 'unknown'. Used for certain sex-specific contraindications.
    allergies:
        List of allergy strings (drug names, drug classes, or substances).
        Matched case-insensitively against drug contraindications and
        cross-reactivity lists.
    current_medications:
        List of drug names currently being taken. Used for interaction checks.
    conditions:
        List of medical condition strings (e.g. ['hypertension', 'asthma']).
        Matched against drug contraindications.
    is_pregnant:
        True if the patient is pregnant.
    renal_impairment:
        True if the patient has clinically significant renal impairment
        (eGFR < 30 mL/min or dialysis-dependent).
    hepatic_impairment:
        True if the patient has clinically significant hepatic impairment
        (Child-Pugh B or C).
    height_cm:
        Height in centimetres (used for IBW/BSA-based dosing when applicable).
    """

    weight_kg: float
    age_years: Optional[float] = None
    sex: str = "unknown"
    allergies: list[str] = field(default_factory=list)
    current_medications: list[str] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)
    is_pregnant: bool = False
    renal_impairment: bool = False
    hepatic_impairment: bool = False
    height_cm: Optional[float] = None

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        if self.weight_kg <= 0 or self.weight_kg > 500:
            raise InvalidPatientError(
                f"Weight {self.weight_kg} kg is outside the physiological range (0–500 kg)."
            )
        if self.age_years is not None and (self.age_years < 0 or self.age_years > 130):
            raise InvalidPatientError(
                f"Age {self.age_years} years is outside the expected range (0–130)."
            )
        self.sex = self.sex.upper()
        if self.sex not in ("M", "F", "UNKNOWN"):
            raise InvalidPatientError(f"Sex must be 'M', 'F', or 'unknown'; got '{self.sex}'.")
        # Normalise lists to lowercase for easier matching
        self.allergies = [a.lower().strip() for a in self.allergies]
        self.current_medications = [m.lower().strip() for m in self.current_medications]
        self.conditions = [c.lower().strip() for c in self.conditions]

    # ------------------------------------------------------------------ #
    # properties                                                           #
    # ------------------------------------------------------------------ #

    @property
    def is_pediatric(self) -> bool:
        """True if patient is under 18 years of age."""
        if self.age_years is None:
            return False
        return self.age_years < 18

    @property
    def is_neonate(self) -> bool:
        """True if patient is a neonate (< 28 days = ~0.077 years)."""
        if self.age_years is None:
            return False
        return self.age_years < 0.077

    @property
    def is_infant(self) -> bool:
        """True if patient is an infant (28 days – 1 year)."""
        if self.age_years is None:
            return False
        return 0.077 <= self.age_years < 1

    @property
    def age_months(self) -> Optional[float]:
        if self.age_years is None:
            return None
        return self.age_years * 12

    @property
    def ibw_kg(self) -> Optional[float]:
        """
        Ideal body weight (Devine formula).
        Returns None when height is unknown or patient is a child.
        """
        if self.height_cm is None or (self.age_years is not None and self.age_years < 18):
            return None
        height_in = self.height_cm / 2.54
        if self.sex == "M":
            return max(0.0, 50.0 + 2.3 * (height_in - 60))
        elif self.sex == "F":
            return max(0.0, 45.5 + 2.3 * (height_in - 60))
        return None

    @property
    def bmi(self) -> Optional[float]:
        if self.height_cm is None or self.height_cm <= 0:
            return None
        return self.weight_kg / ((self.height_cm / 100) ** 2)

    def __repr__(self) -> str:
        age_str = f"{self.age_years:.1f} yr" if self.age_years is not None else "age unknown"
        return f"Patient(weight={self.weight_kg} kg, age={age_str}, sex={self.sex})"
