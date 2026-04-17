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



## R03: Root-Cause Before Edit
**Before the first patch, explicitly name the affected class and function.** State which file, class, and method contains the root cause — then edit only there. Do not edit a file unless you have named it as the root-cause location.
