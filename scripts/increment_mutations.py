#!/usr/bin/env python3
"""
increment_mutations.py

Creates new convention files by adding ONE § from KarparthysClaude.md at a time
to the baseline CONVENTIONS.md. Each § becomes a new condition.

Usage:
    python scripts/increment_mutations.py --list          # show all mutations
    python scripts/increment_mutations.py --create 3     # create mutation for §3
    python scripts/increment_mutations.py --create-all   # create all mutations
"""

import argparse
import hashlib
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
KARPATHRY_FILE = BASE_DIR / "harness" / "KarparthysClaude.md"
BASELINE_FILE = BASE_DIR / "harness" / "CONVENTIONS.baseline.md"
OUTPUT_DIR = BASE_DIR / "harness"

def parse_sections(karp_path: Path) -> list[dict]:
    """Parse KarparthysClaude.md into sections with §number, title, and content."""
    content = karp_path.read_text()
    sections = []
    
    # Match ## §N: Title pattern
    pattern = re.compile(r'^## §(\d+): (.+?)$', re.MULTILINE)
    
    for m in pattern.finditer(content):
        num = int(m.group(1))
        title = m.group(2).strip()
        start = m.end()
        
        # Find next section or end
        next_m = pattern.search(content, m.end())
        end = next_m.start() if next_m else len(content)
        
        section_text = content[start:next_m.start() if next_m else len(content)].strip()
        # Remove leading/trailing markdown separators
        section_text = re.sub(r'^---\n', '', section_text).strip()
        
        sections.append({
            'num': num,
            'title': title,
            'text': section_text,
            'first_line': section_text.split('\n')[0].strip()
        })
    
    return sections

def compute_content_hash(content: str) -> str:
    """Short hash for the convention content."""
    return hashlib.md5(content.encode()).hexdigest()[:8]

def get_baseline_content() -> str:
    return BASELINE_FILE.read_text()

def create_convention_file(condition_id: str, content: str) -> Path:
    """Write a convention file to the harness directory."""
    path = OUTPUT_DIR / f"CONVENTIONS.{condition_id}.md"
    path.write_text(content)
    return path

def section_to_rule(section: dict) -> str:
    """Convert a § section into a rule string for CONVENTIONS.md format."""
    return f"§{section['num']}: {section['first_line']}"

def build_condition_name(section_num: int) -> str:
    return f"baseline_v0_plus_S{section_num:02d}"

def list_mutations():
    sections = parse_sections(KARPATHRY_FILE)
    baseline = get_baseline_content()
    baseline_hash = compute_content_hash(baseline)
    
    print(f"Baseline: {BASELINE_FILE} ({len(baseline)} chars, hash={baseline_hash})")
    print(f"KarparthysClaude: {KARPATHRY_FILE} ({len(sections)} sections)")
    print()
    print("Available mutations:")
    print("-" * 60)
    for s in sections:
        condition = build_condition_name(s['num'])
        content = baseline + f"\n{s['first_line']}\n"
        chash = compute_content_hash(content)
        existing = (OUTPUT_DIR / f"CONVENTIONS.{condition}.md").exists()
        status = "✓ exists" if existing else "  missing"
        print(f"  §{s['num']:02d} | {condition} | {status}")
        print(f"       → {s['first_line'][:70]}")
    print()
    print(f"Run: python scripts/increment_mutations.py --create N")

def create_mutation(section_num: int, dry_run: bool = False):
    sections = parse_sections(KARPATHRY_FILE)
    section = next((s for s in sections if s['num'] == section_num), None)
    
    if not section:
        print(f"ERROR: §{section_num} not found in {KARPATHRY_FILE}")
        sys.exit(1)
    
    baseline = get_baseline_content()
    condition = build_condition_name(section_num)
    
    # Build new convention content
    new_rule = f"\n## §{section['num']}: {section['title']}\n{section['text']}\n"
    new_content = baseline + "\n" + new_rule
    
    print(f"§{section_num}: {section['title']}")
    print(f"Condition: {condition}")
    print(f"Chars: {len(baseline)} → {len(new_content)}")
    print()
    print("Preview:")
    print("-" * 40)
    print(new_content[-500:])
    print("-" * 40)
    
    if dry_run:
        print("(dry run — not written)")
        return
    
    path = create_convention_file(condition, new_content)
    print(f"\nWritten: {path}")

def create_all_mutations():
    sections = parse_sections(KARPATHRY_FILE)
    baseline = get_baseline_content()
    
    for s in sections:
        condition = build_condition_name(s['num'])
        new_rule = f"\n## §{s['num']}: {s['title']}\n{s['text']}\n"
        new_content = baseline + "\n" + new_rule
        path = create_convention_file(condition, new_content)
        print(f"§{s['num']:02d} → {path.name}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Incrementally mutate CONVENTIONS.md")
    parser.add_argument("--list", action="store_true", help="List all available mutations")
    parser.add_argument("--create", type=int, metavar="N", help="Create mutation for §N")
    parser.add_argument("--create-all", action="store_true", help="Create all mutations")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    
    args = parser.parse_args()
    
    if args.list:
        list_mutations()
    elif args.create:
        create_mutation(args.create, dry_run=args.dry_run)
    elif args.create_all:
        create_all_mutations()
    else:
        parser.print_help()
