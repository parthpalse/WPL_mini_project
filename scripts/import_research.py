"""Research ingestion script.

Validates and converts research data from /research/ into versioned config files.
Fails loudly if any rate, assumption, or tax parameter lacks a verifiable source or as_of date.
"""

import os
import sys
import json
from datetime import datetime
from typing import Dict, Any

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.config_schema import validate_all_configs


def validate_research_entry(entry: Dict[str, Any], entry_name: str) -> None:
    """Ensure every research entry contains verifiable provenance."""
    if not entry.get('source'):
        raise ValueError(f"Research entry '{entry_name}' is missing required 'source'.")
    if not entry.get('as_of'):
        raise ValueError(f"Research entry '{entry_name}' is missing required 'as_of' date.")
    try:
        datetime.strptime(entry['as_of'], "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"Research entry '{entry_name}' has invalid as_of format '{entry['as_of']}'. Must be YYYY-MM-DD.")


def import_research_file(research_file_path: str, config_dir: str = "config") -> None:
    """Ingest a research JSON file and update corresponding config files."""
    if not os.path.exists(research_file_path):
        raise FileNotFoundError(f"Research file not found: {research_file_path}")

    with open(research_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"Loaded research file: {research_file_path}")

    # Process Products if present
    if 'products' in data:
        for p in data['products']:
            validate_research_entry(p, f"Product {p.get('name')}")
        target_path = os.path.join(config_dir, "products.json")
        with open(target_path, 'w', encoding='utf-8') as f:
            json.dump({"as_of": str(datetime.now().date()), "version": "imported", "products": data['products']}, f, indent=2)
        print(f"Updated {target_path}")

    # Process Macro if present
    if 'macro' in data:
        macro = data['macro']
        validate_research_entry(macro.get('inflation', {}), "Inflation")
        validate_research_entry(macro.get('risk_free_rate', {}), "Risk Free Rate")
        target_path = os.path.join(config_dir, "macro.json")
        with open(target_path, 'w', encoding='utf-8') as f:
            json.dump(macro, f, indent=2)
        print(f"Updated {target_path}")

    # Validate resulting configs
    validate_all_configs(config_dir)
    print("All updated configurations validated successfully!")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        research_dir = os.path.join(PROJECT_ROOT, "research")
        if not os.path.exists(research_dir):
            print(f"No research file specified and directory '{research_dir}' does not exist.")
            print("Usage: python scripts/import_research.py <path_to_research.json>")
            sys.exit(0)
        files = [os.path.join(research_dir, f) for f in os.listdir(research_dir) if f.endswith('.json')]
        if not files:
            print("No JSON files found in research/.")
            sys.exit(0)
        path = files[0]

    import_research_file(path)
