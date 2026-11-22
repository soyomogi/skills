#!/usr/bin/env python3
"""Append a note's ai-log and link to the new entry in today's daily ai-log."""

import argparse
from contextlib import ExitStack, contextmanager
from datetime import datetime
import errno
import hashlib
try:
    import fcntl
except ImportError:
    fcntl = None
    import msvcrt
import os
from pathlib import Path
import re
import subprocess
import sys
import time


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


@contextmanager
def private_lock(target):
    lock_dir = Path.home() / ".obsidian-ai-log-locks"
    lock_dir.mkdir(mode=0o700, exist_ok=True)
    key = hashlib.sha256(os.fsencode(target)).hexdigest()
    with (lock_dir / key).open("a+b") as lock:
        if fcntl is not None:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield
        else:
            lock.seek(0, os.SEEK_END)
            if lock.tell() == 0:
                lock.write(b"0")
                lock.flush()
            while True:
                try:
                    lock.seek(0)
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError as error:
                    if error.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                        raise
                    time.sleep(0.05)
            try:
                yield
            finally:
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


@contextmanager
def locked_notes(paths):
    for _ in range(10):
        with ExitStack() as stack:
            notes = {}
            # Keep lock order stable, including when reopening replaced files.
            for target in sorted(paths):
                note = stack.enter_context(target.open("r+", encoding="utf-8", newline=""))
                if fcntl is None:
                    stack.enter_context(private_lock(target))
                else:
                    try:
                        fcntl.flock(note, fcntl.LOCK_EX)
                    except OSError as error:
                        if error.errno not in (errno.ENOSYS, errno.EOPNOTSUPP):
                            raise
                        stack.enter_context(private_lock(target))
                notes[target] = note
            # A path may have been replaced while either lock was pending.
            try:
                current = all(os.path.samestat(os.fstat(note.fileno()), target.stat())
                              for target, note in notes.items())
            except FileNotFoundError:
                current = False
            if current:
                yield notes
                return
    raise OSError("Notes repeatedly replaced while acquiring locks; retry the append")


def append_entries(path, entries, *, daily_path, note_link, timestamp=None):
    if timestamp is not None:
        datetime.strptime(timestamp, "%Y%m%d%H%M%S")
    path, daily_path = path.resolve(), daily_path.resolve()
    if path == daily_path:
        raise ValueError("Write log entries to a work note, not the daily note")
    with locked_notes((path, daily_path)) as notes:
        originals = {target: note.read() for target, note in notes.items()}
        text = originals[path]
        timestamp = timestamp or datetime.now().astimezone().strftime("%Y%m%d%H%M%S")
        block_id = timestamp
        used_ids = set(re.findall(r"\^([A-Za-z0-9-]+)[ \t\r]*$", text, re.MULTILINE))
        suffix = 2
        while block_id in used_ids:
            block_id = f"{timestamp}-{suffix}"
            suffix += 1
        content = f"- {timestamp} {' / '.join(entries)} ^{block_id}"
        reference = f"- [[{note_link}#^{block_id}]]"
        # Validate both sections before changing either file.
        updates = {
            path: insert_in_ai_log(text, content),
            daily_path: insert_in_ai_log(originals[daily_path], reference),
        }
        for target, original in originals.items():
            with target.open("r", encoding="utf-8", newline="") as current:
                if current.read() != original:
                    raise OSError(f"Note changed during append: {target}")
        try:
            for target, updated in updates.items():
                note = notes[target]
                note.seek(0)
                note.write(updated)
                note.truncate()
                note.flush()
        except OSError as error:
            raise OSError(
                f"Write failed; check both notes {path} and {daily_path}: {error}"
            ) from error
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
