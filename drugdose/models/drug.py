"""Drug and RouteConfig data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RouteConfig:
    """
    Dosing configuration for a specific administration route.

    Attributes
    ----------
    route:
        Administration route identifier (e.g. 'IV', 'IM', 'PO', 'IN', 'SQ',
        'ETT', 'PR', 'SL', 'INH', 'TOP').
    dose_min:
        Minimum dose in *dose_unit* per kg body weight (or flat if per_kg=False).
    dose_max:
        Maximum dose in *dose_unit* per kg body weight (or flat if per_kg=False).
    dose_unit:
        Unit string, e.g. 'mg/kg', 'mcg/kg', 'mg/kg/min', 'mcg/kg/min',
        'mg', 'mcg', 'units/kg'.
    per_kg:
        True if the dose is weight-based (multiply by patient weight).
    standard_concentration_mg_ml:
        Default stock concentration used for volume calculations (mg/mL).
        None when the drug is not typically drawn from a vial (e.g. tablets).
    max_single_dose_mg:
        Absolute ceiling for a single dose in milligrams.
        None means no hard cap is defined.
    pediatric_max_dose_mg:
        Separate ceiling applied when the patient is a child (<18 y).
        Falls back to max_single_dose_mg when None.
    frequency:
        Plain-text dosing frequency (e.g. 'once', 'q5min PRN', 'continuous').
    onset_min:
        Approximate onset time in minutes (informational).
    duration_min:
        Approximate effect duration in minutes (informational).
    notes:
        Free-text clinical notes for this route.
    continuous_infusion:
        True when the dose_unit is a rate (per/min or per/hr) for drip calcs.
    """

    route: str
    dose_min: float
    dose_max: float
    dose_unit: str
    per_kg: bool = True
    standard_concentration_mg_ml: Optional[float] = None
    max_single_dose_mg: Optional[float] = None
    pediatric_max_dose_mg: Optional[float] = None
    frequency: str = "PRN"
    onset_min: Optional[float] = None
    duration_min: Optional[float] = None
    notes: str = ""
    continuous_infusion: bool = False

    # ------------------------------------------------------------------ #
    # helpers                                                              #
    # ------------------------------------------------------------------ #

    @property
    def is_mcg(self) -> bool:
        """True when the dose unit is in micrograms."""
        return "mcg" in self.dose_unit.lower()

    @property
    def is_per_min(self) -> bool:
        return "/min" in self.dose_unit.lower()

    @property
    def is_per_hr(self) -> bool:
        return "/hr" in self.dose_unit.lower()

    @classmethod
    def from_dict(cls, d: dict) -> "RouteConfig":
        return cls(
            route=d["route"],
            dose_min=d["dose_min"],
            dose_max=d["dose_max"],
            dose_unit=d["dose_unit"],
            per_kg=d.get("per_kg", True),
            standard_concentration_mg_ml=d.get("standard_concentration_mg_ml"),
            max_single_dose_mg=d.get("max_single_dose_mg"),
            pediatric_max_dose_mg=d.get("pediatric_max_dose_mg"),
            frequency=d.get("frequency", "PRN"),
            onset_min=d.get("onset_min"),
            duration_min=d.get("duration_min"),
            notes=d.get("notes", ""),
            continuous_infusion=d.get("continuous_infusion", False),
        )


@dataclass
class Drug:
    """
    A single drug entry in the database.

    Attributes
    ----------
    name:
        Primary generic name (lowercase).
    display_name:
        Capitalised display string.
    brand_names:
        List of common brand/trade names.
    drug_class:
        Pharmacological class (e.g. 'Opioid analgesic').
    indication:
        Primary clinical indication(s).
    mechanism:
        Brief mechanism of action.
    routes:
        All available administration routes with their dose configs.
    contraindications:
        List of condition/allergy strings that are absolute contraindications.
    allergy_cross_reactions:
        Other drugs/substances that share allergy cross-reactivity.
    pregnancy_category:
        FDA pregnancy category letter (A/B/C/D/X) or 'N/A'.
    controlled_substance:
        DEA schedule string (e.g. 'Schedule II') or None.
    min_age_years:
        Minimum patient age in years. None = no restriction.
    max_age_years:
        Maximum patient age in years. None = no restriction.
    min_weight_kg:
        Minimum patient weight in kg. None = no restriction.
    max_weight_kg:
        Maximum patient weight in kg. None = no restriction.
    renal_caution:
        True when dose adjustment is needed in renal impairment.
    hepatic_caution:
        True when dose adjustment is needed in hepatic impairment.
    reversal_agent:
        Name of reversal/antidote drug (e.g. 'naloxone' for opioids).
    tags:
        Free-form tags for search/filtering (e.g. ['emergency', 'cardiac']).
    """

    name: str
    display_name: str
    brand_names: list[str] = field(default_factory=list)
    drug_class: str = ""
    indication: str = ""
    mechanism: str = ""
    routes: list[RouteConfig] = field(default_factory=list)
    contraindications: list[str] = field(default_factory=list)
    allergy_cross_reactions: list[str] = field(default_factory=list)
    pregnancy_category: str = "C"
    controlled_substance: Optional[str] = None
    min_age_years: Optional[float] = None
    max_age_years: Optional[float] = None
    min_weight_kg: Optional[float] = None
    max_weight_kg: Optional[float] = None
    renal_caution: bool = False
    hepatic_caution: bool = False
    reversal_agent: Optional[str] = None
    tags: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------ #
    # helpers                                                              #
    # ------------------------------------------------------------------ #

    def get_route(self, route: str) -> Optional[RouteConfig]:
        """Return the RouteConfig for *route* (case-insensitive) or None."""
        route_upper = route.upper()
        for rc in self.routes:
            if rc.route.upper() == route_upper:
                return rc
        return None

    @property
    def available_routes(self) -> list[str]:
        return [rc.route for rc in self.routes]

    @classmethod
    def from_dict(cls, d: dict) -> "Drug":
        return cls(
            name=d["name"],
            display_name=d.get("display_name", d["name"].title()),
            brand_names=d.get("brand_names", []),
            drug_class=d.get("drug_class", ""),
            indication=d.get("indication", ""),
            mechanism=d.get("mechanism", ""),
            routes=[RouteConfig.from_dict(r) for r in d.get("routes", [])],
            contraindications=d.get("contraindications", []),
            allergy_cross_reactions=d.get("allergy_cross_reactions", []),
            pregnancy_category=d.get("pregnancy_category", "C"),
            controlled_substance=d.get("controlled_substance"),
            min_age_years=d.get("min_age_years"),
            max_age_years=d.get("max_age_years"),
            min_weight_kg=d.get("min_weight_kg"),
            max_weight_kg=d.get("max_weight_kg"),
            renal_caution=d.get("renal_caution", False),
            hepatic_caution=d.get("hepatic_caution", False),
            reversal_agent=d.get("reversal_agent"),
            tags=d.get("tags", []),
        )
