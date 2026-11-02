# Instructions for AI agents

You are about to write or modify a model in the **Financial Modeling Language
(FML)**. The language is specified in [`spec/fml-1.0.md`](spec/fml-1.0.md); the
protocol you follow is [`spec/fml-agent-protocol-1.0.md`](spec/fml-agent-protocol-1.0.md);
the practices behind it are in [`spec/fml-modelling-guide-1.0.md`](spec/fml-modelling-guide-1.0.md).
This file tells you how to use them.

## Read first, in this order

1. **Specification §3** — the vocabulary: variable, grain, dimension, member,
   parent, property, formula, null, carrier.
2. **Specification §11** — evaluation semantics. Most defects in FML models are
   explained by one of its rules. Read all of it.
3. **The Agent Protocol** — the procedure you follow: decision tables,
   self-review checklist, delivery format.
4. **Modelling Guide §3** — dimension design, before you design any dimension.

Use the rest of the document as reference. Rules are cited by identifier, for
example `[EVAL-23]`; anti-patterns by `AP-nn`; diagnostics by `FML-Xnnnn`.

## Non-negotiable rules (summary of Protocol §2)

- Qualify every member reference: `Quarters > Q1`, never `Q1` alone.
- Never write `Dim = Member` inside a formula; pins belong in the grain only.
- Never name a `Versions` member other than `Actual` in a formula; route
  versions with forecast flags (Guide §6).
- Write standard FML. Use an engine extension only when the model targets that
  engine and no standard construct expresses the same thing, and list it.
  When the target is Farseer, follow Section 9 of the
  [Farseer Implementation Profile](spec/fml-farseer-profile-1.0.md) — among
  others: never set `@calculateOnDemand true` yourself. You may propose it, with its
  risks stated, and apply it only on the model owner's explicit request.
- Every variable that is not a planner input (` IN`) is `@readonly true`.
- Keep cells null where there is no data: two-argument `if`, no constant
  else-branches, no literal-only formulas, no defaults through `hasValue`.
- Do not mix an own-grain filter with a through-parent filter in one formula
  [EVAL-23]; make every line a formula selects a member reachable through a
  parent [DIMD-6].
- Align operand grains or project first [EVAL-12]; never add operands at
  different grains.
- Present your dimension design for confirmation before writing formulas.
- Do not delete members, variables or parents, or change an output's grain,
  without explicit approval.
- Report what you verified, how, and what you did not verify.

## Before you deliver

Run the self-review checklist of Protocol §5 item by item. A control reading zero is
not evidence on its own [TEST-1]; verify stored variables by value and cell
count against independently computed expectations [TEST-2], [TEST-5].

## Translating a model to Excel

Follow [`spec/fml-excel-1.0.md`](spec/fml-excel-1.0.md), Section 15. A
workbook reconstructs values, not engine behaviour; never approximate a formula
silently — list it on the `Notes` sheet.

## Worked example

[`examples/three-statement/`](examples/three-statement/) is a complete model
(P&L, balance sheet, cash, controls, member files) that follows every rule
above. Reproduce its structure; do not copy its business assumptions.
