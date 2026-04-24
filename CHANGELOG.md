# Changelog

All notable changes to **drugdose** are documented in this file.

This project adheres to [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned
- ACLS/PALS protocol mode (automated sequence recommendations)
- Broselow tape weight-estimation integration
- Renal dose-adjustment engine (Cockcroft-Gault, CKD-EPI)
- Export results to PDF / JSON report
- REST API wrapper (`drugdose serve`)
- Extended drug database: oncology, psychiatry, pediatric-specific drugs
- Pharmacokinetic simulation (Cp vs. time curves)
- Plugin system for custom formularies

---

## [0.1.0] — 2026-04-23

### Added

#### Core Library
- `Patient` model with weight, age, sex, allergies, current medications,
  conditions, pregnancy, renal/hepatic impairment, and height fields
  — includes computed properties: `is_pediatric`, `is_neonate`, `is_infant`,
  `ibw_kg` (Devine formula), `bmi`, `age_months`
- `Drug` model with full clinical metadata per drug entry:
  drug class, indication, mechanism, pregnancy category, controlled-substance
  schedule, reversal agent, cross-reactivity list, age/weight restrictions,
  and per-route dosing configurations
- `RouteConfig` model per administration route:
  dose range (min/max), dose unit, weight-based flag, standard concentration,
  adult and pediatric maximum single doses, frequency, onset, duration, notes,
  continuous-infusion flag
- `DoseResult` structured output: calculated dose in mg and native units,
  volume in mL, dose range (min/max), cap flags, safety flags, interaction
  flags, clinical metadata
- `DripResult` structured output: rate in mL/hr and mL/min, bag duration,
  absolute mg/min delivered, cap flags

#### Calculator (`calculate_dose`)
- Weight-based dose calculation supporting `mg/kg`, `mcg/kg`,
  `mg`, `mcg`, `g/kg`, `units/kg`
- Dose fraction parameter: select anywhere within the dose range
  (0.0 = minimum, 1.0 = maximum, 0.5 = mid-range)
- Pediatric maximum dose cap (separate from adult cap)
- Adult maximum single-dose cap with warning
- Volume calculation from dose and stock concentration
- `calculate_range()` helper returning both min and max `DoseResult`

#### Drip Calculator (`calculate_drip`)
- Supports 10+ rate unit formats: `mcg/kg/min`, `mcg/kg/hr`, `mg/kg/min`,
  `mg/kg/hr`, `mcg/min`, `mcg/hr`, `mg/min`, `mg/hr`, `g/hr`,
  `units/min`, `units/hr`, `units/kg/hr`
- Outputs pump rate (mL/hr), rate (mL/min), absolute mg/min, bag duration
- Detects rate-exceeded-maximum and very-low/very-high rate conditions
- `standard_mixture()` helper for computing concentration from drug mass + volume

#### Safety Checker (`checker.py`)
- Allergy checker: direct drug-name match, brand-name match,
  cross-reactivity list, drug-class overlap
- Condition contraindication checker: matches patient condition strings
  against absolute and relative contraindications
- Pregnancy category flagging: Category D (relative warning) and
  Category X (absolute contraindication)
- Age restriction enforcement (min/max age per drug)
- Weight restriction enforcement (min/max weight per drug)
- Renal and hepatic impairment caution flags
- Controlled-substance documentation reminder
- Drug–drug interaction checker against bundled interaction rule set
- `full_safety_check()` returns both contraindications and interactions
  in one call
- `ContraindicationFlag` with `absolute` field for hard vs. soft blocks
- `InteractionFlag` with severity (`major`, `moderate`, `minor`),
  clinical description, and management guidance

#### Drug Database (`drugs.json`)
49 drugs across clinical categories:

- **Emergency/EMS:** Epinephrine, Adenosine, Atropine, Naloxone, Dextrose,
  Tranexamic Acid, Activated Charcoal, Glucagon, Sodium Bicarbonate,
  Calcium Gluconate, Diphenhydramine
- **Opioid Analgesics:** Morphine, Fentanyl, (Naloxone reversal)
- **Sedation/Anesthesia:** Midazolam, Lorazepam, Diazepam, Ketamine,
  Propofol, Etomidate
- **Neuromuscular Blockers:** Succinylcholine, Rocuronium
- **Cardiac/Antiarrhythmics:** Amiodarone, Lidocaine, Metoprolol, Diltiazem,
  Digoxin, Magnesium Sulfate, Nitroglycerin
- **Vasopressors/Inotropes:** Epinephrine (drip), Norepinephrine, Dopamine,
  Dobutamine, Vasopressin, Phenylephrine
- **Antihypertensives:** Labetalol
- **Respiratory:** Albuterol, Ipratropium, Methylprednisolone, Dexamethasone
- **Antibiotics:** Vancomycin, Ceftriaxone, Piperacillin-Tazobactam
- **Anticoagulants/Thrombolytics:** Heparin, Alteplase (tPA)
- **Diuretics:** Furosemide
- **Endocrine/Metabolic:** Insulin Regular, Acetaminophen, Ketorolac,
  Ondansetron
- **Psychiatric/Agitation:** Haloperidol

Each drug entry includes multiple routes with full per-route dose configs.

#### Interaction Database (`interactions.json`)
39 curated drug–drug interaction rules covering:
- Opioid + benzodiazepine combinations (FDA Black Box)
- Amiodarone combinations (digoxin, metoprolol, diltiazem, lidocaine)
- QTc-prolonging agent pairs (haloperidol, ondansetron, amiodarone)
- Vasopressor combinations
- Nitroglycerin + PDE-5 inhibitors (sildenafil, tadalafil)
- NSAID + anticoagulant bleeding risk
- Furosemide + vancomycin (ototoxicity)
- Furosemide + digoxin (hypokalemia toxicity)
- Neuromuscular blocker + magnesium interactions
- Ceftriaxone + calcium precipitation warning
- Naloxone reversal dynamics (re-narcotization risk)
- Propofol + CNS depressant combinations

#### CLI (`drugdose` command)
Built with [Rich](https://github.com/Textualize/rich) and [Click](https://click.palletsprojects.com):

| Command | Description |
|---|---|
| `drugdose calculate` | Interactive weight-based dose calculator |
| `drugdose drip` | IV drip rate and pump calculator |
| `drugdose info <drug>` | Full drug information panel |
| `drugdose search <query>` | Search drugs by name, indication, or class |
| `drugdose list [--tag]` | Browse all drugs with optional tag filter |
| `drugdose check <drug>` | Full safety check for a patient |
| `drugdose version` | Library version and database info |

All commands support `--help` / `-h` flags.

#### Test Suite
- 24 unit tests across `Patient`, `calculate_dose`, `calculate_range`,
  `calculate_drip`, and `standard_mixture`
- Covers: weight-based math, mcg/mg unit conversion, dose capping,
  pediatric caps, allergy detection, interaction detection, age restrictions,
  pregnancy flagging, renal caution, custom concentration, error raising

### Dependencies
- `rich >= 13.0` — terminal rendering
- `click >= 8.1` — CLI framework
- Python `>= 3.10`

---

[Unreleased]: https://github.com/londonchowdhury/drugdose/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/londonchowdhury/drugdose/releases/tag/v0.1.0
