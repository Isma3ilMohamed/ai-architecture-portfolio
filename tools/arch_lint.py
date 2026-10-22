"""Architecture guardrail: fail CI when the design drifts from the governance pack.

Checks:
1. Every ADR has the required sections and cites at least one principle.
2. The diagram and the pack agree: every principle in the pack appears in the
   diagram, and every ADR referenced anywhere has a file in adr/.
3. The governance pack stays within the two-page limit set by the assignment.
"""
import html
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PACK = ROOT / "docs" / "01-governance-pack.md"
DIAGRAM = ROOT / "diagrams" / "src" / "01-governance-architecture.drawio"
REQUIRED_SECTIONS = ["## Context", "## Options", "## Decision", "## Consequences", "## Revisit when"]
PRINCIPLE_REF = re.compile(r"\bP[1-9]\b")
PRINCIPLE_DEF = re.compile(r"^\| \*\*(P[1-9])\*\* \|", re.MULTILINE)
ADR_REF = re.compile(r"\bADR-(\d{4})\b")
MAX_PACK_WORDS = 1300  # roughly two printed pages including tables


def check_adrs(adr_files: list[pathlib.Path]) -> list[str]:
    """Each ADR needs a status line, the required sections and a principle reference."""
    problems = []
    for adr in adr_files:
        text = adr.read_text(encoding="utf-8")
        if "Status:" not in text:
            problems.append(f"{adr.name}: missing 'Status:' line")
        problems += [f"{adr.name}: missing section '{s}'" for s in REQUIRED_SECTIONS if s not in text]
        if not PRINCIPLE_REF.search(text):
            problems.append(f"{adr.name}: does not cite any principle")
    return problems


def check_consistency(adr_files: list[pathlib.Path]) -> list[str]:
    """The pack, the diagram and adr/ must reference the same principles and decisions."""
    pack = PACK.read_text(encoding="utf-8")
    diagram = html.unescape(DIAGRAM.read_text(encoding="utf-8"))
    problems = []

    principles = sorted(set(PRINCIPLE_DEF.findall(pack)))
    if not principles:
        problems.append("governance pack defines no principles")
    for p in principles:
        if not re.search(rf"\b{p}\b", diagram):
            problems.append(f"principle {p} is defined in the pack but not shown in the diagram")

    existing = {f.name[:4] for f in adr_files}
    for source, text in (("diagram", diagram), ("pack", pack)):
        for num in sorted(set(ADR_REF.findall(text))):
            if num not in existing:
                problems.append(f"{source} references ADR-{num} but adr/{num}-*.md does not exist")
    for num in sorted(existing):
        if f"ADR-{num}" not in diagram and f"{num}" not in pack:
            problems.append(f"ADR-{num} is not referenced by the pack or the diagram")
    return problems


def check_pack_length() -> list[str]:
    """The assignment caps the deliverable at two pages."""
    words = len(PACK.read_text(encoding="utf-8").split())
    print(f"Governance pack: {words} words (limit {MAX_PACK_WORDS})")
    return [f"governance pack is {words} words, over the {MAX_PACK_WORDS}-word limit"] if words > MAX_PACK_WORDS else []


def main() -> int:
    adr_files = sorted((ROOT / "adr").glob("[0-9][0-9][0-9][0-9]-*.md"))
    problems = check_adrs(adr_files) + check_consistency(adr_files) + check_pack_length()
    for problem in problems:
        print(f"FAIL {problem}")
    print(f"Checked {len(adr_files)} ADR(s), the pack and the diagram: {'FAILED' if problems else 'OK'}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
