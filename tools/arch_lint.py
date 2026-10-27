"""Architecture guardrail: fail CI when the design drifts from the governance pack.

Checks:
1. Every ADR has the required sections and cites at least one principle.
2. The Session 1 diagram shows every principle defined in the pack.
3. Every ADR referenced in docs/, diagrams/ or the README has a file in adr/,
   and every ADR in adr/ is referenced from at least one of them.
4. Every session SDD (docs/NN-sdd.md) has the course template's sections.
5. The governance pack stays within the two-page limit set by the assignment.
"""
import html
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PACK = ROOT / "docs" / "01-governance-pack.md"
DIAGRAM = ROOT / "diagrams" / "src" / "01-governance-architecture.drawio"
REQUIRED_SECTIONS = ["## Context", "## Options", "## Decision", "## Consequences", "## Revisit when"]
SDD_SECTIONS = ["Problem", "Goals and non-goals", "Assumptions", "Context viewpoint",
                "Deployment viewpoint", "Data viewpoint", "Concurrency viewpoint", "Operation viewpoint"]
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


def referencing_sources() -> list[tuple[str, str]]:
    """Every file outside adr/ that may mention an ADR: docs, diagrams and the README."""
    files = sorted((ROOT / "docs").glob("*.md")) + sorted((ROOT / "diagrams" / "src").glob("*.drawio"))
    files.append(ROOT / "README.md")
    return [(str(f.relative_to(ROOT)), html.unescape(f.read_text(encoding="utf-8"))) for f in files]


def check_consistency(adr_files: list[pathlib.Path]) -> list[str]:
    """The pack and diagram agree on principles; ADR references point at real files and back."""
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
    sources = referencing_sources()
    referenced = set()
    for name, text in sources:
        refs = set(ADR_REF.findall(text)) | set(re.findall(r"adr/(\d{4})-", text))
        referenced |= refs
        for num in sorted(refs - existing):
            problems.append(f"{name} references ADR-{num} but adr/{num}-*.md does not exist")
    for num in sorted(existing - referenced):
        problems.append(f"ADR-{num} is not referenced from docs/, diagrams/ or the README")
    return problems


def check_sdds() -> list[str]:
    """Each session SDD keeps the viewpoint structure of the course template."""
    problems = []
    for sdd in sorted((ROOT / "docs").glob("[0-9][0-9]-sdd.md")):
        headings = [line for line in sdd.read_text(encoding="utf-8").splitlines() if line.startswith("#")]
        for section in SDD_SECTIONS:
            if not any(section.lower() in h.lower() for h in headings):
                problems.append(f"{sdd.name}: no heading for '{section}'")
    return problems


def check_pack_length() -> list[str]:
    """The assignment caps the deliverable at two pages."""
    words = len(PACK.read_text(encoding="utf-8").split())
    print(f"Governance pack: {words} words (limit {MAX_PACK_WORDS})")
    return [f"governance pack is {words} words, over the {MAX_PACK_WORDS}-word limit"] if words > MAX_PACK_WORDS else []


def main() -> int:
    adr_files = sorted((ROOT / "adr").glob("[0-9][0-9][0-9][0-9]-*.md"))
    problems = check_adrs(adr_files) + check_consistency(adr_files) + check_sdds() + check_pack_length()
    for problem in problems:
        print(f"FAIL {problem}")
    print(f"Checked {len(adr_files)} ADR(s), the docs and the diagrams: {'FAILED' if problems else 'OK'}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
