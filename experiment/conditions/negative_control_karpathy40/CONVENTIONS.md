# KarparthysClaude — AI Agent Engineering Principles
# Jeder § ist ein MUTATIONSPUNKT — eine Zeile → eine neue Condition
# Quelle: karpathy/Mastering-the-Art-of-Engineering-LLMs / forrestchang/prompt-engineering-for-llms

---

## §1: Think Before You Code

**Think out loud before you touch any code.** Spend the first 30 seconds describing the bug in plain English. State your hypothesis. Describe what you expect to happen vs. what actually happens. Only then touch the code.

---

## §2: Narrow Scope

**Fix the smallest possible surface area.** If a bug is in one function, don't touch related functions. Resist the urge to "also clean up" nearby code. Discipline > completeness.

---

## §3: Verify Before Fix

**Inspect the failing test or error trace first.** Read the stack trace. Identify the exact line and variable state. If you don't understand the failure, ask clarifying questions about the expected behavior before proposing a fix.

---

## §4: Prefer Explicit Over Clever

**Write the boring solution.** Prefer obvious, explicit code over clever tricks. If a junior developer couldn't understand it in 30 seconds, rewrite it. Cleverness is a liability in production code.

---

## §5: One Hypothesis At A Time

**Isolate the cause.** When debugging, change one thing at a time. If you change three things and tests pass, you don't know which one fixed it. Systematic elimination, not shotgun debugging.

---

## §6: Minimal Diff

**The patch should be the smallest correct change.** If the tests pass with 3 lines changed, don't change 10. If you're unsure whether a change is needed, remove it and check if tests still pass.

---

## §7: Name Things Correctly

**Fix variable/function names if they mislead.** A misnamed variable is often the root cause of a bug. If renaming clarifies intent and the tests pass, include it.

---

## §8: Reproduce First

**Write a failing test that demonstrates the bug before fixing it.** If no test exists, write one. This proves the bug exists and prevents regressions. Only then write the fix.

---

## §9: Explain the Fix

**In the final message, state what changed and why.** "Changed X to Y because Z" is the minimum. If you found something surprising, document it. Future readers (including future-you) will thank you.

---

## §10: Run Tests Before Finishing

**Run the relevant test suite before declaring success.** Don't assume the fix works. Actually run `pytest` or the equivalent. If tests fail, don't hide it — report which tests fail and why you think the fix is still correct.

---

## §11: No Refactoring Unless Related

**Do not refactor unrelated code.** If you're fixing a bug and notice the formatting is ugly, leave it. A bug fix should only contain the changes necessary to fix the bug. Style fixes are a separate commit.

---

## §12: Document Workarounds

**If the fix requires a non-obvious workaround, explain why.** Some bugs don't have clean fixes. If you had to hack around a limitation, document the limitation and why this workaround was chosen.

---

## §13: Edge Cases

**Consider edge cases in the fix.** If a function handles `None`, empty string, or zero, verify your fix handles those correctly. Document if it changes existing behavior for these cases.

---

## §14: Keep Functions Focused

**If a function does two things, consider splitting it.** Single responsibility. If you're fixing a bug in a multi-purpose function, ask whether the bug is actually two bugs caused by unclear separation.

---

## §15: Error Messages Matter

**If a bug is caused by a confusing error message, improve it.** Users (and future developers) shouldn't need to decode cryptic errors. A clear error message that suggests the fix is worth more than many lines of code.

---

## §16: Read the Diff Before Submitting

**Before finalizing, read your own diff.** Does it make sense? Is every change necessary? Are there debug prints or commented-out code that should be removed? A clean diff is a professional diff.

---

## §17: Graceful Degradation

**If the ideal fix is too large, implement a partial fix.** A smaller fix that ships is better than a larger fix that never ships. Document the remaining risk.

---

## §18: Don't Suppress Warnings

**If a warning exists, understand it before silencing it.** Suppressing warnings without understanding them hides future bugs. If the warning is valid, fix the underlying issue.

---

## §19: Commit Message Discipline

**Write commit messages that stand alone.** The message should explain what changed and why, without requiring the reviewer to read the diff.

---

## §20: Review Your Own PR

**Act as your own first reviewer.** Read your change as if someone else submitted it. What questions would you ask? What would you flag? Address those before requesting review.

---

## §21: Log the Unexpected

**If the bug was caused by unexpected input, add logging.** The bug happened once, it will happen again. Structured logging at the right level helps diagnose future failures.

---

## §22: Use Types If Available

**If the codebase uses type hints, respect them.** Don't cast types to bypass the type checker. If the types are wrong, fix the types.

---

## §23: Keep Imports Clean

**Don't import modules you don't use.** An import statement that isn't referenced is dead code. Remove it. If you need it for testing only, mark it accordingly.

---

## §24: Configurable Constants

**If a magic number appears, make it a constant.** `60` seconds is unclear. `TIMEOUT_SECONDS = 60` is obvious. If a constant is used in multiple places, define it once.

---

## §25: Fail Loudly in Development

**In development, prefer loud failures over silent bugs.** An assertion that crashes early is better than a silent wrong value that propagates. In production, graceful degradation may be preferred.

---

## §26: Test the Happy Path Too

**Don't just test the failure case.** If a function handles the happy path, verify it. A fix that handles edge cases but breaks the common case is not a fix.

---

## §27: Understand the Domain

**Read related documentation before changing domain logic.** If the bug is in billing, tax calculation, or data processing, understand the domain rules. A bug fix that violates domain rules is worse than no fix.

---

## §28: Dependency Risk

**If a fix introduces a new dependency, evaluate the risk.** New dependencies bring maintenance burden, security vulnerabilities, and breaking changes. Prefer stdlib when possible.

---

## §29: API Contracts

**If you're fixing a bug in a public API, document the change.** Did the fix change behavior? Was the old behavior a bug or a feature? API changes should be intentional and documented.

---

## §30: Backwards Compatibility

**If the fix changes existing behavior, check for backwards compatibility.** Does the change break existing callers? If so, a migration path or deprecation warning is needed.

---

## §31: Security Implications

**If the bug has security implications, treat it as critical.** Information disclosure, injection vulnerabilities, and authentication bypasses require immediate attention and careful review.

---

## §32: Performance Budget

**If the fix might affect performance, consider the impact.** A simpler algorithm with worse time complexity is not always better. Know the performance budget for the function being fixed.

---

## §33: Concurrency

**If the bug involves concurrency, be extra careful.** Race conditions, deadlocks, and state corruption are hard to reproduce and debug. Add comments explaining the concurrency model.

---

## §34: Idempotency

**If the fix involves side effects, verify idempotency.** Can the operation be safely retried? If not, document it. Operations that can be retried safely are more robust.

---

## §35: observability

**If the bug is hard to reproduce, improve observability.** Add structured logging, metrics, or tracing that helps diagnose future occurrences. The next incident should be easier to debug.

---

## §36: Ownership

**If the bug is in code you don't own, collaborate.** Don't unilaterally change code you don't own. Coordinate with the owner. A fix that violates their assumptions will cause merge conflicts and regressions.

---

## §37: Test Coverage

**If the bug wasn't caught by tests, write a test.** A bug that ships is a test gap. The test should be minimal, focused, and prevent the specific regression.

---

## §38: Zero-Trust Assumptions

**Assume nothing.** The most insidious bugs come from assumptions that "this will never happen." Validate all inputs, even if you trust the caller.

---

## §39: Principle of Least Surprise

**Fixes should not surprise the user.** If the old behavior was documented, the fix should either preserve that behavior or explicitly change the documentation. Surprise = bug.

---

## §40: Simplify the Problem

**If the fix is complex, simplify first.** Complex fixes have complex failure modes. Can you reproduce the bug with a simpler input? Can you fix it with a simpler change?
