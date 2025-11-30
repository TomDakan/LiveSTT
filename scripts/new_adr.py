#!/usr/bin/env python
"""Creates a new, numbered ADR file from the template."""

import re
import sys
from datetime import date
from pathlib import Path

# --- Configuration ---
# [ ]: ADR_DIR should probably be configurable in the future
ADR_DIR = Path("docs/adr")
TEMPLATE_FILE = ADR_DIR / "0000-template.md"
TITLE_PLACEHOLDER = "ADR_TITLE_PLACEHOLDER"
DATE_PLACEHOLDER = "YYYY-MM-DD"
# --------------------


def get_next_adr_num() -> int:
    """Finds the highest existing ADR number and returns the next sequential number."""
    if not ADR_DIR.exists():
        print(f"Creating ADR directory: {ADR_DIR}")
        ADR_DIR.mkdir(parents=True)

    highest_num = 0
    # Iterate through markdown files in the ADR directory
    for f in ADR_DIR.glob("*.md"):
        # Match filenames like '0001-some-decision.md'
        if match := re.match(r"^(\d{4})-.*\.md$", f.name):
            num = int(match.group(1))
            highest_num = max(highest_num, num)
    return highest_num + 1


def slugify(text: str) -> str:
    """Converts a title string into a lowercase, hyphen-separated slug."""
    text = text.lower()
    # Remove characters that aren't alphanumeric, underscores, hyphens, or whitespace
    text = re.sub(r"[^\w\s-]", "", text)
    # Replace whitespace and repeated hyphens with a single hyphen
    text = re.sub(r"[\s_]+", "-", text)
    # Remove leading/trailing hyphens
    text = text.strip("-")
    # Return 'new-decision' if the slug ends up empty
    return text or "new-decision"


def create_adr_file(adr_num: int, title: str, slug: str) -> Path | None:
    """Creates the new ADR file from the template and returns its path."""
    if not TEMPLATE_FILE.exists():
        print(f"Error: Template file not found at {TEMPLATE_FILE}", file=sys.stderr)
        return None

    new_adr_file = ADR_DIR / f"{adr_num:04d}-{slug}.md"
    current_date_str = date.today().strftime("%Y-%m-%d")

    try:
        content = TEMPLATE_FILE.read_text(encoding="utf-8")

        content = content.replace(TITLE_PLACEHOLDER, title)
        content = content.replace(DATE_PLACEHOLDER, current_date_str)

        new_adr_file.write_text(content, encoding="utf-8")
        print(f"Created new ADR: {new_adr_file}")
        return new_adr_file
    except OSError as e:
        print(f"Error writing file {new_adr_file}: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        return None


def main() -> None:
    """Parses arguments and orchestrates ADR creation."""
    # Get the title from command line arguments (joined if multiple words)
    title = " ".join(sys.argv[1:])

    if not title:
        print("Error: A title for the ADR is required.", file=sys.stderr)
        print("\nUsage example:")
        print('  uv run scripts/new_adr.py "Your concise decision title"', file=sys.stderr)
        print("  # or, if using just:")
        print('  just adr "Your concise decision title"', file=sys.stderr)
        sys.exit(1)

    adr_num = get_next_adr_num()
    slug = slugify(title)

    if not create_adr_file(adr_num, title, slug):
        sys.exit(1)


if __name__ == "__main__":
    main()
