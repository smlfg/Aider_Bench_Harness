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



## §3: Verify Before Fix
**Inspect the failing test or error trace first.** Read the stack trace. Identify the exact line and variable state. If you don't understand the failure, ask clarifying questions about the expected behavior before proposing a fix.

---
