#!/usr/bin/env python3
"""Check that an ai-log cleanup preserves incoming Obsidian block wikilinks."""

import argparse
from collections import Counter
from pathlib import Path
import re
import sys
from urllib.parse import unquote


BLOCK_ID = re.compile(r"(?:^|[ \t])\^([A-Za-z0-9-]+)[ \t]*$")
BLOCK_LINK = re.compile(r"\[\[([^\]#|\r\n]*)#\^([A-Za-z0-9-]+)(?:\|[^\]\r\n]*)?\]\]")


def block_anchors(text):
    anchors = Counter()
    previous = ""
    for line in text.splitlines():
        match = BLOCK_ID.search(line)
        if match:
            # A standalone ID refers to the preceding block.
            context = previous if not line[:match.start()].strip() else ""
            anchors[match[1], line, context] += 1
        if line.strip():
            previous = line
    return anchors


def targets_note(link, source, note, vault):
    if not link:
        return source.resolve() == note
    for spelling in (link, unquote(link)):
        if spelling.lower().endswith(".md"):
            spelling = spelling[:-3]
        if spelling.startswith(("./", "../")):
            relative = (source.parent / (spelling + ".md")).resolve()
            if relative == note:
                return True
        else:
            target = note.relative_to(vault).with_suffix("").as_posix().casefold()
            spelling = spelling.lstrip("/").casefold()
            if target == spelling or target.endswith("/" + spelling):
                return True
    return False


def affected_links(vault, note, original, candidate):
    removed_ids = {block_id for block_id, _, _ in block_anchors(original) - block_anchors(candidate)}
    if not removed_ids:
        return
    for source in sorted(vault.rglob("*.md")):
        relative = source.relative_to(vault)
        if any(part.startswith(".") for part in relative.parts):
            continue
        text = candidate if source.resolve() == note else source.read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), 1):
            for link, block_id in BLOCK_LINK.findall(line):
                if block_id in removed_ids and targets_note(link, source, note, vault):
                    yield f"{relative}:{number}: [[{link}#^{block_id}]]"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, required=True, help="Vault directory")
    parser.add_argument("--path", type=Path, required=True, help="Original note path relative to the vault")
    parser.add_argument("--candidate", type=Path, required=True, help="Full proposed note, saved outside the vault")
    args = parser.parse_args()
    try:
        vault = args.vault.resolve()
        note = (vault / args.path).resolve()
        if not note.is_relative_to(vault):
            parser.error("The original note must be inside the vault")
        if args.candidate.resolve().is_relative_to(vault):
            parser.error("Save the candidate outside the vault")
        original = note.read_text(encoding="utf-8")
        candidate = args.candidate.read_text(encoding="utf-8")
        affected = list(affected_links(vault, note, original, candidate))
    except (OSError, UnicodeError) as error:
        parser.error(str(error))
    for link in affected:
        print(link, file=sys.stderr)
    return int(bool(affected))


if __name__ == "__main__":
    sys.exit(main())
