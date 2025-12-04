#!/usr/bin/env python3
"""
Pre-commit hook to check if ADRs in docs/20_architecture/adrs/
are listed in mkdocs.yml navigation.
"""

import sys
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]


def get_adr_files() -> set[str]:
    """Get all ADR markdown files from the adrs directory."""
    adr_dir = Path("docs/20_architecture/adrs")
    if not adr_dir.exists():
        return set()
    return {f.name for f in adr_dir.glob("*.md")}


def get_mkdocs_adrs() -> set[str]:
    """Extract ADR files listed in mkdocs.yml."""
    try:
        with open("mkdocs.yml") as f:
            config: dict[str, Any] = yaml.safe_load(f)

        # Navigate through the nav structure to find ADRs
        nav: list[Any] = config.get("nav", [])
        for section in nav:
            if isinstance(section, dict) and "Architecture" in section:
                arch_items: list[Any] = section["Architecture"]
                for item in arch_items:
                    if isinstance(item, dict) and "ADRs" in item:
                        adrs_list: list[Any] = item["ADRs"]
                        # Each ADR is a dict with title: path
                        result = set()
                        for adr_item in adrs_list:
                            if isinstance(adr_item, dict):
                                for path in adr_item.values():
                                    if isinstance(path, str):
                                        result.add(Path(path).name)
                        return result
        return set()
    except Exception as e:
        print(f"Error reading mkdocs.yml: {e}")
        return set()


def main() -> int:
    adr_files = get_adr_files()
    mkdocs_adrs = get_mkdocs_adrs()

    missing_in_mkdocs = adr_files - mkdocs_adrs

    if missing_in_mkdocs:
        print("[ERROR] The following ADRs are not listed in mkdocs.yml:")
        for adr in sorted(missing_in_mkdocs):
            print(f"  - {adr}")
        print("\nPlease add them to the 'Architecture > ADRs' section in mkdocs.yml")
        return 1

    print("[OK] All ADRs are listed in mkdocs.yml")
    return 0


if __name__ == "__main__":
    sys.exit(main())
