"""Result data models returned by the calculator and checker."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class InteractionFlag:
    """Describes a drug–drug or drug–condition interaction."""

    drug_a: str
    drug_b: str
    severity: str          # 'major', 'moderate', 'minor'
    description: str
    management: str = ""


@dataclass
class ContraindicationFlag:
    """Describes a contraindication triggered for the patient."""

    category: str          # 'allergy', 'condition', 'age', 'weight', 'pregnancy'
    detail: str
    absolute: bool = True  # False = relative / caution


@dataclass
class DoseResult:
    """
    Full output of a single dose calculation.

    All *_mg fields are in milligrams; volume_ml is in millilitres.
    When the dose unit is mcg/kg, dose_mg still stores the converted mg value.
    """

    drug_name: str
    display_name: str
    route: str
    dose_unit: str

    # Core calculated values
    dose_mg: float                   # calculated dose in mg
    dose_display: float              # in original units (mg or mcg)
    volume_ml: Optional[float]       # None when no concentration available

    # Concentration used
    concentration_mg_ml: Optional[float] = None

    # Limits
    max_single_dose_mg: Optional[float] = None
    pediatric_max_dose_mg: Optional[float] = None
    pediatric_cap_applied: bool = False
    max_dose_exceeded: bool = False

    # Range
    dose_min_mg: Optional[float] = None
    dose_max_mg: Optional[float] = None
    dose_min_display: Optional[float] = None
    dose_max_display: Optional[float] = None

    # Safety
    warnings: list[str] = field(default_factory=list)
    contraindications: list[ContraindicationFlag] = field(default_factory=list)
    interactions: list[InteractionFlag] = field(default_factory=list)
    is_contraindicated: bool = False    # any absolute contraindication present

    # Drug metadata
    frequency: str = ""
    onset_min: Optional[float] = None
    duration_min: Optional[float] = None
    notes: str = ""
    reversal_agent: Optional[str] = None
    controlled_substance: Optional[str] = None

    # ------------------------------------------------------------------ #
    # helpers                                                              #
    # ------------------------------------------------------------------ #

    @property
    def safe_to_administer(self) -> bool:
        """False if any absolute contraindication is present."""
        return not self.is_contraindicated

    @property
    def has_warnings(self) -> bool:
        return bool(self.warnings or self.interactions)

    def summary(self) -> str:
        """One-line human-readable summary."""
        vol = f" → {self.volume_ml:.2f} mL" if self.volume_ml is not None else ""
        unit = "mcg" if "mcg" in self.dose_unit else "mg"
        return (
            f"{self.display_name} {self.route}: "
            f"{self.dose_display:.2f} {unit}{vol}"
            + (" [CAPPED]" if self.pediatric_cap_applied else "")
            + (" [CONTRAINDICATED]" if self.is_contraindicated else "")
        )


@dataclass
class DripResult:
    """
    Output of an IV drip-rate calculation.

    All time-based values use minutes as the base unit unless otherwise noted.
    """

    drug_name: str
    display_name: str
    route: str

    # Ordered dose (what the clinician wants)
    ordered_dose: float          # in dose_unit
    dose_unit: str               # e.g. 'mcg/kg/min'
    patient_weight_kg: float

    # Bag / concentration
    concentration_mg_ml: float   # mg/mL in the infusion bag
    bag_volume_ml: float         # total bag volume in mL

    # Calculated rates
    dose_mg_per_min: float       # absolute mg/min infused
    rate_ml_per_hr: float        # pump rate in mL/hr
    rate_ml_per_min: float       # pump rate in mL/min

    # Duration
    duration_hr: Optional[float] = None   # how long the bag will last at this rate

    # Safety
    warnings: list[str] = field(default_factory=list)
    max_rate_ml_per_hr: Optional[float] = None
    rate_exceeded: bool = False

    def summary(self) -> str:
        d = f"{self.duration_hr:.1f} hr" if self.duration_hr is not None else "∞"
        return (
            f"{self.display_name} drip @ {self.ordered_dose} {self.dose_unit}: "
            f"{self.rate_ml_per_hr:.2f} mL/hr  (bag lasts {d})"
        )
