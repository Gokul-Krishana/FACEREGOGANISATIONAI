"""Regenerate the master SDD document with a clean header, TOC, and sections."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SDD = ROOT / "docs" / "sdd"
MASTER = ROOT / "docs" / "PROJECT_DOCUMENTATION.md"

section_files = sorted([f for f in os.listdir(SDD) if f[0].isdigit() and f.endswith(".md")])


def title_from_name(name: str) -> str:
    body = name[3:-3].replace("_", " ")
    return body[:1].upper() + body[1:]


out = []
out.append("# FaceRecognitionAI — Complete Software Design Document (Master)")
out.append("")
out.append("> Single-file edition of the 30-section Software Design Document (SDD).")
out.append("> Per-section files live in `docs/sdd/`. Generated directly from the")
out.append("> repository source code — every statement is grounded in the actual")
out.append("> implementation.")
out.append("")
out.append("## Table of Contents")
out.append("")
out.append("| # | Section | File |")
out.append("|---|---------|------|")
for f in section_files:
    n = int(f[:2])
    out.append(f"| {n} | {title_from_name(f)} | [docs/sdd/{f}](docs/sdd/{f}) |")
out.append("")
out.append("---")
out.append("")

for f in section_files:
    text = (SDD / f).read_text(encoding="utf-8").rstrip()
    out.append(f"<!-- Section: {f} -->")
    out.append(text)
    out.append("")
    out.append("---")
    out.append("")

MASTER.write_text("\n".join(out) + "\n", encoding="utf-8")

lines = MASTER.read_text(encoding="utf-8").count("\n")
size = MASTER.stat().st_size
print(f"OK: {MASTER} — {len(section_files)} sections, {lines} lines, {size} bytes")
