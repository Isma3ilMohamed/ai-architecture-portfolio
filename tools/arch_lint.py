"""Architecture guardrail: fail CI when an ADR breaks the governance rules.

Every ADR must contain the required sections and cite at least one principle (P1-P4)
defined in docs/01-governance-pack.md.
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
REQUIRED_SECTIONS = ["## Context", "## Options", "## Decision", "## Consequences", "## Revisit when"]
PRINCIPLE = re.compile(r"\bP[1-4]\b")


def check_adr(path: pathlib.Path) -> list[str]:
    """Return the list of problems found in one ADR file."""
    text = path.read_text(encoding="utf-8")
    problems = []
    if "Status:" not in text:
        problems.append("missing 'Status:' line")
    problems += [f"missing section '{s}'" for s in REQUIRED_SECTIONS if s not in text]
    if not PRINCIPLE.search(text):
        problems.append("does not cite any principle (P1-P4)")
    return problems


def main() -> int:
    adrs = sorted((ROOT / "adr").glob("[0-9][0-9][0-9][0-9]-*.md"))
    failed = False
    for adr in adrs:
        for problem in check_adr(adr):
            print(f"FAIL {adr.name}: {problem}")
            failed = True
    print(f"Checked {len(adrs)} ADR(s): {'FAILED' if failed else 'OK'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
