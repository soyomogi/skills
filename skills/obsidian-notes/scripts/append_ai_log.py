#!/usr/bin/env python3
"""Append a note's ai-log and embed the new entry in today's daily ai-log."""

import argparse
from contextlib import ExitStack
from datetime import datetime
import fcntl
from pathlib import Path
import re
import subprocess
import sys


def insert_in_ai_log(text, content):
    section = None
    end = len(text)
    offset = 0
    fence = None
    for line in text.splitlines(keepends=True):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if marker:
            token = marker[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
        elif fence is None:
            heading = re.match(r"^(#{1,6})[ \t]+(.+?)\s*$", line)
            if heading:
                if section is not None and len(heading[1]) <= section:
                    end = offset
                    break
                if heading[2].rstrip("#").strip() == "ai-log":
                    section = len(heading[1])
        offset += len(line)
    if section is None:
        raise ValueError("The note has no ai-log section")
    newline = "\r\n" if "\r\n" in text else "\n"
    separator = "" if text[:end].endswith("\n") else newline
    return text[:end] + separator + content + newline + text[end:]


def append_entries(path, entries, *, daily_path, note_link, timestamp=None):
    if timestamp is not None:
        datetime.strptime(timestamp, "%Y%m%d%H%M%S")
    path, daily_path = path.resolve(), daily_path.resolve()
    if path == daily_path:
        raise ValueError("Write log entries to a work note, not the daily note")
    with ExitStack() as stack:
        notes = {}
        # Use a stable lock order when multiple processes share a daily note.
        for target in sorted((path, daily_path)):
            note = stack.enter_context(target.open("r+", encoding="utf-8", newline=""))
            fcntl.flock(note, fcntl.LOCK_EX)
            notes[target] = note
        text = notes[path].read()
        timestamp = timestamp or datetime.now().astimezone().strftime("%Y%m%d%H%M%S")
        block_id = timestamp
        used_ids = set(re.findall(r"\^([A-Za-z0-9-]+)[ \t\r]*$", text, re.MULTILINE))
        suffix = 2
        while block_id in used_ids:
            block_id = f"{timestamp}-{suffix}"
            suffix += 1
        content = f"- {timestamp} {' / '.join(entries)} ^{block_id}"
        reference = f"![[{note_link}#^{block_id}]]"
        # Validate both sections before changing either file.
        updates = {
            path: insert_in_ai_log(text, content),
            daily_path: insert_in_ai_log(notes[daily_path].read(), reference),
        }
        for target, updated in updates.items():
            note = notes[target]
            note.seek(0)
            note.write(updated)
            note.truncate()
            note.flush()
        return reference


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", required=True)
    parser.add_argument("--path", required=True, help="Work note path relative to the vault")
    parser.add_argument("entries", nargs="*", help="Log entries in append order; omit to read stdin")
    args = parser.parse_args()

    def obsidian(command, *parameters):
        result = subprocess.run(
            ["obsidian", f"vault={args.vault}", command, *parameters],
            check=True, capture_output=True, text=True,
        )
        if result.stdout.startswith("Error:"):
            raise SystemExit(result.stdout.strip())
        return result.stdout

    source = args.entries if args.entries else [sys.stdin.read()]
    entries = [line.strip() for entry in source for line in entry.splitlines()
               if line.strip()]
    if not entries:
        parser.error("Log entries must not be empty")

    vault = Path(obsidian("vault", "info=path").strip()).resolve()
    destination = (vault / args.path).resolve()
    daily = obsidian("daily:path").strip()
    if not daily:
        parser.error("Obsidian returned no daily note path")
    daily_path = (vault / daily).resolve()
    if not all(path.is_relative_to(vault) for path in (destination, daily_path)):
        parser.error("Both notes must be inside the vault")
    note_link = destination.relative_to(vault).with_suffix("").as_posix()
    try:
        reference = append_entries(destination, entries, daily_path=daily_path,
                                   note_link=note_link)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(reference)


if __name__ == "__main__":
    main()
