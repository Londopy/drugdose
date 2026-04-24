"""
drugdose CLI — powered by Rich + Click.

Commands
--------
drugdose calculate   Interactive dose calculator
drugdose drip        IV drip rate calculator
drugdose info        Detailed drug information panel
drugdose search      Search the drug database
drugdose list        List all drugs (optionally filtered by tag)
drugdose check       Check interactions for a patient's medication list
drugdose version     Show version information
"""

from __future__ import annotations

import sys
from typing import Optional

import click
from rich import box
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from . import __version__
from .calculator import calculate_dose, calculate_range
from .checker import full_safety_check
from .db import get_drug, get_all_drugs, search_drugs
from .drip import calculate_drip, standard_mixture
from .exceptions import (
    ConcentrationError,
    DrugDoseError,
    DrugNotFoundError,
    InvalidPatientError,
    InvalidRouteError,
)
from .models.patient import Patient
from .models.result import ContraindicationFlag, DoseResult, DripResult, InteractionFlag

console = Console()

# ---------------------------------------------------------------------------
# Severity colour mapping
# ---------------------------------------------------------------------------
SEVERITY_COLOR = {
    "major": "bold red",
    "moderate": "yellow",
    "minor": "dim green",
}

CONTRA_CATEGORY_COLOR = {
    "allergy": "bold red",
    "condition": "orange3",
    "age": "magenta",
    "weight": "magenta",
    "pregnancy": "hot_pink",
    "controlled": "dim cyan",
}


# ---------------------------------------------------------------------------
# Rich render helpers
# ---------------------------------------------------------------------------

def _render_dose_result(result: DoseResult) -> None:
    """Render a DoseResult to the terminal."""
    # Header
    safe_str = "[green]✓ SAFE TO ADMINISTER[/green]" if result.safe_to_administer else "[bold red]✗ CONTRAINDICATED[/bold red]"
    console.print()
    console.print(Panel(
        f"[bold white]{result.display_name}[/bold white]  [dim]{result.route}[/dim]\n{safe_str}",
        style="bright_blue",
        expand=False,
    ))

    # Main dose table
    unit = "mcg" if "mcg" in result.dose_unit else "mg"
    table = Table(box=box.ROUNDED, show_header=False, pad_edge=True)
    table.add_column("Field", style="dim cyan", width=26)
    table.add_column("Value", style="bold white")

    table.add_row("Dose (calculated)", f"[bold green]{result.dose_display:.3f} {unit}[/bold green]")

    if result.dose_min_display is not None and result.dose_max_display is not None and \
       result.dose_min_display != result.dose_max_display:
        table.add_row(
            "Dose range",
            f"{result.dose_min_display:.3f} – {result.dose_max_display:.3f} {unit}",
        )

    if result.volume_ml is not None:
        table.add_row(
            "Volume to administer",
            f"[bold yellow]{result.volume_ml:.2f} mL[/bold yellow]",
        )
    else:
        table.add_row("Volume", "[dim]N/A (no concentration)[/dim]")

    if result.concentration_mg_ml is not None:
        table.add_row("Concentration used", f"{result.concentration_mg_ml} mg/mL")

    if result.pediatric_cap_applied:
        table.add_row("Pediatric cap", f"[magenta]Applied ({result.pediatric_max_dose_mg} mg max)[/magenta]")

    if result.max_dose_exceeded:
        table.add_row("Max dose cap", f"[red]Applied ({result.max_single_dose_mg} mg max)[/red]")

    table.add_row("Frequency", result.frequency or "—")
    if result.onset_min is not None:
        onset_str = f"{result.onset_min:.0f} min"
        if result.duration_min is not None:
            onset_str += f" · Duration: {result.duration_min:.0f} min"
        table.add_row("Onset / Duration", onset_str)

    if result.reversal_agent:
        table.add_row("Reversal agent", f"[cyan]{result.reversal_agent.title()}[/cyan]")

    if result.controlled_substance:
        table.add_row("Controlled substance", f"[yellow]{result.controlled_substance}[/yellow]")

    console.print(table)

    # Notes
    if result.notes:
        console.print(Panel(
            f"[dim]{result.notes}[/dim]",
            title="[bold]Clinical Notes[/bold]",
            style="dim",
            expand=False,
        ))

    # Warnings
    if result.warnings:
        console.print()
        console.print(Rule("[yellow]⚠  Warnings[/yellow]"))
        for w in result.warnings:
            console.print(f"  [yellow]•[/yellow] {w}")

    # Contraindications
    _render_contraindications(result.contraindications)

    # Interactions
    _render_interactions(result.interactions)

    console.print()


def _render_drip_result(result: DripResult) -> None:
    """Render a DripResult to the terminal."""
    console.print()
    console.print(Panel(
        f"[bold white]{result.display_name}[/bold white]  [dim]IV Drip[/dim]",
        style="bright_blue",
        expand=False,
    ))

    table = Table(box=box.ROUNDED, show_header=False, pad_edge=True)
    table.add_column("Field", style="dim cyan", width=26)
    table.add_column("Value", style="bold white")

    table.add_row("Ordered dose", f"{result.ordered_dose} {result.dose_unit}")
    table.add_row("Patient weight", f"{result.patient_weight_kg} kg")
    table.add_row("Concentration", f"{result.concentration_mg_ml:.4f} mg/mL")
    table.add_row("Bag volume", f"{result.bag_volume_ml} mL")
    table.add_row(
        "Infusion rate",
        f"[bold green]{result.rate_ml_per_hr:.2f} mL/hr[/bold green]"
        f"  [dim]({result.rate_ml_per_min:.4f} mL/min)[/dim]",
    )
    table.add_row("Dose delivered", f"{result.dose_mg_per_min * 60:.3f} mg/hr")

    if result.duration_hr is not None:
        h = int(result.duration_hr)
        m = int((result.duration_hr - h) * 60)
        table.add_row("Bag duration", f"[yellow]{h}h {m}m[/yellow] at this rate")

    console.print(table)

    if result.rate_exceeded:
        console.print(f"\n  [red bold]⚠  Rate exceeds documented maximum for this drug![/red bold]")

    if result.warnings:
        console.print()
        console.print(Rule("[yellow]⚠  Warnings[/yellow]"))
        for w in result.warnings:
            console.print(f"  [yellow]•[/yellow] {w}")

    console.print()


def _render_contraindications(flags: list[ContraindicationFlag]) -> None:
    if not flags:
        return
    console.print()
    console.print(Rule("[red]Safety Flags[/red]"))
    for f in flags:
        prefix = "[bold red]✗ ABSOLUTE[/bold red]" if f.absolute else "[orange3]⚠  RELATIVE[/orange3]"
        cat_color = CONTRA_CATEGORY_COLOR.get(f.category, "white")
        cat_str = f"[{cat_color}][{f.category.upper()}][/{cat_color}]"
        console.print(f"  {prefix} {cat_str}  {f.detail}")


def _render_interactions(flags: list[InteractionFlag]) -> None:
    if not flags:
        return
    console.print()
    console.print(Rule("[orange3]Drug Interactions[/orange3]"))
    for ix in flags:
        sev_color = SEVERITY_COLOR.get(ix.severity, "white")
        console.print(
            f"  [{sev_color}]{ix.severity.upper()}[/{sev_color}]  "
            f"[bold]{ix.drug_a.title()}[/bold] ⟺ [bold]{ix.drug_b.title()}[/bold]"
        )
        console.print(f"    [dim]{ix.description}[/dim]")
        if ix.management:
            console.print(f"    [cyan]Management:[/cyan] {ix.management}")
        console.print()


# ---------------------------------------------------------------------------
# Patient input helper
# ---------------------------------------------------------------------------

def _prompt_patient(
    weight: Optional[float] = None,
    age: Optional[float] = None,
    allergies: Optional[list[str]] = None,
    meds: Optional[list[str]] = None,
    conditions: Optional[list[str]] = None,
) -> Patient:
    """Interactively build a Patient from CLI prompts if values not supplied."""
    if weight is None:
        weight = click.prompt(
            click.style("  Patient weight (kg)", fg="cyan"), type=float
        )
    if age is None:
        age_str = click.prompt(
            click.style("  Patient age in years (Enter to skip)", fg="cyan"),
            default="", show_default=False,
        )
        age = float(age_str) if age_str.strip() else None

    if allergies is None:
        allergy_str = click.prompt(
            click.style("  Known allergies (comma-separated, Enter to skip)", fg="cyan"),
            default="", show_default=False,
        )
        allergies = [a.strip() for a in allergy_str.split(",") if a.strip()]

    if meds is None:
        meds_str = click.prompt(
            click.style("  Current medications (comma-separated, Enter to skip)", fg="cyan"),
            default="", show_default=False,
        )
        meds = [m.strip() for m in meds_str.split(",") if m.strip()]

    if conditions is None:
        cond_str = click.prompt(
            click.style("  Medical conditions (comma-separated, Enter to skip)", fg="cyan"),
            default="", show_default=False,
        )
        conditions = [c.strip() for c in cond_str.split(",") if c.strip()]

    pregnant_str = click.prompt(
        click.style("  Pregnant? (y/N)", fg="cyan"), default="n", show_default=False
    )
    is_pregnant = pregnant_str.strip().lower() == "y"

    renal_str = click.prompt(
        click.style("  Significant renal impairment? (y/N)", fg="cyan"), default="n", show_default=False
    )
    hepatic_str = click.prompt(
        click.style("  Significant hepatic impairment? (y/N)", fg="cyan"), default="n", show_default=False
    )

    try:
        return Patient(
            weight_kg=weight,
            age_years=age,
            allergies=allergies,
            current_medications=meds,
            conditions=conditions,
            is_pregnant=is_pregnant,
            renal_impairment=renal_str.strip().lower() == "y",
            hepatic_impairment=hepatic_str.strip().lower() == "y",
        )
    except InvalidPatientError as e:
        console.print(f"\n[red]Invalid patient data:[/red] {e}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------

@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def main() -> None:
    """
    \b
    ╔═══════════════════════════════════╗
    ║  💊  drugdose  — Clinical Dosing  ║
    ╚═══════════════════════════════════╝

    Weight-based drug dosing calculator for EMS and clinical use.
    """


# ---------------------------------------------------------------------------
# calculate command
# ---------------------------------------------------------------------------

@main.command("calculate")
@click.argument("drug", required=False)
@click.option("-r", "--route", default=None, help="Administration route (IV, IM, IN, etc.)")
@click.option("-w", "--weight", type=float, default=None, help="Patient weight in kg")
@click.option("-a", "--age", type=float, default=None, help="Patient age in years")
@click.option("--allergies", default=None, help="Comma-separated allergies")
@click.option("--meds", default=None, help="Comma-separated current medications")
@click.option("--conditions", default=None, help="Comma-separated medical conditions")
@click.option("-c", "--concentration", type=float, default=None, help="Stock concentration in mg/mL")
@click.option(
    "--fraction",
    type=click.FloatRange(0.0, 1.0),
    default=1.0,
    show_default=True,
    help="Dose fraction (0=min, 0.5=mid, 1=max)",
)
@click.option("--range", "show_range", is_flag=True, default=False, help="Show full min–max dose range")
def cmd_calculate(
    drug, route, weight, age, allergies, meds, conditions, concentration, fraction, show_range
) -> None:
    """Calculate a weight-based drug dose.

    \b
    Examples:
      drugdose calculate epinephrine --route IV --weight 70
      drugdose calculate fentanyl -r IM -w 25 --age 8
      drugdose calculate midazolam --range
    """
    console.print()
    console.print(Panel("[bold bright_blue]💊  Drug Dose Calculator[/bold bright_blue]", expand=False))

    if not drug:
        drug = click.prompt(click.style("  Drug name", fg="cyan"))

    # Resolve route
    drug_obj = get_drug(drug)
    if drug_obj is None:
        console.print(f"\n[red]Drug not found:[/red] '{drug}'. Try [cyan]drugdose search {drug}[/cyan]")
        sys.exit(1)

    if route is None:
        available = ", ".join(drug_obj.available_routes)
        route = click.prompt(
            click.style(f"  Route ({available})", fg="cyan"),
            default=drug_obj.available_routes[0] if drug_obj.available_routes else "IV",
        )

    # Parse CSV options
    allergy_list = [a.strip() for a in allergies.split(",")] if allergies else None
    med_list = [m.strip() for m in meds.split(",")] if meds else None
    cond_list = [c.strip() for c in conditions.split(",")] if conditions else None

    patient = _prompt_patient(weight, age, allergy_list, med_list, cond_list)

    console.print()
    try:
        if show_range:
            min_r, max_r = calculate_range(drug, patient, route.upper(), concentration)
            console.print(Rule("[cyan]Minimum Dose[/cyan]"))
            _render_dose_result(min_r)
            console.print(Rule("[cyan]Maximum Dose[/cyan]"))
            _render_dose_result(max_r)
        else:
            result = calculate_dose(drug, patient, route.upper(), concentration, fraction)
            _render_dose_result(result)
    except DrugDoseError as e:
        console.print(f"\n[red]Error:[/red] {e}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# drip command
# ---------------------------------------------------------------------------

@main.command("drip")
@click.argument("drug", required=False)
@click.option("-w", "--weight", type=float, default=None, help="Patient weight in kg")
@click.option("-d", "--dose", type=float, default=None, help="Ordered dose (numeric)")
@click.option("-u", "--unit", default=None, help="Dose unit (e.g. mcg/kg/min, mg/hr)")
@click.option("-c", "--concentration", type=float, default=None, help="Bag concentration in mg/mL")
@click.option("-b", "--bag", type=float, default=250.0, show_default=True, help="Bag volume in mL")
@click.option("--mix", is_flag=True, default=False, help="Calculate a standard mixture concentration")
@click.option("--total-mg", type=float, default=None, help="Total drug in bag (mg) for --mix")
def cmd_drip(drug, weight, dose, unit, concentration, bag, mix, total_mg) -> None:
    """Calculate IV drip / infusion pump rate.

    \b
    Examples:
      drugdose drip dopamine -w 70 -d 5 -u mcg/kg/min
      drugdose drip norepinephrine -w 80 -d 0.05 -u mcg/kg/min -c 0.064
      drugdose drip epinephrine --mix --total-mg 4 -b 250
    """
    console.print()
    console.print(Panel("[bold bright_blue]🩺  IV Drip Rate Calculator[/bold bright_blue]", expand=False))

    if not drug:
        drug = click.prompt(click.style("  Drug name", fg="cyan"))

    drug_obj = get_drug(drug)
    if drug_obj is None:
        console.print(f"\n[red]Drug not found:[/red] '{drug}'.")
        sys.exit(1)

    if mix:
        if total_mg is None:
            total_mg = click.prompt(click.style("  Total drug in bag (mg)", fg="cyan"), type=float)
        conc = standard_mixture(drug, total_mg, bag)
        console.print()
        console.print(Panel(
            f"[bold white]{drug_obj.display_name}[/bold white]\n"
            f"{total_mg} mg in {bag} mL  →  [bold green]{conc:.4f} mg/mL[/bold green]",
            title="Mixture Concentration",
            style="bright_blue",
            expand=False,
        ))
        return

    if weight is None:
        weight = click.prompt(click.style("  Patient weight (kg)", fg="cyan"), type=float)
    if dose is None:
        dose = click.prompt(click.style("  Ordered dose (number)", fg="cyan"), type=float)
    if unit is None:
        drip_routes = [rc for rc in drug_obj.routes if rc.continuous_infusion]
        default_unit = drip_routes[0].dose_unit if drip_routes else "mcg/kg/min"
        unit = click.prompt(click.style(f"  Dose unit (e.g. {default_unit})", fg="cyan"))

    try:
        patient = Patient(weight_kg=weight)
        result = calculate_drip(drug, patient, dose, unit, concentration, bag)
        _render_drip_result(result)
    except DrugDoseError as e:
        console.print(f"\n[red]Error:[/red] {e}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# info command
# ---------------------------------------------------------------------------

@main.command("info")
@click.argument("drug")
def cmd_info(drug: str) -> None:
    """Show detailed information about a drug.

    \b
    Examples:
      drugdose info ketamine
      drugdose info "EpiPen"
    """
    drug_obj = get_drug(drug)
    if drug_obj is None:
        console.print(f"\n[red]Drug not found:[/red] '{drug}'.")
        console.print(f"Try: [cyan]drugdose search {drug}[/cyan]")
        sys.exit(1)

    console.print()
    console.print(Panel(
        f"[bold white]{drug_obj.display_name}[/bold white]\n"
        f"[dim]{drug_obj.drug_class}[/dim]",
        style="bright_blue",
        expand=False,
    ))

    # General info
    table = Table(box=box.SIMPLE, show_header=False, pad_edge=True)
    table.add_column("Field", style="dim cyan", width=22)
    table.add_column("Value", style="white")

    if drug_obj.brand_names:
        table.add_row("Brand names", ", ".join(drug_obj.brand_names))
    table.add_row("Indication", drug_obj.indication or "—")
    table.add_row("Mechanism", drug_obj.mechanism or "—")
    table.add_row("Pregnancy", f"Category {drug_obj.pregnancy_category}")
    if drug_obj.controlled_substance:
        table.add_row("Controlled", f"[yellow]{drug_obj.controlled_substance}[/yellow]")
    if drug_obj.reversal_agent:
        table.add_row("Reversal agent", f"[cyan]{drug_obj.reversal_agent.title()}[/cyan]")
    table.add_row("Renal caution", "[red]Yes[/red]" if drug_obj.renal_caution else "No")
    table.add_row("Hepatic caution", "[red]Yes[/red]" if drug_obj.hepatic_caution else "No")
    if drug_obj.tags:
        table.add_row("Tags", ", ".join(drug_obj.tags))

    console.print(table)

    # Contraindications
    if drug_obj.contraindications:
        console.print(Rule("[red]Contraindications[/red]"))
        for ci in drug_obj.contraindications:
            console.print(f"  • {ci}")

    # Routes table
    console.print()
    console.print(Rule("[cyan]Available Routes & Dosing[/cyan]"))
    for rc in drug_obj.routes:
        label = f"[bold cyan]{rc.route}[/bold cyan]"
        if rc.continuous_infusion:
            label += " [dim](infusion)[/dim]"
        rt = Table(box=box.MINIMAL_HEAVY_HEAD, title=label, show_header=True, pad_edge=True)
        rt.add_column("Parameter", style="dim")
        rt.add_column("Value", style="white")

        unit_label = rc.dose_unit
        rt.add_row("Dose min", f"{rc.dose_min} {unit_label}")
        rt.add_row("Dose max", f"[bold]{rc.dose_max} {unit_label}[/bold]")
        if rc.max_single_dose_mg is not None:
            rt.add_row("Max single dose", f"{rc.max_single_dose_mg} mg")
        if rc.pediatric_max_dose_mg is not None:
            rt.add_row("Peds max dose", f"{rc.pediatric_max_dose_mg} mg")
        if rc.standard_concentration_mg_ml is not None:
            rt.add_row("Default concentration", f"{rc.standard_concentration_mg_ml} mg/mL")
        if rc.frequency:
            rt.add_row("Frequency", rc.frequency)
        if rc.onset_min is not None:
            rt.add_row("Onset", f"{rc.onset_min} min")
        if rc.duration_min is not None:
            rt.add_row("Duration", f"{rc.duration_min} min")
        if rc.notes:
            rt.add_row("Notes", f"[dim]{rc.notes}[/dim]")

        console.print(rt)

    console.print()


# ---------------------------------------------------------------------------
# search command
# ---------------------------------------------------------------------------

@main.command("search")
@click.argument("query", default="")
@click.option("-t", "--tag", default=None, help="Filter by tag (e.g. cardiac, emergency, analgesic)")
def cmd_search(query: str, tag: Optional[str]) -> None:
    """Search the drug database by name, indication, or tag.

    \b
    Examples:
      drugdose search opioid
      drugdose search --tag cardiac
      drugdose search epi
    """
    results = search_drugs(query, tag)

    if not results:
        console.print(f"\n[yellow]No results for:[/yellow] '{query}'" + (f" [tag={tag}]" if tag else ""))
        return

    console.print()
    table = Table(
        title=f"Search results for [cyan]'{query}'[/cyan]" + (f"  [dim][tag={tag}][/dim]" if tag else ""),
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Drug", style="bold white", min_width=28)
    table.add_column("Class", style="dim", min_width=30)
    table.add_column("Routes", style="cyan")
    table.add_column("Tags", style="dim green")

    for drug_obj in results:
        table.add_row(
            drug_obj.display_name,
            drug_obj.drug_class,
            ", ".join(drug_obj.available_routes),
            ", ".join(drug_obj.tags[:4]),
        )

    console.print(table)
    console.print(f"\n[dim]{len(results)} drug(s) found. Use [cyan]drugdose info <name>[/cyan] for details.[/dim]")


# ---------------------------------------------------------------------------
# list command
# ---------------------------------------------------------------------------

@main.command("list")
@click.option("-t", "--tag", default=None, help="Filter by tag")
@click.option("--class", "drug_class", default=None, help="Filter by drug class keyword")
def cmd_list(tag: Optional[str], drug_class: Optional[str]) -> None:
    """List all drugs in the database.

    \b
    Examples:
      drugdose list
      drugdose list --tag emergency
      drugdose list --class opioid
    """
    all_drugs = list(get_all_drugs().values())

    if tag:
        all_drugs = [d for d in all_drugs if tag.lower() in [t.lower() for t in d.tags]]
    if drug_class:
        all_drugs = [d for d in all_drugs if drug_class.lower() in d.drug_class.lower()]

    all_drugs = sorted(all_drugs, key=lambda d: d.display_name)

    console.print()
    table = Table(
        title="Drug Database",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("#", style="dim", width=4)
    table.add_column("Drug", style="bold white", min_width=30)
    table.add_column("Class", style="dim", min_width=32)
    table.add_column("Ctrl", style="yellow", width=5)
    table.add_column("Routes", style="cyan")

    for i, drug_obj in enumerate(all_drugs, 1):
        ctrl = "✓" if drug_obj.controlled_substance else ""
        table.add_row(
            str(i),
            drug_obj.display_name,
            drug_obj.drug_class,
            ctrl,
            ", ".join(drug_obj.available_routes),
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(all_drugs)} drugs. [cyan]drugdose info <name>[/cyan] for full details.[/dim]")


# ---------------------------------------------------------------------------
# check command
# ---------------------------------------------------------------------------

@main.command("check")
@click.argument("drug")
@click.option("-w", "--weight", type=float, default=None)
@click.option("-a", "--age", type=float, default=None)
@click.option("--allergies", default=None)
@click.option("--meds", default=None)
@click.option("--conditions", default=None)
def cmd_check(drug, weight, age, allergies, meds, conditions) -> None:
    """Run a full safety check for a drug and patient.

    \b
    Examples:
      drugdose check amiodarone --meds digoxin,metoprolol --age 72 --weight 80
      drugdose check morphine --allergies codeine --conditions respiratory_depression
    """
    drug_obj = get_drug(drug)
    if drug_obj is None:
        console.print(f"\n[red]Drug not found:[/red] '{drug}'.")
        sys.exit(1)

    allergy_list = [a.strip() for a in allergies.split(",")] if allergies else None
    med_list = [m.strip() for m in meds.split(",")] if meds else None
    cond_list = [c.strip() for c in conditions.split(",")] if conditions else None

    patient = _prompt_patient(weight, age, allergy_list, med_list, cond_list)

    ci_flags, ix_flags = full_safety_check(drug_obj, patient)

    console.print()
    console.print(Panel(
        f"[bold white]Safety Check: {drug_obj.display_name}[/bold white]",
        style="bright_blue",
        expand=False,
    ))

    if not ci_flags and not ix_flags:
        console.print("\n[green]✓ No contraindications or interactions found for this patient.[/green]\n")
        return

    _render_contraindications(ci_flags)
    _render_interactions(ix_flags)
    console.print()


# ---------------------------------------------------------------------------
# version command
# ---------------------------------------------------------------------------

@main.command("version")
def cmd_version() -> None:
    """Show version and library info."""
    console.print()
    console.print(Panel(
        f"[bold white]drugdose[/bold white]  v[cyan]{__version__}[/cyan]\n"
        "[dim]EMS & Clinical Drug Dosing Calculator Library\n"
        "https://github.com/Londopy/drugdose[/dim]",
        style="bright_blue",
        expand=False,
    ))
    total = len(get_all_drugs())
    console.print(f"\n[dim]Database: {total} drugs loaded[/dim]\n")
