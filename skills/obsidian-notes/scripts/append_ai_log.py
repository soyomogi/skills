#!/usr/bin/env python3
"""Append timestamped entries to an existing note's ai-log section."""

import argparse
from datetime import datetime
import fcntl
from pathlib import Path
import re
import subprocess
import sys


def append_entries(path, entries, *, timestamp=None):
    if timestamp is not None:
        datetime.strptime(timestamp, "%Y%m%d%H%M%S")
    with path.open("r+", encoding="utf-8", newline="") as note:
        fcntl.flock(note, fcntl.LOCK_EX)
        text = note.read()
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
        timestamp = timestamp or datetime.now().astimezone().strftime("%Y%m%d%H%M%S")
        block_id = timestamp
        used_ids = set(re.findall(r"\^([A-Za-z0-9-]+)[ \t]*$", text, re.MULTILINE))
        suffix = 2
        while block_id in used_ids:
            block_id = f"{timestamp}-{suffix}"
            suffix += 1
        content = f"- {timestamp} {' / '.join(entries)} ^{block_id}"
        separator = "" if text[:end].endswith("\n") else newline
        note.seek(0)
        note.write(text[:end] + separator + content + newline + text[end:])
        note.truncate()
        return block_id


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", required=True)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--path", help="Note path relative to the vault")
    target.add_argument("--daily", action="store_true")
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
    path = obsidian("daily:path").strip() if args.daily else args.path
    destination = (vault / path).resolve()
    if not destination.is_relative_to(vault):
        parser.error("The note must be inside the vault")
    try:
        block_id = append_entries(destination, entries)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"![[{Path(path).with_suffix('').as_posix()}#^{block_id}]]")


if __name__ == "__main__":
    main()
