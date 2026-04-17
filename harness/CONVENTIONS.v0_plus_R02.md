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



## R02: Minimal-Diff Discipline
**Prefer the smallest plausible change at the root cause.** If a bug traces to one function, change only that function. Do not touch neighboring code, even if it could benefit from cleanup. Fewer changed lines = fewer regression risks.
