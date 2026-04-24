"""
Drug database loader and lookup functions.

The database is loaded once at import time from the bundled JSON files.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from .models.drug import Drug

_DATA_DIR = Path(__file__).parent / "data"


@lru_cache(maxsize=1)
def _load_drugs() -> dict[str, Drug]:
    """Load and cache the drug database. Returns {name: Drug}."""
    path = _DATA_DIR / "drugs.json"
    with open(path, encoding="utf-8") as f:
        raw: list[dict] = json.load(f)

    drugs: dict[str, Drug] = {}
    for entry in raw:
        drug = Drug.from_dict(entry)
        # Only insert if not already present (first entry wins for duplicates)
        if drug.name not in drugs:
            drugs[drug.name] = drug
    return drugs


@lru_cache(maxsize=1)
def _load_interactions() -> list[dict]:
    """Load and cache the interaction rule set."""
    path = _DATA_DIR / "interactions.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("interactions", [])


def get_all_drugs() -> dict[str, Drug]:
    """Return the full drug database as {name: Drug}."""
    return _load_drugs()


def get_drug(name: str) -> Optional[Drug]:
    """
    Look up a drug by name (case-insensitive).

    Searches by canonical name and brand names.  Returns None if not found.
    """
    normalised = name.lower().strip()
    db = _load_drugs()

    # Direct match
    if normalised in db:
        return db[normalised]

    # Partial / brand-name match
    for drug in db.values():
        if normalised == drug.name:
            return drug
        if normalised == drug.display_name.lower():
            return drug
        if any(normalised == bn.lower() for bn in drug.brand_names):
            return drug
        # Substring match as last resort
        if normalised in drug.name or drug.name in normalised:
            return drug

    return None


def search_drugs(query: str, tag: Optional[str] = None) -> list[Drug]:
    """
    Search drugs by name, brand name, indication keyword, or tag.

    Parameters
    ----------
    query:
        Search string (partial match, case-insensitive). Pass '' to list all.
    tag:
        Optional tag to filter by (e.g. 'cardiac', 'emergency').
    """
    query_lower = query.lower().strip()
    db = _load_drugs()
    results: list[Drug] = []

    for drug in db.values():
        # Tag filter
        if tag and tag.lower() not in [t.lower() for t in drug.tags]:
            continue

        # Query match
        if not query_lower:
            results.append(drug)
            continue

        if (
            query_lower in drug.name
            or query_lower in drug.display_name.lower()
            or any(query_lower in bn.lower() for bn in drug.brand_names)
            or query_lower in drug.indication.lower()
            or query_lower in drug.drug_class.lower()
            or any(query_lower in t.lower() for t in drug.tags)
        ):
            results.append(drug)

    return sorted(results, key=lambda d: d.display_name)


def get_interactions() -> list[dict]:
    """Return the raw interaction rule list."""
    return _load_interactions()


def get_interactions_for(drug_name: str) -> list[dict]:
    """Return all interactions involving *drug_name*."""
    name = drug_name.lower().strip()
    return [
        i for i in _load_interactions()
        if i["drug_a"] == name or i["drug_b"] == name
    ]
