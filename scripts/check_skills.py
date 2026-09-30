#!/usr/bin/env python3
"""Offline checks for this skill repository. Exit code 1 on any failure.

  python3 scripts/check_skills.py [--allow-pending]

--allow-pending tolerates links to sibling skills in skills/ that do not exist
yet. It exists only while the skills land one PR at a time; the last skill PR
removes it from CI.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
ROOT_SKILL = SKILLS / "ios_development.md"
DOCS = [ROOT / "README.md", ROOT / "AGENTS.md", *sorted((ROOT / "docs").glob("*.md")), *sorted(SKILLS.glob("*.md"))]

LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
PRIVATE = {
    "1Password reference": re.compile(r"op://"),
    "personal macOS path": re.compile(r"/Users/(?!<)[A-Za-z0-9_.-]+/"),
    "personal Linux path": re.compile(r"/home/(?!<)[A-Za-z0-9_.-]+/"),
    "filled-in team ID": re.compile(r"DEVELOPMENT_TEAM\s*=\s*[A-Z0-9]{10}\b"),
    "UUID (profile or device id)": re.compile(r"\b[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\b"),
}
REQUIRED = {
    "metadata": re.compile(r"^#+\s+Metadata\b", re.M | re.I),
    "goal or boundaries": re.compile(r"^#+\s+.*\b(Goal|Boundaries)\b", re.M | re.I),
    "acceptance criteria": re.compile(r"^#+\s+.*\bAcceptance\b", re.M | re.I),
}


def main() -> int:
    allow_pending = "--allow-pending" in sys.argv
    errors, pending = [], []
    for doc in DOCS:
        if not doc.exists():
            continue
        text = doc.read_text()
        rel = doc.relative_to(ROOT)
        for target in LINK.findall(text):
            if re.match(r"^[a-z][a-z0-9+.-]*:", target) or target.startswith("#"):
                continue
            path = (doc.parent / target.split("#", 1)[0]).resolve()
            if not path.exists():
                if allow_pending and path.parent == SKILLS.resolve() and path.suffix == ".md":
                    pending.append(f"{rel}: pending skill {target}")
                else:
                    errors.append(f"{rel}: broken link {target}")
        for label, pattern in PRIVATE.items():
            for m in pattern.finditer(text):
                errors.append(f"{rel}: {label}: {m.group(0)}")

    skills = sorted(p for p in SKILLS.glob("*.md"))
    if skills:
        if not ROOT_SKILL.exists():
            errors.append("skills/ios_development.md (root skill) is missing")
        else:
            root_text = ROOT_SKILL.read_text()
            for s in skills:
                if s != ROOT_SKILL and f"({s.name})" not in root_text and f"(./{s.name})" not in root_text:
                    errors.append(f"root skill does not link skills/{s.name}")
        for s in skills:
            text = s.read_text()
            for label, pattern in REQUIRED.items():
                if not pattern.search(text):
                    errors.append(f"skills/{s.name}: missing {label} section")

    for p in sorted(set(pending)):
        print(f"PENDING {p}")
    for e in errors:
        print(f"FAIL {e}")
    print(f"{len(errors)} problem(s) in {sum(1 for d in DOCS if d.exists())} files, {len(skills)} skill(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
