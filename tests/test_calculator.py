"""Tests for the dose calculator."""

import pytest
from drugdose import (
    Patient,
    calculate_dose,
    calculate_range,
    DrugNotFoundError,
    InvalidRouteError,
)


class TestPatient:
    def test_basic_patient(self):
        p = Patient(weight_kg=70, age_years=35)
        assert p.weight_kg == 70
        assert p.age_years == 35
        assert not p.is_pediatric

    def test_pediatric_flag(self):
        child = Patient(weight_kg=25, age_years=8)
        assert child.is_pediatric

    def test_neonate_flag(self):
        neonate = Patient(weight_kg=3.2, age_years=0.02)
        assert neonate.is_neonate

    def test_invalid_weight(self):
        from drugdose import InvalidPatientError
        with pytest.raises(InvalidPatientError):
            Patient(weight_kg=0)

    def test_allergies_normalised(self):
        p = Patient(weight_kg=70, allergies=["Codeine", "IBUPROFEN"])
        assert "codeine" in p.allergies
        assert "ibuprofen" in p.allergies

    def test_ibw(self):
        p = Patient(weight_kg=80, age_years=30, sex="M", height_cm=180)
        ibw = p.ibw_kg
        assert ibw is not None
        assert 70 < ibw < 80

    def test_bmi(self):
        p = Patient(weight_kg=80, height_cm=180)
        bmi = p.bmi
        assert bmi is not None
        assert abs(bmi - 24.7) < 1.0


class TestCalculateDose:

    def test_epinephrine_iv_adult(self):
        patient = Patient(weight_kg=70, age_years=35)
        result = calculate_dose("epinephrine", patient, route="IV")
        # 0.01 mg/kg × 70 kg = 0.7 mg (capped at 1 mg)
        assert abs(result.dose_mg - 0.7) < 0.01
        assert result.volume_ml is not None
        # 0.7 mg / 0.1 mg/mL = 7 mL
        assert abs(result.volume_ml - 7.0) < 0.1

    def test_epinephrine_pediatric_cap(self):
        # 5 kg child: 0.01 × 5 = 0.05 mg — well under cap
        patient = Patient(weight_kg=5, age_years=0.5)
        result = calculate_dose("epinephrine", patient, route="IV")
        assert result.dose_mg < 1.0
        assert not result.pediatric_cap_applied

    def test_fentanyl_mcg_units(self):
        patient = Patient(weight_kg=70, age_years=30)
        result = calculate_dose("fentanyl", patient, route="IV")
        # Max dose: 3 mcg/kg × 70 = 210 mcg = 0.21 mg; capped at 0.2 mg (200 mcg)
        assert result.dose_mg <= 0.2 + 0.001
        assert "mcg" in result.dose_unit

    def test_dose_fraction_minimum(self):
        patient = Patient(weight_kg=70, age_years=40)
        min_r = calculate_dose("morphine", patient, route="IV", dose_fraction=0.0)
        max_r = calculate_dose("morphine", patient, route="IV", dose_fraction=1.0)
        assert min_r.dose_mg < max_r.dose_mg

    def test_drug_not_found(self):
        patient = Patient(weight_kg=70)
        with pytest.raises(DrugNotFoundError):
            calculate_dose("fakepharinex9000", patient, route="IV")

    def test_invalid_route(self):
        patient = Patient(weight_kg=70, age_years=35)
        with pytest.raises(InvalidRouteError):
            calculate_dose("adenosine", patient, route="PR")

    def test_custom_concentration(self):
        patient = Patient(weight_kg=70, age_years=35)
        result = calculate_dose("epinephrine", patient, route="IV", concentration_mg_ml=1.0)
        # 0.7 mg / 1.0 mg/mL = 0.7 mL
        assert abs(result.volume_ml - 0.7) < 0.01

    def test_calculate_range(self):
        patient = Patient(weight_kg=80, age_years=40)
        min_r, max_r = calculate_range("ketamine", patient, route="IV")
        assert min_r.dose_mg < max_r.dose_mg

    def test_allergy_contraindication(self):
        patient = Patient(
            weight_kg=70, age_years=30,
            allergies=["iodine"],
        )
        result = calculate_dose("amiodarone", patient, route="IV")
        ci_cats = [f.category for f in result.contraindications]
        assert "allergy" in ci_cats

    def test_interaction_detected(self):
        patient = Patient(
            weight_kg=70, age_years=35,
            current_medications=["midazolam"],
        )
        result = calculate_dose("fentanyl", patient, route="IV")
        ix_drugs = [(f.drug_a, f.drug_b) for f in result.interactions]
        assert any("midazolam" in pair for pair in ix_drugs)

    def test_pediatric_age_restriction(self):
        # morphine min_age_years=0.5; test with 2-month infant
        patient = Patient(weight_kg=5, age_years=0.15)
        result = calculate_dose("morphine", patient, route="IV")
        ci_cats = [f.category for f in result.contraindications]
        assert "age" in ci_cats

    def test_pregnancy_category_d_flagged(self):
        patient = Patient(weight_kg=60, age_years=28, is_pregnant=True)
        result = calculate_dose("lorazepam", patient, route="IV")
        ci_cats = [f.category for f in result.contraindications]
        assert "pregnancy" in ci_cats

    def test_renal_caution_flagged(self):
        patient = Patient(weight_kg=75, age_years=65, renal_impairment=True)
        result = calculate_dose("vancomycin", patient, route="IV")
        assert any("renal" in f.detail.lower() for f in result.contraindications)

    def test_result_summary_string(self):
        patient = Patient(weight_kg=70, age_years=35)
        result = calculate_dose("epinephrine", patient, route="IV")
        summary = result.summary()
        assert "Epinephrine" in summary
        assert "IV" in summary


class TestDripCalculator:
    def test_dopamine_drip(self):
        from drugdose import calculate_drip
        patient = Patient(weight_kg=70)
        result = calculate_drip(
            "dopamine", patient,
            ordered_dose=5.0,
            dose_unit="mcg/kg/min",
        )
        # 5 mcg/kg/min × 70 kg = 350 mcg/min = 0.35 mg/min
        assert abs(result.dose_mg_per_min - 0.35) < 0.01
        # 0.35 mg/min / 1.6 mg/mL × 60 = ~13.13 mL/hr
        assert abs(result.rate_ml_per_hr - 13.125) < 0.1

    def test_duration_calculated(self):
        from drugdose import calculate_drip
        patient = Patient(weight_kg=70)
        result = calculate_drip(
            "dopamine", patient,
            ordered_dose=5.0,
            dose_unit="mcg/kg/min",
            bag_volume_ml=250.0,
        )
        assert result.duration_hr is not None
        assert result.duration_hr > 0

    def test_standard_mixture(self):
        from drugdose import standard_mixture
        conc = standard_mixture("epinephrine", total_drug_mg=4.0, bag_volume_ml=250.0)
        assert abs(conc - 0.016) < 0.0001
