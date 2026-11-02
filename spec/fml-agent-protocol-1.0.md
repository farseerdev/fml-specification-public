# Financial Modeling Language (FML) — Agent Authoring Protocol

## Companion Specification — Version 1.0 (Draft)

*How an automated agent writes and changes FML models*

| | |
|---|---|
| **Version** | 1.0 — draft |
| **Status** | Normative for the conformance class *FML authoring agent* (FML §2.2) |
| **Editor** | Zrinko Dolic (Farseer) |
| **Companion to** | [Financial Modeling Language (FML) Specification 1.0](fml-1.0.md) · [FML Modelling Guide 1.0](fml-modelling-guide-1.0.md) |
| **Copyright** | © 2026 Farseer d.o.o., Zagreb, Croatia |
| **License** | [Creative Commons Attribution 4.0 International (CC BY 4.0)](../LICENSE) |

This protocol is addressed to **automated agents** — language models and
programs that generate or modify FML models — and to the people who supervise
them. It turns the specification and the Modelling Guide into a procedure. An
agent that follows it produces models that are syntactically valid,
semantically correct and reviewable. References of the form "FML §n" point to
the specification, "Guide §n" to the [FML Modelling Guide](fml-modelling-guide-1.0.md).

---

## 1. What the agent needs before it starts

An agent SHOULD obtain, and MUST record as an explicit assumption whatever it
could not obtain:

1. **Purpose** — the business question the model answers, in one sentence.
2. **Outputs** — the reports, exports or downstream models that will read the
   model, and the axes each one slices by.
3. **Sources** — each data source, the grain it delivers, and its periodicity.
4. **Planning process** — who enters what, at which grain, for which versions.
5. **Existing model** — if the model exists, its full FML and member files.
   An agent MUST read an existing model before changing it and MUST reuse its
   dimensions, naming style (Guide §2.2) and conventions.
6. **Engine constraints** — the engine's limits, whether the strict member
   resolution of [EXPR-8] applies, and the linter profile in force.

## 2. Ground rules

An authoring agent:

1. **MUST** produce documents that conform to the FML Specification.
2. **MUST** qualify every member reference (`Dim > Member`) [EXPR-8].
3. **MUST NOT** write `Dim = Member` inside a formula [VAR-6].
4. **MUST NOT** reference a variable it has not declared, or that does not
   exist in the model it is modifying [DOC-1], [EXPR-6].
5. **MUST NOT** name any `Versions` member other than `Actual` in a formula
   [TIME-3].
6. **MUST** follow the agent rules of the target engine's implementation
   profile (FML Annex D) whenever the model will be loaded into that engine.
7. **MUST NOT** use an extension where a standard construct expresses the same
   thing, and **MUST** list every extension the model uses with the delivery
   [EXT-3].
8. **MUST** set `@readonly true` on every variable that is not a planner input
   [NAME-4].
9. **MUST** keep cells null where there is no data (Guide §5): no constant
   else-branches, no literal-only formulas, no defaults through `hasValue`.
10. **MUST NOT** delete a member, variable or parent of an existing model, or
    change the grain of an existing output, without explicit approval (§7).
11. **MUST** present its dimension design for confirmation before writing
    formulas, when the design is new or changes (§3, step 3).
12. **MUST** report, with every delivery, what it verified and how, what it did
    not verify, and every assumption it made (§6).
13. **MUST** declare every dimension it uses, other than a system dimension, in
    `dimensions.fml` (FML §5.4) [DOC-6], with a `@parent` for each parent
    (`many` where a member may have several) and `@null` where [DIM-5] asks
    for a NULL member. It **MUST NOT** declare a system dimension (FML §6.7).

## 3. Procedure for a new model

**Step 1 — Frame.** State the purpose, the outputs and their axes, the sources
and their grains, and the planning process (§1). List unknowns as numbered
assumptions with a proposed default for each; prefer "I assumed X — confirm or
correct" to an open question.

**Step 2 — Outputs first.** For each output, write its grain. This fixes which
dimensions must exist and be reachable.

**Step 3 — Dimension design (gate).** Design the dimensions and their parents
following Guide §3, and present them for confirmation before any formula is
written:

```text
Dimension      Members (approx.)   Level       Parents             Source of members
Account        ~400                analytic    PLLine, BSLine      ledger
PLLine         12                  synthetic   PLSection           statement layout
PLSection      5                   synthetic   —                   statement layout
Entity         8                   analytic    Currency            master data
…
```

Check the design against the checklist of Guide §3.12. Estimate the cells every
planned formula will produce [EVAL-31]. Once confirmed, write the design as
dimension declarations in `dimensions.fml`: a member source for each dimension
whose members are known (inline, or `from` a member file), a `@parent` per
parent, and `@null` on each parent whose children may be unmapped [DIM-5].

**Step 4 — Variable graph (before formulas).** Draft every variable as a row:

| Name | Class | Grain | `@type` | `@rollup` | `@format` | `@folder` | Writer → Reader |
|---|---|---|---|---|---|---|---|
| `"IMPORT GL Actual"` | import | Account, Entity, YearMonth | number | sum | — | Import | ledger integration → upstream |
| `"Revenue Plan IN"` | input | Product, Entity, Versions, YearMonth | number | sum | — | Revenue/Input | sales planners → revenue calc |
| … | | | | | | | |

Use the decision tables of §4. Trace every output back to imports and
inputs; a variable that nothing reads, or that reads nothing, is a defect.

**Step 5 — Formulas.** Write formulas block by block. For each formula, apply
the alignment checklist (Guide §4.5) and the sparsity checklist (Guide §5.6) before
moving on.

**Step 6 — Controls.** Add control chains (Guide §7.2) for every interface,
allocation, merge and identity, and a conservation invariant for every
transformation that preserves a total (Guide §7.3).

**Step 7 — Self-review.** Run the checklist of §5. Fix every finding.

**Step 8 — Validate.** Always, with or without an engine:

1. lint every document under the `strict` profile (FML §15.4) and fix every
   error and warning, or record why it stays;
2. state, for every output and control, where its cells come from — the
   references that place them [EVAL-4a] — and check that statement against
   the formula;
3. compute by hand at least one cell of every output and every control, and
   at least one cell where the result must be **null**.

Where an engine is available, also: load into a non-production environment;
read back the stored variables by value and cell count (never by evaluating
the expression alone [TEST-2]); compare against the independently computed
expectations [TEST-5]; read every control together with its positions
[TEST-1]. Without an engine, everything beyond items 1–3 is reported as
**unverified** (§6).

**Step 9 — Deliver** (§6).

## 4. Decision tables

**Class and name**

| The variable… | Class | Name | `@readonly` |
|---|---|---|---|
| receives source data from an integration | import | `"IMPORT …"` | true |
| is typed by planners | input | `"… IN"` | false |
| is the final figure a report, export or other model reads | output | `"… OUT"` | true |
| is anything else | calculation | descriptive, block prefix | true |

**`@rollup`**

| The variable is… | `@rollup` |
|---|---|
| a flow (amount per period: revenue, cost, cash movement, hires) | `sum` |
| a balance at a point in time (cash, receivable, debt, headcount, stock) | `closing_state` |
| an opening balance | `beginning_state` |
| a rate, price, percentage, ratio, FX rate | `average` |
| a ratio that must be recomputed from totals at every aggregate | Farseer extension `formula` (FML Annex D) |
| a 1-or-null presence flag used for counting | `sum` |
| a 0/1 status or routing flag | `average` |

**`@type` and display**

| Content | `@type` | Display |
|---|---|---|
| amount | `number` | default, or `@numberFormat` with `currency` |
| count of people or items (whole) | `integer` | `@decimals 0` |
| FTE, fractional headcount | `number` | `@decimals 2` |
| percentage, rate | `number` | `@format percentage` — hold the ratio, never × 100 |
| date | `date` | `@format date` |
| flag, month number | `integer` | `@decimals 0` |

**Formula shape**

| Need | Shape |
|---|---|
| value where a condition holds, nothing elsewhere | `if(c, x)` |
| one of two real values | `if(c, a, b)` — only if `b` is a variable reference [EVAL-25] |
| override when entered, calculated otherwise | `if(hasValue("X override IN"), "X override IN", "X")` |
| default where no input exists | carrier in value position (Guide §5.4), not `hasValue` |
| read a variable at one member | `sum(X, Dim > Member)` — mind [EVAL-23] |
| a value constant across a dimension | helper at a grain without that dimension [DIMD-7] |
| move data to a coarser dimension | projection through a parent [EVAL-13] |
| move a value to another member of the same dimension | transfer variable with a pinned grain [EVAL-19] |
| select rows of a class | classifier parent + `hasDMember(Class > Member)` [DIMD-14] |
| select a version | forecast flag; two-stage gate for comparisons (Guide §4.3, Guide §6) |
| actual/plan merge | two stored halves + sum [VER-4] |
| running balance | movement variable + `cumsum(movement)`, `@rollup closing_state` |
| count | 1-or-null flag + `sum` |
| all of N conditions | `eq(P1 + … + PN, N)` |

## 5. Self-review checklist

Before delivery, the agent checks every item and fixes every failure. Each item
cites the rule it enforces.

**Syntax and structure**

1. Every name that is not an identifier is quoted [LEX-1]; no control
   characters in names [LEX-3].
2. Variable names are unique across the model [DOC-1]; no dimension repeats in
   a grain [VAR-3].
3. Each defaults block heads one group of variables; read upward to the
   nearest block to see what a variable inherits — a later block replaces,
   never extends, the one before it [PROP-3].
4. Every non-system dimension is declared once, in `dimensions.fml` (FML §5.4)
   [DOC-6], and no system dimension is declared; every parent is a `@parent`
   on its child's declaration [PARENT-1]; every dimension with known members
   lists them inline or names a member file that exists [DIM-12]; every parent
   whose children may be unmapped declares `@null`, and no member source lists
   a NULL member [DIM-5].
5. Parentheses balance in every formula [EXPR-5]; subtraction before a digit
   has a space [LEX-5].

**Naming and properties**

6. Classes and names agree (Guide §1.1, Guide §2.1); one word-separator style [NAME-5].
7. `@readonly true` on every non-input [NAME-4]; `@desc` empty, `@notes`
   records writer and reader [NAME-6].
8. Balances use `closing_state` [TIME-1]; rates use `average`; percentages are
   ratios [PROP-7].
9. Every extension is listed and justified [EXT-3]; the self-review items of
   the target engine's implementation profile pass.

**Dimensions**

10. The Guide §3.12 checklist passes.
11. Every line a formula selects is reachable through a parent [DIMD-6].
12. No foreign-key column is left empty [DIMD-12].

**Formulas**

13. Every member reference is qualified [EXPR-8]; no `Dim = Member` in a
    formula [VAR-6]; no version other than `Actual` named [TIME-3].
14. No formula mixes an own-grain filter with a through-parent filter [EVAL-23].
15. Every operand is aligned or an intended broadcast (Guide §4.5); no cross-grain
    `+` whose full-grain operand may be empty [EVAL-12]; no misaligned
    product inside `sum` [EVAL-8].
16. No pinned variable reads its pinned dimension unfiltered [EVAL-18].
17. No literal-only formula; every constant output is a carrier when the
    condition names two or more variables [EVAL-4].
18. No `if(…, …, 0)` with a constant else-branch unless zero is a real value
    [FUN-3]; no default through `hasValue` (Guide §5.2).
19. No product of operands dense in different dimensions without a sparse
    carrier [SPARSE-5].
20. Every recurrence uses `cumsum` [EVAL-29].

**Controls and validation**

21. Every interface, allocation, merge and identity has a control chain
    (Guide §7.2); every total-preserving step has an invariant (Guide §7.3).
22. Validation reads stored variables, by value and cell count, against
    independent expectations [TEST-2], [TEST-5].
23. No control is reported as passing without its positions [TEST-1].

## 6. Delivery

A delivery SHOULD consist of:

1. **The documents** — FML files, `dimensions.fml`, member files — in canonical
   form (FML §5.6).
2. **A design summary** — the dimension table of step 3 and the variable table
   of step 4, as delivered.
3. **An assumption log** — every assumption, numbered, with its default.
4. **A verification report** — what was checked (lint, cell statements, hand
   calculations, engine load, reads, controls), how, and with what result;
   what was **not** checked, and why. A claim of correctness that was not
   verified MUST be labelled as unverified. Each finding is one line: the
   rule or diagnostic code, the document and line or the variable, and its
   status — *fixed*, *accepted with reason* or *open*.
5. **Open risks** — anything implementation-defined the model relies on
   (FML §2.3), every extension it uses [EXT-3], and anything that needs the
   owner's decision.

## 7. Actions that require explicit approval

An agent MUST obtain explicit approval from the model owner before:

- any action that the target engine's implementation profile lists as
  requiring approval;
- deleting a member, variable, parent or dimension of an existing model [DIM-7];
- renaming a variable or a member that reports, integrations or other models
  may read;
- changing the grain, `@type` or `@rollup` of an existing input or import, or
  the grain, type or meaning of an existing output — a grain change of a
  variable that holds entered or imported values can discard them;
- changing foreign-key data in member files of an existing model;
- overwriting entered values;
- introducing several parents per member (`@parent … many`) [DIMD-13];
- loading a model into, or writing data to, an environment in production use;
- departing from a SHOULD of the Modelling Guide without an alternative that
  satisfies its intent.

Each request for approval names the change, the variables and members it
touches and, where it can be estimated, the number of cells affected. Where no
owner can be asked, the agent does not make the change: it stops and reports
it as open (§6). The rules of the target engine's implementation profile apply
in addition to this protocol; where they are stricter, they prevail.

## 8. Modifying an existing model

1. **Read** the whole model and its member files; identify its style and
   conventions.
2. **Classify the risk**: a fix inside one block with no output change; a new
   block, output or parent; a change to an existing output's contract.
3. **Snapshot** the model and the values of its outputs before changing
   anything; the snapshot is the rollback point and the regression baseline.
4. **Analyse impact**: every variable, output, report and integration that
   reads what is changing.
5. **Change one thing per change set.** In a model in production use,
   introduce new logic as a no-op by construction [TEST-6].
6. **Compare** after the change: only intended deltas may appear.

## 9. Communicating about models

When an agent explains a design, it SHOULD use the terms of Section 3 —
variable, grain, dimension, member, parent, property, formula — and show FML
snippets rather than invent vocabulary. "The `Gross Profit` variable at grain
`{ PLAccount, Versions, YearMonth }` filters through `PLLine`, the parent of
`PLAccount`" is reviewable; "the gross-profit calculation engine module" is
not.

---

# Annexes

---

## Revision history

| Version | Date | Changes |
|---|---|---|
| 1.0 | (draft) | First version. |
