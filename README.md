# 💊 drugdose

> **EMS & Clinical Drug Dosing Calculator** — weight-based doses, IV drip rates, contraindication checking, and drug interaction screening, all in one Python library.

[![PyPI version](https://img.shields.io/pypi/v/drugdose.svg)](https://pypi.org/project/drugdose/)
[![Python](https://img.shields.io/pypi/pyversions/drugdose.svg)](https://pypi.org/project/drugdose/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-24%20passing-brightgreen.svg)](#)

---

**⚠️ Medical Disclaimer**
> `drugdose` is a **clinical decision-support tool** intended for use by licensed healthcare professionals. It does not replace professional clinical judgment, institutional protocols, or current drug references (e.g. Lexicomp, Micromedex). Always verify doses independently before administration. The authors assume no liability for patient outcomes.
**[Read the full legal disclaimer →](DISCLAIMER.md)**
---

## Features

- **Weight-based dose calculation** — `mg/kg`, `mcg/kg`, flat doses, across all common administration routes
- **Pediatric dose caps** — separate adult and pediatric maximum single-dose limits
- **IV drip rate calculator** — any rate unit (`mcg/kg/min`, `mg/hr`, `g/hr`, etc.) → mL/hr pump rate and bag duration
- **Allergy checker** — direct, brand-name, cross-reactivity, and drug-class allergy matching
- **Contraindication flags** — conditions, age/weight restrictions, pregnancy categories D & X, renal/hepatic caution
- **Drug–drug interaction screener** — 39 curated rules with severity (major/moderate/minor), clinical description, and management guidance
- **49-drug bundled database** — EMS, cardiac, anesthesia, ICU, antibiotics, toxicology, obstetrics, and more
- **Rich CLI** — interactive terminal interface with colour-coded safety output
- **Pure Python, zero heavy dependencies** — only `rich` and `click`

---

## Installation

```bash
pip install drugdose
```

Requires Python 3.10+.

---

## Quick Start

### Python API

```python
from drugdose import Patient, calculate_dose, calculate_drip

# ── Build a patient ───────────────────────────────────────────────────────────
patient = Patient(
    weight_kg=70,
    age_years=35,
    allergies=["codeine"],
    current_medications=["midazolam"],
    conditions=["hypertension"],
    renal_impairment=False,
)

# ── Calculate a single dose ───────────────────────────────────────────────────
result = calculate_dose("fentanyl", patient, route="IV")

print(result.summary())
# → Fentanyl Citrate IV: 200.00 mcg → 4.00 mL

print(f"Dose:    {result.dose_display:.1f} mcg")
print(f"Volume:  {result.volume_ml:.2f} mL")
print(f"Freq:    {result.frequency}")

# Safety flags
if result.contraindications:
    for ci in result.contraindications:
        print(f"[{'ABSOLUTE' if ci.absolute else 'relative'}] {ci.detail}")

if result.interactions:
    for ix in result.interactions:
        print(f"[{ix.severity.upper()}] {ix.drug_a} ⟺ {ix.drug_b}: {ix.description}")
```

### IV Drip Rate

```python
from drugdose import Patient, calculate_drip, standard_mixture

patient = Patient(weight_kg=80)

# Calculate pump rate
drip = calculate_drip(
    "dopamine",
    patient,
    ordered_dose=5.0,
    dose_unit="mcg/kg/min",
    bag_volume_ml=250.0,
)

print(drip.summary())
# → Dopamine drip @ 5 mcg/kg/min: 15.00 mL/hr  (bag lasts 16.7 hr)

print(f"Rate:     {drip.rate_ml_per_hr:.2f} mL/hr")
print(f"Delivers: {drip.dose_mg_per_min * 60:.2f} mg/hr")
print(f"Duration: {drip.duration_hr:.1f} hr")

# Build a custom mixture concentration
conc = standard_mixture("norepinephrine", total_drug_mg=4.0, bag_volume_ml=250.0)
print(f"Bag conc: {conc:.4f} mg/mL")   # → 0.0160 mg/mL
```

### Dose Range (min → max)

```python
from drugdose import Patient, calculate_range

patient = Patient(weight_kg=25, age_years=7)
min_r, max_r = calculate_range("ketamine", patient, route="IV")

print(f"Min dose: {min_r.dose_display:.1f} mg  ({min_r.volume_ml:.2f} mL)")
print(f"Max dose: {max_r.dose_display:.1f} mg  ({max_r.volume_ml:.2f} mL)")
```

### Safety Check Only

```python
from drugdose import get_drug, Patient, full_safety_check

drug = get_drug("amiodarone")
patient = Patient(
    weight_kg=70,
    age_years=68,
    allergies=["iodine"],
    current_medications=["digoxin", "metoprolol"],
)

ci_flags, ix_flags = full_safety_check(drug, patient)

for ci in ci_flags:
    severity = "ABSOLUTE" if ci.absolute else "relative"
    print(f"[{severity}] [{ci.category}] {ci.detail}")

for ix in ix_flags:
    print(f"[{ix.severity.upper()}] {ix.drug_a} + {ix.drug_b}")
    print(f"  {ix.description}")
    print(f"  Management: {ix.management}")
```

### Drug Search & Lookup

```python
from drugdose import get_drug, search_drugs, get_all_drugs

# Lookup by name or brand name
drug = get_drug("Narcan")     # returns naloxone Drug object
drug = get_drug("epi")        # partial match → epinephrine

# Search with query and/or tag
cardiac_drugs = search_drugs("", tag="cardiac")
opioid_results = search_drugs("opioid")

# Full database
all_drugs = get_all_drugs()   # dict[str, Drug]
print(f"{len(all_drugs)} drugs in database")
```

---

## CLI Reference

Install via pip then run `drugdose`:

```
Usage: drugdose [OPTIONS] COMMAND [ARGS]...

  💊 drugdose — Clinical Dosing

Commands:
  calculate   Calculate a weight-based drug dose
  check       Run a full safety check for a drug and patient
  drip        Calculate IV drip / infusion pump rate
  info        Show detailed information about a drug
  list        List all drugs in the database
  search      Search the drug database by name, indication, or tag
  version     Show version and library info
```

Every command accepts `--help` / `-h` for full option details.

### Examples

```bash
# Interactive dose calculator (prompts for patient info)
drugdose calculate epinephrine --route IV --weight 70

# Specify everything inline
drugdose calculate fentanyl -r IM -w 25 --age 8 --allergies penicillin

# Show the full min-to-max dose range
drugdose calculate ketamine --range -w 70 --age 30

# IV drip rate
drugdose drip dopamine -w 70 -d 5 -u mcg/kg/min

# Calculate a custom mixture concentration
drugdose drip epinephrine --mix --total-mg 4 -b 250

# Full drug info panel
drugdose info ketamine
drugdose info "Narcan"

# Safety check with patient context
drugdose check amiodarone --meds "digoxin,metoprolol" --age 72 -w 80
drugdose check morphine --allergies codeine --conditions "respiratory depression"

# Search and list
drugdose search opioid
drugdose search --tag cardiac
drugdose list --tag emergency
drugdose list --class benzodiazepine
```

---

## Drug Database

49 drugs bundled across clinical categories:

| Category | Drugs |
|---|---|
| **Emergency / EMS** | Epinephrine, Adenosine, Atropine, Naloxone, Dextrose, Tranexamic Acid, Glucagon, Activated Charcoal |
| **Cardiac** | Amiodarone, Lidocaine, Adenosine, Metoprolol, Diltiazem, Digoxin, Nitroglycerin, Magnesium Sulfate |
| **Vasopressors / Inotropes** | Norepinephrine, Dopamine, Dobutamine, Vasopressin, Phenylephrine, Epinephrine (drip) |
| **Anesthesia / Sedation** | Ketamine, Propofol, Etomidate, Midazolam, Lorazepam, Diazepam |
| **Neuromuscular Blockers** | Succinylcholine, Rocuronium |
| **Opioid Analgesics** | Morphine, Fentanyl |
| **Non-Opioid Analgesics** | Ketorolac, Acetaminophen |
| **Respiratory** | Albuterol, Ipratropium, Methylprednisolone, Dexamethasone |
| **Antibiotics** | Vancomycin, Ceftriaxone, Piperacillin-Tazobactam |
| **Anticoagulants / Thrombolytics** | Heparin, Alteplase (tPA) |
| **Metabolic / Electrolytes** | Insulin Regular, Sodium Bicarbonate, Calcium Gluconate, Furosemide |
| **Other** | Ondansetron, Diphenhydramine, Haloperidol, Labetalol |

All drugs include: multiple routes, dose ranges (mg/kg or mcg/kg), standard concentrations, adult and pediatric dose caps, frequency, onset/duration, contraindications, cross-reactivity lists, and clinical notes.

---

## Adding Custom Drugs

Extend the bundled database by editing `src/drugdose/data/drugs.json`, or load your own at runtime:

```python
import json
from drugdose.models.drug import Drug
from drugdose import calculate_dose, Patient

# Load a custom drug dict
with open("my_formulary.json") as f:
    entries = json.load(f)

custom_drug = Drug.from_dict(entries[0])

# Pass it directly to the checker or calculator internals
from drugdose.calculator import calculate_dose as _calc
from drugdose.db import get_all_drugs

# Or monkey-patch the cache for the session:
db = get_all_drugs()
db["my_drug"] = custom_drug
```

> A plugin/formulary override system is planned for v0.2.0.

---

## API Reference

### `Patient(weight_kg, age_years, sex, allergies, current_medications, conditions, is_pregnant, renal_impairment, hepatic_impairment, height_cm)`

| Property | Type | Description |
|---|---|---|
| `is_pediatric` | `bool` | Age < 18 years |
| `is_neonate` | `bool` | Age < 28 days |
| `is_infant` | `bool` | Age 28 days – 1 year |
| `ibw_kg` | `float \| None` | Ideal body weight (Devine formula) |
| `bmi` | `float \| None` | Body mass index |
| `age_months` | `float \| None` | Age expressed in months |

### `calculate_dose(drug_name, patient, route, concentration_mg_ml, dose_fraction) → DoseResult`

| Parameter | Default | Description |
|---|---|---|
| `drug_name` | required | Generic name, brand name, or partial name |
| `patient` | required | `Patient` object |
| `route` | `"IV"` | Route string: `IV`, `IM`, `IN`, `SQ`, `ETT`, `PR`, `SL`, `INH`, `IV_DRIP` |
| `concentration_mg_ml` | `None` | Override stock concentration. Uses database default when `None`. |
| `dose_fraction` | `1.0` | `0.0` = minimum dose, `1.0` = maximum dose |

### `calculate_range(drug_name, patient, route, concentration_mg_ml) → (DoseResult, DoseResult)`

Returns `(min_result, max_result)`.

### `calculate_drip(drug_name, patient, ordered_dose, dose_unit, concentration_mg_ml, bag_volume_ml) → DripResult`

Supported `dose_unit` values: `mcg/kg/min`, `mcg/kg/hr`, `mg/kg/min`, `mg/kg/hr`, `mcg/min`, `mcg/hr`, `mg/min`, `mg/hr`, `g/hr`, `units/min`, `units/hr`.

### `standard_mixture(drug_name, total_drug_mg, bag_volume_ml) → float`

Returns concentration in mg/mL.

### `full_safety_check(drug, patient, route) → (list[ContraindicationFlag], list[InteractionFlag])`

### `search_drugs(query, tag) → list[Drug]`

### `get_drug(name) → Drug | None`

Matches by generic name, display name, brand names, and partial substring.

---

## Exceptions

| Exception | Raised when |
|---|---|
| `DrugNotFoundError` | Drug name not in database |
| `InvalidRouteError` | Route not available for the drug |
| `InvalidPatientError` | Weight/age outside physiologic range |
| `ContraindicatedError` | Absolute contraindication triggered (if you raise it yourself) |
| `WeightError` | Weight is zero or negative |
| `ConcentrationError` | No concentration provided and none in database |

All inherit from `DrugDoseError`.

---

## Development

```bash
# Clone and install in editable mode
git clone https://github.com/londonchowdhury/drugdose.git
cd drugdose
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run tests with coverage
pytest tests/ --cov=drugdose --cov-report=term-missing
```

### Project Structure

```
drugdose/
├── pyproject.toml              # Package config & dependencies
├── README.md
├── CHANGELOG.md
├── .gitignore
├── src/
│   └── drugdose/
│       ├── __init__.py         # Public API re-exports
│       ├── calculator.py       # calculate_dose(), calculate_range()
│       ├── drip.py             # calculate_drip(), standard_mixture()
│       ├── checker.py          # Contraindication & interaction engine
│       ├── db.py               # Drug database loader & search
│       ├── exceptions.py       # Custom exception hierarchy
│       ├── cli.py              # Rich + Click CLI
│       ├── models/
│       │   ├── drug.py         # Drug, RouteConfig dataclasses
│       │   ├── patient.py      # Patient dataclass
│       │   └── result.py       # DoseResult, DripResult, flags
│       └── data/
│           ├── drugs.json      # 49-drug database
│           └── interactions.json  # 39 interaction rules
└── tests/
    └── test_calculator.py      # 24 unit tests
```

### Publishing to PyPI

```bash
pip install build twine
python -m build
twine check dist/*
twine upload dist/*
```

---

## Roadmap

- [ ] Renal dose-adjustment engine (Cockcroft-Gault, CKD-EPI)
- [ ] ACLS/PALS automated protocol sequences
- [ ] Broselow tape weight-estimation by age/length
- [ ] Pharmacokinetic simulation (Cp vs. time)
- [ ] PDF/JSON export for dose calculations
- [ ] REST API via `drugdose serve`
- [ ] Plugin / custom formulary system
- [ ] Expanded database: oncology, psychiatry, neonatal specific
- [ ] Web UI

---

## Contributing

Contributions are welcome — especially:

- **New drugs or routes** — open a PR editing `drugs.json`
- **Interaction rules** — open a PR editing `interactions.json`
- **Bug reports** — open an issue with patient parameters and expected vs. actual output
- **Protocol corrections** — cite your source (AHA guidelines, package insert, etc.)

Please include a citation for any dose ranges added or modified.

---

## License

MIT © 2026. See [LICENSE](LICENSE) for full text.

---

## Acknowledgements

Dose ranges sourced from and cross-referenced against:
- American Heart Association (AHA) ACLS/PALS Guidelines 2020
- Pediatric Advanced Life Support (PALS) Provider Manual
- Micromedex / Lexicomp drug references
- Surviving Sepsis Campaign Guidelines 2021
- Individual FDA-approved package inserts