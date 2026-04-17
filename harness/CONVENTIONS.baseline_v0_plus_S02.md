# CONVENTIONS.md

## Goal
Solve the requested bug with the smallest correct change.

## Rules
1. State the bug hypothesis before editing.
2. Reproduce or inspect the failing behavior first.
3. Prefer the smallest fix that makes tests pass.
4. Do not refactor unrelated code.
5. Run the relevant tests before finalizing.
6. In the final message, state what changed and which tests passed.



## §2: Narrow Scope
**Fix the smallest possible surface area.** If a bug is in one function, don't touch related functions. Resist the urge to "also clean up" nearby code. Discipline > completeness.

---
