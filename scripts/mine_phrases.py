#!/usr/bin/env python3
"""
Script to mine high-frequency proper nouns from caption files (VTT/JSON).
Used for creating the 'Silver Standard' dataset for Deepgram PhraseSets.

Usage:
    python scripts/mine_phrases.py data/silver/ --output=config/initial_phrases.json --min-frequency=3
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

# Common English stop words to ignore even if capitalized (e.g. at start of sentence)
STOP_WORDS = {
    "The",
    "A",
    "An",
    "And",
    "But",
    "Or",
    "Nor",
    "For",
    "Yet",
    "So",
    "I",
    "You",
    "He",
    "She",
    "It",
    "We",
    "They",
    "My",
    "Your",
    "His",
    "Her",
    "Its",
    "Our",
    "Their",
    "This",
    "That",
    "These",
    "Those",
    "Here",
    "There",
    "Where",
    "When",
    "Why",
    "How",
    "In",
    "On",
    "At",
    "To",
    "From",
    "By",
    "With",
    "About",
    "Of",
    "As",
    "Is",
    "Are",
    "Was",
    "Were",
    "Be",
    "Been",
    "Being",
    "Have",
    "Has",
    "Had",
    "Do",
    "Does",
    "Did",
    "Can",
    "Could",
    "Will",
    "Would",
    "Shall",
    "Should",
    "May",
    "Might",
    "Must",
    "God",
    "Lord",
    "Jesus",
    "Christ",  # Common in church context, but maybe we WANT these if they are specific titles?
    # Actually, let's keep God/Jesus/Christ as valid phrases if they appear frequently,
    # but maybe filter out generic "God" if it's too common.
    # For now, let's exclude the most generic ones to focus on specific names/places.
}


def parse_vtt(file_path: Path) -> str:
    """Extract text content from a VTT file."""
    text_content = []
    try:
        with open(file_path, encoding="utf-8") as f:
            lines = f.readlines()

        # Simple VTT parser: skip headers, timestamps, and empty lines
        # VTT timestamp regex: 00:00:00.000 --> 00:00:00.000
        timestamp_pattern = re.compile(
            r"\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}"
        )

        for line in lines:
            line = line.strip()
            if not line:
                continue
            if (
                line.startswith("WEBVTT")
                or line.startswith("Kind:")
                or line.startswith("Language:")
            ):
                continue
            if timestamp_pattern.match(line):
                continue
            # Skip numeric identifiers often found in VTT
            if line.isdigit():
                continue

            text_content.append(line)

    except Exception as e:
        print(f"⚠️ Error reading {file_path}: {e}", file=sys.stderr)

    return " ".join(text_content)


def extract_phrases(text: str) -> list[str]:
    """
    Extract potential proper nouns (capitalized words), including multi-word phrases.
    Strategy:
    1. Split into words.
    2. Identify sequences of capitalized words.
    3. Filter out stop words (unless they are part of a larger phrase? No, keep simple for now).
    """
    # Remove punctuation but keep spaces
    text = re.sub(r"[^\w\s]", "", text)
    words = text.split()

    candidates = []
    current_phrase = []

    for word in words:
        # Check if word is capitalized, alphabetic, and not a stop word
        is_capitalized = word[0].isupper() and word.isalpha() and len(word) > 1
        is_stop = word in STOP_WORDS

        if is_capitalized and not is_stop:
            current_phrase.append(word)
        else:
            # End of a phrase sequence
            if current_phrase:
                print(f"DEBUG: Found phrase: {' '.join(current_phrase)}")
                candidates.append(" ".join(current_phrase))
                current_phrase = []

    # Capture the last phrase if exists
    if current_phrase:
        candidates.append(" ".join(current_phrase))

    return candidates


def main():
    parser = argparse.ArgumentParser(description="Mine phrases from caption files.")
    parser.add_argument("input_dir", type=Path, help="Directory containing .vtt files")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("config/initial_phrases.json"),
        help="Output JSON file",
    )
    parser.add_argument(
        "--min-frequency",
        type=int,
        default=3,
        help="Minimum frequency to include a phrase",
    )

    args = parser.parse_args()

    if not args.input_dir.exists():
        print(f"❌ Input directory not found: {args.input_dir}")
        sys.exit(1)

    print(f"📂 Scanning {args.input_dir} for .vtt files...")
    files = list(args.input_dir.glob("*.vtt"))
    if not files:
        # Try .en.vtt (common from yt-dlp)
        files = list(args.input_dir.glob("*.en.vtt"))

    if not files:
        print("⚠️ No .vtt files found.")
        sys.exit(0)

    print(f"   Found {len(files)} files.")

    all_candidates = []

    for file_path in files:
        text = parse_vtt(file_path)
        candidates = extract_phrases(text)
        all_candidates.extend(candidates)

    # Count frequencies
    counts = Counter(all_candidates)

    # Filter
    valid_phrases = [
        phrase for phrase, count in counts.items() if count >= args.min_frequency
    ]

    # Sort alphabetically
    valid_phrases.sort()

    print(f"📊 Found {len(valid_phrases)} unique phrases (freq >= {args.min_frequency})")
    print(f"   Top 10: {', '.join([p for p, c in counts.most_common(10)])}")

    # Format for Deepgram (simple list of strings, or object with boost)
    # Deepgram expects: { "phrases": ["Phrase1", "Phrase2"] } OR { "phrases": [{ "phrase": "Phrase1", "boost": 10 }] }
    # Let's use simple string list for now, user can manually tune boosts later.

    output_data = {
        "phrases": valid_phrases,
        "meta": {
            "source": "Silver Standard Mining",
            "file_count": len(files),
            "min_frequency": args.min_frequency,
        },
    }

    # Ensure output dir exists
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)

    print(f"✅ Saved to {args.output}")


if __name__ == "__main__":
    main()
