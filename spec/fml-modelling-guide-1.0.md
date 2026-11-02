# Financial Modeling Language (FML) — Modelling Guide

## Companion Document — Version 1.0 (Draft)

*How to build FML models that are correct, fast and maintainable*

| | |
|---|---|
| **Version** | 1.0 — draft |
| **Status** | Informative. Recommended practice; defines nothing a conforming FML document must use |
| **Editor** | Zrinko Dolic (Farseer) |
| **Companion to** | [Financial Modeling Language (FML) Specification 1.0](fml-1.0.md) |
| **Copyright** | © 2026 Farseer d.o.o., Zagreb, Croatia |
| **License** | [Creative Commons Attribution 4.0 International (CC BY 4.0)](../LICENSE) |

The FML Specification says what a model *means*. This guide says how to build
one that is correct, fast and maintainable. Its practices come from planning
models — consolidation, three-statement, workforce, sales and distribution.
References of the form "FML §n" point to the specification; "Protocol §n" to the
[FML Agent Authoring Protocol](fml-agent-protocol-1.0.md).

**Status of the rules.** The guide is informative. Its rules carry identifiers
(for example **[GRAIN-1]**) so that reviews and tools can cite them, and the key
words MUST, SHOULD and MAY state the strength of a recommendation. Rules that
can be checked statically have a diagnostic in FML Annex C; a linter reports
them under the profiles of FML §15.4, and an authoring agent follows them
(Protocol §2).

---

## 1. Model architecture

### 1.1 Four variable classes

Every variable belongs to exactly one **class**. The class decides who writes
the variable, whether it may be edited, and how it is named.

| Class | Written by | Formula | `@readonly` | Name (§2) |
|---|---|---|---|---|
| **Import** | integrations only | never | `true` | `IMPORT` prefix |
| **Input** | planners, through input forms | none (exceptions, §1.4) | `false` | ` IN` suffix |
| **Calculation** | the engine | always | `true` | no marker |
| **Output** | the engine; read by reports, other models, exports | always | `true` | ` OUT` suffix |

**[ARCH-1]** Integrations write only import variables; planners write only input
variables; reports read only output variables (and controls). Everything in
between is formula-only and read-only.

```text
IMPORT  ──►  IN (planner)  ──►  CALCULATION  ──►  OUT (to the business)
landing      inputs and         read-only chain    final, read-only
read-only    assumptions
```

### 1.2 The layered pipeline

Larger models extend the four classes into layers. A typical operational model:

| Layer | Purpose |
|---|---|
| 1 · Import | facts at source grain, without `Versions`, semantics resolved before landing |
| 2 · Leveling | source grain → planning grain (`upstream` feeders), still without `Versions` |
| 3 · Plan | driver inputs in natural units: quantities, prices, rates, headcount |
| 4 · Submodels | allocations, rebates, working capital, workforce, depreciation |
| 5 · Merge | actuals and plan meet in the outputs through the forecast gate (§6) |
| 6 · Controls and reports | checks ending in a final flag; statements; bridges |

Layers are joined by ordinary references; the engine orders evaluation, so the
layering is a reading order, not an execution order [DOC-2].

### 1.3 Files, folders and names agree

**[ARCH-2]** One document SHOULD hold one functional block, the variables of a
block SHOULD share one top-level `@folder`, and their names SHOULD share the
block's prefix (§2.3). The document is where a modeler edits a variable, the
folder is where a user finds it, and the name is its identity; keeping the
three aligned makes the model read top to bottom like its pipeline.

```text
model/
  dimensions.fml       every dimension declaration, nowhere else
  foundation.fml       forecast flags and shared switches
  import.fml           the import layer
  revenue.fml          one document per block …
  workforce.fml
  statements.fml
  controls.fml
  dimensions/<Dimension>.csv
```

Defaults blocks (FML §9.2) remove repetition within a document, one block per
group of variables:

```fml
@defaults
  @folder "Import"
  @readonly true

"IMPORT Sales Volume" { Item, Customer, YearMonth }
"IMPORT GL Actual"    { Account, CostCenter, YearMonth }

@defaults
  @folder "Revenue/Inputs"

"Volume IN" { Item, Customer, Versions, YearMonth }    # entry, not read-only
```

### 1.4 Inputs carry no plan formula

**[ARCH-3]** A variable is either an input or an output, never both. An input
variable SHOULD NOT have a formula. One exception is permitted, and an
implementation profile may permit others (Farseer's: growth functions, Annex
D): a **fenced seed** — a formula that writes only into cells the planner does not own,
typically the actual periods, so that the input shows actuals for history and
accepts planner entries for the plan. A fenced seed relies on entered values in
a calculated variable [VAR-8] and is portable only to engines that support
them (FML §8.5):

```fml
"Unit Price IN" { Product, Versions, YearMonth } =
  if(eq("FC Actual Flag", 1), "Unit Price upstream")
  @notes "Planner owns plan periods; actual periods show realised prices."
```

An unfenced formula on an input (`"X IN" = "IMPORT X"`) makes every cell
computed while the name tells tools and people that the cells belong to the
planner; it SHOULD be renamed to a calculation. Any other formula on an input
MUST be justified in `@notes`.

### 1.5 Overrides

**[ARCH-4]** A calculated value that a planner must be able to correct SHOULD
NOT be made writable. Add a formula-free override input at the **same grain**
and combine:

```fml
"IMPORT Headcount"            { CostCenter, YearMonth }   # landing
  @rollup closing_state
  @readonly true
"Headcount Adjustment IN"        { CostCenter, YearMonth }   # planner correction
  @rollup closing_state
"Headcount adjusted"   { CostCenter, YearMonth } = "IMPORT Headcount" + "Headcount Adjustment IN"
  @rollup closing_state
  @readonly true

"Allocation Factor effective" { CostCenter, Years } =
  if(hasValue("Allocation Factor override IN"), "Allocation Factor override IN", "Allocation Factor")
  @readonly true
```

Consumers read the adjusted or effective variable; the source remains as an
audit trail. The additive form needs no `hasValue` guard [EVAL-11] because the
three variables share one grain.

### 1.6 Delivery

**[ARCH-5]** A layer is complete only when it has (1) the FML that computes it,
(2) an input or report surface that exposes it, and (3) a test — a known input
with a known output, plus a conservation invariant where one applies (§7).

---

## 2. Naming conventions

From a variable's name alone, a reader — person or agent — should be able to
tell who writes it, whether it may be edited, and whether anything outside the
model depends on it.

The role markers of this section — `IMPORT`, ` IN`, ` OUT` — and the folder
`Import` are the RECOMMENDED spelling. A model MAY use other markers for the
same roles, provided it uses them consistently and records them with the
model; the rules below then apply to the markers it chose.

### 2.1 Core rules

**[NAME-1] Import prefix.** A variable written by an integration SHOULD carry
the prefix `IMPORT` and live in the `Import` folder. `IMPORT` is reserved for
direct landing targets: a variable that aggregates or reshapes an import is a
calculation and MUST NOT carry the prefix.

```fml
# Wrong — looks like a landing target but is a formula
"IMPORT Balance by Line" { BSLine, YearMonth } = "IMPORT GL Balance"
  @readonly true

# Right
"Balance Actual upstream" { BSLine, YearMonth } = "IMPORT GL Balance"
  @folder "Import/Upstream"
  @readonly true
```

**[NAME-2] Input suffix.** A planner-writable variable SHOULD end in the suffix
` IN` — a space followed by `IN` — and is therefore written in string form:
`"Sales Volume IN"`. The suffix is the last token of the name:
`"Bonus Override IN"`, not `"Bonus IN Override"`.

**[NAME-3] Output suffix.** A variable the model publishes — read by a report,
a dashboard, another model or an export — SHOULD end in ` OUT`:
`"Net Revenue OUT"`. ` OUT` marks this contract with the outside; variables of
the model MAY read an output too, but a step that exists only to compute
another variable MUST NOT carry it. A model typically has a handful to a few
dozen outputs.

**[NAME-4] Read-only rule.** Every variable whose name does not end in ` IN`
SHOULD be `@readonly true` [PROP-8].

### 2.2 Word-separator style

A model uses one of two styles for multi-word names, consistently:

| Style A — spaces, quoted (RECOMMENDED) | Style B — underscores, unquoted |
|---|---|
| `"Gross Base Salary IN"` | `Gross_Base_Salary_IN` |
| `"IMPORT GL Balance"` | `IMPORT_GL_Balance` |
| `"Net Revenue OUT"` | `Net_Revenue_OUT` |
| `@folder "Workforce/Pay"` | `@folder "Workforce/Pay"` |

**[NAME-5]** A model MUST NOT mix the two styles in variable names
(`"Closing_Balance OUT"` mixes them). When extending an existing model, match
its style. In Style B the role markers are spelled `IMPORT_`, `_IN` and
`_OUT`.

Dimension names SHOULD be single words in PascalCase (`CostCenter`,
`PayGrade`, `PLLine`), which read the same in either style. This
specification uses Style A for variables throughout.

### 2.3 Functional prefixes (recommended)

A short prefix naming the block keeps names sortable and lets a reader predict
a variable's folder:

| Prefix | Block |
|---|---|
| `PL` | profit and loss |
| `BS` | balance sheet |
| `CF` | cash flow |
| `HR` | workforce |
| `FC` | forecast and version routing |
| `ASS` / `ASSG` | assumptions / assumptions by grade |
| `CHECK` | controls |
| `XP` | disposable experiments, deleted after use |

Descriptive markers inside names are lowercase (`upstream`, `effective`,
`override`, `base`); role markers are uppercase (`IMPORT`, `IN`, `OUT`,
`ADJUSTMENT`, `CHECK`, `FINAL`).

| Marker | Meaning |
|---|---|
| `… upstream` | a feeder that sends data from the import layer towards an output |
| `… collector` | a destination that gathers several sources |
| `… at <grain>` | a projection to that grain (§4.4) — for example `"PL Plan at PLLine"` |
| `… effective` | an input or calculation after overrides are applied |
| `CHECK <area> A`, `… B`, `… FINAL` | a control chain (§7) |

### 2.4 Text properties

**[NAME-6]** Prose describing a variable belongs in `@notes`; `@desc` SHOULD be
left empty on variables [PROP-11]. `@notes` SHOULD record the variable's class,
**who writes it** (an integration, an input form, a person) and **who reads it**
(a report, an export, another variable). A note that restates the name is worse
than none.

A **member's** description is different: it is the member's display label and
SHOULD be filled.

### 2.5 Dimensions, members and coded taxonomies

- **Dimension names** state business meaning, singular, PascalCase:
  `CostCenter`, `Position`, `PayGrade`. They SHOULD NOT encode maintenance
  cadence or technical role (`S_Products`, `D_Customers`, `F_Market`).
- **Hierarchy levels** are named for the level: `CostCenterL1` … `CostCenterL4`,
  or `Account`, `PLLine`, `PLSection`.
- **Member names** are stable codes (`4000`, `CC100`, `EL101`); labels go in
  the description column.
- **Coded taxonomies** (salary elements, cost elements) are numbered in
  semantic blocks, with gaps for growth — `EL1xx` recurring pay, `EL2xx`
  employer contributions, `EL3xx` one-off payments, `EL5xx` cost-centre items.
  The code is the member name; reclassifying a member changes its classifier
  parent, never its code.
- **No market, country or personal markers** in variable names
  (`"Base Salary Market A"`, `"Bonus JS"`). Variation by market belongs in data
  (§3.9).

---

## 3. Dimension design

Dimension design is the most consequential decision in a model. Formulas can
be rewritten in an afternoon; a dimension structure is load-bearing for every
variable, every report and every integration. This section collects the rules
for choosing dimensions and composing them into a graph.

### 3.1 The governing principle: distinctions live in dimensions

**[DIMD-1]** A business distinction that drills, aggregates or changes over
time SHOULD be represented as a **dimension or a mapping in a dimension
table**, not as a member name written in a formula, and not as a separate
variable per case.

Compare two ways of computing gross profit when cost-of-sales accounts must be
identified:

```fml
# Distinction in a formula: a member name hard-coded per line
"Gross Profit" { Account, Versions, YearMonth } =
    sum("PL Amount", PLLine > Revenue) - sum("PL Amount", Account > "5000")
  @readonly true

# Distinction in a dimension: the account's role is data
dimension Account from "dimensions/Account.csv"
  @parent PLLine                      # 5000 maps to PLLine "Cost of sales"
"Gross Profit" { Account, Versions, YearMonth } =
    sum("PL Amount", PLLine > Revenue) - sum("PL Amount", PLLine > "Cost of sales")
  @readonly true
```

In the second form, a new cost-of-sales account is one foreign-key value, not a
formula edit; reports drill by the distinction; and the formula is correct by
[EVAL-23] (both terms filter through a parent). The first form is also wrong:
`Account > "5000"` filters the variable's own grain and broadcasts (§3.4).

The same principle yields these consequences:

- a new entity, market or product line is a **new member**, not a model change;
- a classification that varies by market or year is a **data grid**
  (`"Element In Base IN" { SalaryElement, Market, Years }`), not a nested
  `if` over member names;
- a hierarchy is a **parent**, not a sum of named members.

### 3.2 Choosing the dimensions

Work from the outputs backwards.

1. **List the reports** and the axes they slice by. Every axis a report
   drills by must be reachable from the output variables' grains.
2. **List the sources** and the grain at which each delivers data. Actuals
   are landed at their natural grain (§1.2).
3. **Choose the planning grain** — the coarsest grain at which the business
   actually plans. Plan quantities live there; finer detail is reached by
   allocation, not by planning every leaf (§8).
4. **Identify the conformed dimensions** that plan and actuals share; these are
   where variance is computed by a single subtraction.
5. **Hang every attribute off the dimension it describes** with a parent,
   rather than adding it to variable grains (§3.5).

**[DIMD-2]** Each dimension SHOULD represent one business object. One dimension
per site, region or company with identical members and parents is a defect:
opening a site should add a member, not a dimension.

**[DIMD-3]** Dimensions with very many members (employees, contracts,
customers × items) SHOULD appear only in the grains that need them. What
costs is the number of cells a formula **produces** [EVAL-31] — an operand's
cells times every member it is expanded over, including `Versions` and
the time dimension — not the size of the grain.

### 3.3 Analytic and synthetic levels

Financial models almost always have two levels of the same classification:

| Level | Example | Role |
|---|---|---|
| **analytic** | chart of accounts, cost centre, salary element, SKU | the grain at which data is held and imported |
| **synthetic** | statement line, reporting group, element class, category | the grain at which it is reported and at which formulas select |

**[DIMD-4]** Data SHOULD be held at the analytic level, with each synthetic
level declared as its parent (`@parent`, one parent member per member).
Formulas that select a class of rows SHOULD filter on the synthetic level —
through the parent — not on analytic member names.

```fml
dimension Account from "dimensions/Account.csv"
  @parent PLLine
  @parent BSLine
dimension PLLine from "dimensions/PLLine.csv"
  @parent PLSection

"PL Amount" { Account, Entity, Versions, YearMonth }
"Operating Expenses" { Account, Entity, Versions, YearMonth } =
    sum("PL Amount", PLSection > "Operating expenses")
  @readonly true
```

**[DIMD-5]** Several entities with their own charts of accounts SHOULD each
keep their local chart as analytic data, with one shared, entity-neutral
reporting dimension as its parent. Group reporting then reads the shared
dimension; local detail remains drillable.

### 3.4 Make the synthetic level as fine as the statement

The interaction of filters with the evaluation context [EVAL-23] dictates a
structural rule.

**[DIMD-6]** If a formula needs to select a line, that line SHOULD be a member
of a dimension that the formula's operands reach **through a parent**. A
formula that selects rows by filtering on its **own** grain dimension, while
other terms of the same formula filter through a parent, is wrong by an exact multiple
(AP-01).

The defect almost always appears because a line that a subtotal needs is
buried inside a coarse synthetic member. Suppose cost of sales and depreciation
both sit inside one synthetic member `Operating expenses`. No parent can reach
either alone, so a modeler filters the analytic level instead:

```fml
# DEFECTIVE — mixes a through-parent term with an own-grain term
"Gross Profit" { PLAccount, Versions, YearMonth } =
    sum("PL Amount", PLLine > "Operating revenue")       # through the parent: this cell's slice
  - sum("PL Amount", PLAccount > "Cost of sales")        # own grain: the full total, on every cell
  @readonly true
# → cost of sales is subtracted once for every account the first term reaches
```

The fix is to make the synthetic level reflect the actual statement:

```fml
# PLLine, flat: Operating revenue · Cost of sales · Other operating expenses ·
#               Depreciation and amortisation · Financial income ·
#               Financial expense · Income tax · NULL (PLLine)
dimension PLLine from "dimensions/PLLine.csv"
  @null
dimension PLAccount from "dimensions/PLAccount.csv"
  @parent PLLine

"Gross Profit" { PLAccount, Versions, YearMonth } =
    sum("PL Amount", PLLine > "Operating revenue")
  - sum("PL Amount", PLLine > "Cost of sales")
  @readonly true

"EBITDA" { PLAccount, Versions, YearMonth } =
    sum("PL Amount", PLLine > "Operating revenue")
  - sum("PL Amount", PLLine > "Cost of sales")
  - sum("PL Amount", PLLine > "Other operating expenses")
  @readonly true
```

Beyond correctness, a correction step disappears: EBITDA no longer has to *add
depreciation back*, because depreciation was never subtracted. **A formula that
has to undo something is usually a sign that the dimension underneath it is
coarser than the statement it describes.**

When the synthetic level cannot be split — it is fixed by a statutory layout or
a source system — add a small, flat **role dimension** that isolates the line,
and make it a parent of the analytic level:

```fml
dimension MarginRole { COGS, DandA, Other }
  @null
dimension PLAccount from "dimensions/PLAccount.csv"
  @parent PLLine
  @parent MarginRole

"Gross Profit" { PLAccount, Versions, YearMonth } =
    sum("PL Amount", PLLine > "Operating revenue")
  - sum("PL Amount", MarginRole > COGS)
  @readonly true
```

The role dimension is the second choice: it adds a table to carry what the
statement's own structure would otherwise carry.

**[DIMD-7]** A value that must be **the same in every cell** — a denominator,
a scaling factor — is a legitimate broadcast. It SHOULD be stated as a helper
variable at a grain that does **not** carry the dimension it is constant
across, and consumed from there:

```fml
"Operating Revenue Total" { Versions, YearMonth } = sum("PL Amount", PLLine > "Operating revenue")
  @readonly true
"Share of Revenue"        { PLAccount, Versions, YearMonth } =
  if(gt("Operating Revenue Total", 0), "PL Amount" / "Operating Revenue Total")
  @readonly true
```

Writing the denominator inline as `sum("PL Amount", PLLine > "Operating
revenue")` at `PLAccount` grain would be wrong: `PLLine` is reached through a
parent, so the filter intersects [EVAL-23] and each revenue account would be
divided by itself. An own-grain filter (`sum("PL Amount", PLAccount > "4000")`)
does broadcast, but the helper states the intent explicitly.

### 3.5 Attributes hang off the object they describe

**[DIMD-8]** An attribute of a business object — a position's cost centre, a
customer's sales representative, an employee's grade — SHOULD be a parent of
the object's dimension: `@parent` on the object's declaration names the
attribute's dimension. It SHOULD NOT be added to
the grains of the variables that hold the object's data.

```fml
dimension Position
  @parent CostCenter
  @parent JobCode
dimension JobCode from "dimensions/JobCode.csv"
  @parent PayGrade
dimension CostCenter from "dimensions/CostCenter.csv"
  @parent Entity

# Right — minimal grain; every attribute is a free projection
"Base Pay" { Position, Versions, YearMonth } = "Base Salary IN" * "FTE"
  @readonly true

# Wrong — the attribute is in the grain: moving a position means rewriting data
# "Base Pay" { Position, CostCenter, Versions, YearMonth }
```

Aggregation to `CostCenter`, `Entity`, `PayGrade` follows by projection
[EVAL-13], and moving a position to another cost centre is one foreign-key
change.

**[DIMD-9]** An attribute that **changes over time** (a cost-centre move from
month N, a grade change) cannot be a parent, because a foreign key has no time
axis. Model it as a time-phased input keyed on both dimensions — for example
`"Allocation Weight IN" { Employee, CostCenter, Versions, YearMonth }` — and
resolve it where cost is finally attributed (§9.7).

### 3.6 Flat levels versus trees

| | Levels as separate dimensions | Tree |
|---|---|---|
| shape | `Account -> PLLine -> PLSection` | `OrgUnit` with `@parent OrgUnit` |
| depth | fixed | arbitrary, may be ragged |
| rollup nodes | none — every member is a leaf of its level | parents are members and can hold cells |
| formula behaviour | predictable | calculated variables may hold a cell at a parent [EVAL-16], and `sum(X, D > m)` includes it [EVAL-22] |

**[DIMD-10]** Dimensions that formulas **select on** (statement lines, roles,
classes) SHOULD be flat. A tree SHOULD NOT appear in the grain of a calculated
variable: keep variables on a flat analytic dimension that has the tree as its
parent, and let the tree serve navigation and reporting (balance-sheet
groupings, organisation charts). Where a tree must be in a grain, calculated
variables over it SHOULD be gated so that no cell is created at a rollup node:

```fml
"Allocated Overhead" { OrgUnit, Versions, YearMonth } =
  if(hasDMember(OrgUnitType > Leaf), "Overhead Pool" * "Allocation Key")
  @readonly true
```

If a rollup node is not supposed to contribute, give it nothing to contribute
*with*; subtracting the node afterwards breaks as soon as the tree changes.

### 3.7 The dimension graph

**[DIMD-11]** Parents SHOULD form a forest of single-parent paths (no `many`)
from analytic levels to synthetic levels and attributes. In particular:

- **No sister parents.** If `Employee` and `CostCenter` are both reached
  from `Position`, do not also give `Employee` the parent `CostCenter`. A graph
  in which one of two dimensions reachable from a third is also a parent of the
  other makes aggregation ambiguous when they are combined in one grain
  (`FML-W0704`), and an engine MAY reject such a grain [VAR-3a].
- **No diamonds** — two distinct paths between the same pair of dimensions
  (FML §7.5) — unless every path is known to aggregate identically.
- **No ancestor in the grain.** A dimension and a dimension reachable from it
  do not belong in the same grain [VAR-3a].
- **Clone dimensions.** When an input genuinely needs a dimension together
  with its own ancestor — an allocation to a *target* cost centre where the
  home cost centre is derived from the position — create a standalone clone
  (`CostCenterTarget`) with the same member names and **no parent back** to the
  original; relate the two by name where values are finally attributed.
- **Conformed star.** Sister dimensions reached from one object, with no parents
  among them, are safe in one grain [VAR-3a].
- **Reclassification bridges.** To map an actual attribute onto a planned one
  (an actual job code onto a planned job code), add a parallel parent
  (`@parent JobCode` on `JobCodeActual`), never carry both in one grain.
- **Code books.** When source codes map to model members (pay codes to salary
  elements, local accounts to group accounts), the mapping is a parent: the
  code-book dimension declares the target dimension with `@parent`, and its
  column is regenerated from the agreed mapping. Imports land on the code; the
  projection does the rest:

  ```fml
  dimension PayCode from "dimensions/PayCode.csv"
    @parent SalaryElement
  "Payroll by Element upstream" { Employee, SalaryElement, YearMonth } = "IMPORT Payroll by PayCode"
    @readonly true
  ```

**[DIMD-12]** A parent and its data MUST be introduced together. A parent whose
foreign-key column is empty routes nothing [PARENT-3]; a model between the two
changes reads null wherever data passes through the parent. When a parent is
added for existing members, populate every member — with the NULL member where
the parent is unknown.

**[DIMD-13]** Several parents (`@parent … many`) [PARENT-2] SHOULD be used
only where a child genuinely belongs to several parents in the same view. Each
parent then includes the child's full value; reports that add the parents
double-count.

### 3.8 Classifier dimensions and positive tests

A **classifier dimension** is a small, flat dimension whose members name a
class of rows: `ContributionClass` (`Liable`, `Exempt`), `CFEntryType`
(`Walk line`, `Opening`, `Closing`), `ElementClass` (`Fixed`, `Variable`,
`Contribution`, `One-off`). Rows are assigned to a class by a parent.

**[DIMD-14]** "Which rows does this formula apply to?" SHOULD be answered by a
classifier dimension and a **positive** test for the class that should compute:

```fml
dimension SalaryElement from "dimensions/SalaryElement.csv"
  @parent ContributionClass

"Contribution Base" { SalaryElement, Position, Versions, YearMonth } =
  if(hasDMember(ContributionClass > Liable), "Gross Pay")
  @readonly true
```

Negative tests — "every row that does *not* map to …", and especially tests
against a NULL member through a parent — SHOULD NOT be used [EVAL-17]:

```text
# Fragile: the NULL test changes meaning as keys are populated
if(hasDMember(CFLine > "NULL (CFLine)"), 0, "CF Movement")

# Robust and sparse
if(hasDMember(CFEntryType > "Walk line"), "CF Movement")
```

The positive form also keeps the model sparse, and makes "which rows are in
scope" a property of the data.

### 3.9 Variation by entity, market and year

**[DIMD-15]** A new entity, market or year MUST be addable as data. Formulas
SHOULD NOT name entity or market members. Variation is expressed as:

- **parameter grids** keyed by the varying dimension —
  `"Employer Rate IN" { Market, Versions, Years }` — with that dimension in the
  grain of **every** parameter that varies by it (omitting it silently applies
  one market's rule to all);
- **applicability flags** — `"Element Applicable IN" { SalaryElement, Market,
  Years }` — multiplied in, rather than `if(hasDMember(Market > A), …)` gates;
- **local currency throughout**, with translation as a thin variable beside
  the local total: `"FX Rate IN" { Currency, Versions, YearMonth }`,
  reached through `@parent Currency` on `Market`.

Where a named gate is unavoidable, keep the **same formula shape** for every
market so that a fix applies to all of them mechanically.

### 3.10 The NULL member in practice

A dimension that is the parent of a dimension whose members may be unmapped
SHOULD declare its NULL member with `@null` [DIM-5], and every unknown parent
SHOULD point at it. Time dimensions have no NULL member, and dimensions
populated entirely by integration SHOULD NOT declare one. Use it to *see* unmapped
data — a report filtered to `NULL (PLLine)` lists every account without a
statement line — and monitor it: a growing NULL population signals an upstream mapping that drifted.
Do not use it as a formula selector through parents [EVAL-17].

### 3.11 Time and versions are not business dimensions

`YearMonth`, `Years`, `Months` and `Versions` are system dimensions (FML §6.7, FML §13). Models MUST
NOT create parallel period or scenario dimensions (`Period`, `Scenario`,
`FiscalMonth`) for data that the system dimensions can carry. A fiscal year
that differs from the calendar year is handled by the engine's calendar
configuration (implementation-defined), not by a custom dimension.

### 3.12 Checklist

Before writing formulas, confirm:

1. Every report axis is reachable from the output grains.
2. Every source is landed at its natural grain, without `Versions`.
3. Each dimension is one business object; no per-site copies.
4. Attributes are parents, not grain members.
5. Every line a formula selects is a member reachable through a parent.
6. Dimensions that formulas select on are flat.
7. No sister parents, no unintended diamonds, no empty foreign keys.
8. Every parent of a dimension whose members may be unmapped declares `@null`;
   every unknown parent points to its NULL member.
9. Every classification that varies by market or year is a data grid.
10. No formula produces cells densely: the estimated cells of every new
    variable (operand cells × the members it expands over) are known [EVAL-31].

---

## 4. Grain design and alignment

### 4.1 The rule

**[GRAIN-1]** In every formula, each operand SHOULD be at the output's grain, or
reach it by aggregation through parents ([EVAL-13]), or be an intended broadcast
([EVAL-9]). Operands of `+`, `-` and of a product inside `sum` SHOULD be
**aligned** — at the same grain as each other and as the output.

Grain misalignment is the most common cause of wrong numbers and slow formulas
alike, and the two usually come together.

### 4.2 Orphan dimensions

An **orphan dimension** is a dimension in the output grain that no operand
carries or reaches. The engine broadcasts every operand across it [EVAL-9]: the
same number appears on every member, and the calculation grows by the
dimension's member count.

```fml
# PackageRevenue's operands carry Package, not RevenueAccount
"Package Revenue OUT" { Board, Channel, RevenueAccount, Versions, YearMonth } =
  "Allocation Key IN" * "Revenue by Board"
  @readonly true
# → every RevenueAccount member gets the same value; the formula is ~100× slower
```

The fix is to put the dimension the operand **does** carry in the grain, and
obtain the coarser view by aggregation:

```fml
dimension Package from "dimensions/Package.csv"
  @parent RevenueAccount
"Package Revenue OUT" { Board, Channel, Package, Versions, YearMonth } =
  "Allocation Key IN" * "Revenue by Board"
  @readonly true
```

Ask of any output dimension that no operand carries: **is the same value
supposed to land on every member?** If yes, the broadcast is intended (an
exchange rate, a version-free actual). If no, the grain is wrong.

**[GRAIN-2]** The reverse never works: an output that **omits** a dimension
cannot **select** one member of it, because every operand is aggregated over
the omitted dimension before the formula is applied [EVAL-8].

### 4.3 Mixed-grain operands

Operands at different grains combined in one expression misalign. The remedy is
always the same: give each operand its own variable at the common grain first.

```fml
# Wrong — three grains in one if
"PL Plan OUT" { PLLine, CostCenter, Versions, YearMonth } =
  if(eq("FC Flag", 1), "PL Actual upstream", "PL Plan IN")
  @readonly true
#   "FC Flag"            { Versions, YearMonth }
#   "PL Actual upstream" { PLLine, CostCenter, YearMonth }
#   "PL Plan IN"         { Account, CostCenter, Versions, YearMonth }

# Right — project, then combine aligned operands
"PL Plan at PLLine" { PLLine, CostCenter, Versions, YearMonth } = "PL Plan IN"
  @readonly true
```

and then merge as in §6.3.

**Products inside `sum`.** `sum(A * F)` where `A` and `F` do not share the
result's grain aggregates each first and multiplies the aggregates [EVAL-8].
Compute the product at the finer grain; reading it at the result's grain
aggregates it [FUN-1]:

```fml
"Amount x Flag" { Dim, Position, YearMonth } = "Amount" * "Flag"
  @readonly true
"Target"        { YearMonth } = "Amount x Flag"
  @readonly true
```

**Two-stage gate, then collapse.** To select by a flag on a dimension the
result omits, gate first at a grain that still carries the dimension, then
collapse; the collapse performs the selection because the gated variable is
null on every other member:

```fml
"Cost at Budget"   { Position, Versions, YearMonth } = "Cost" * "Version Role Budget"
  @readonly true
"Cost at Forecast" { Position, Versions, YearMonth } = "Cost" * "Version Role Forecast"
  @readonly true
"Variance"         { Position, YearMonth }           = "Cost at Forecast" - "Cost at Budget"
  @readonly true
```

Pre-aggregation is per operand, so the two gated variables resolve to their own
versions independently — the whole variance is written without naming a
version member.

### 4.4 Projections

A **projection** is a variable whose only job is to hold another variable at a
different grain, reached through parents:

```text
"<Source> at <grain>" { <grain> } = "<Source>"
  @readonly true
```

**[GRAIN-3]** Projections SHOULD be named `"<Source> at <Grain>"` and SHOULD be
`@readonly true`. An engine whose calculation optimiser must be disabled for a
projection whose source is written by an integration says so in its
implementation profile; disabling it on the **consumer** of a misaligned
operand instead hides the defect.

Projections fix cross-grain addition [EVAL-12]: when `X + S` shows `S`'s
values only where `X` has cells — or nothing at all while `X` is empty — project
`S` to the consumer's grain and add the projection. A three-variable diagnostic
locates the culprit:

```text
"DIAG X"        { <consumer grain> } = X
"DIAG S"        { <consumer grain> } = 0 + "Suspect"
"DIAG X plus S" { <consumer grain> } = X + "Suspect"
```

If `"DIAG X plus S"` has the cells of `"DIAG X"` only, and `"DIAG S"` has cells
elsewhere, `"Suspect"` contributes values but places no cells [EVAL-4a].

### 4.5 Alignment checklist

For every calculated variable:

1. List the output grain.
2. List each operand's grain, with pinned members.
3. Map each operand dimension to the output through parents.
4. An output dimension reached by no operand → orphan: fix the grain, unless
   the broadcast is intended.
5. An operand dimension absent from the output → aggregated by that operand's
   `@rollup`: confirm that is intended.
6. Operands of `+` or `-` at different grains → project first.
7. A product inside `sum` at different grains → product variable first.
8. A pinned output with an operand that carries the pinned dimension → that
   operand reads all members [EVAL-18]: filter it explicitly.
9. A coarse variable read by a finer consumer → every consumer dimension the
   coarse variable lacks is broadcast: intended?
10. Two pins on dimensions connected by a parent → pin only the child [VAR-7].

---

## 5. Sparsity discipline

### 5.1 The rule

**[SPARSE-1] Do not answer the false branch.** Where a condition does not hold,
or data is absent, a formula SHOULD produce null, not `0` and not a constant.

Sparsity is the largest single performance lever in an FML model, and its
failures are invisible: a zero adds the same as a null, so totals stay right
while the cell count — and every rollup, export and report — grows by orders of
magnitude.

### 5.2 Writing sparse formulas

| Instead of | Write | Why |
|---|---|---|
| `if(c, x, 0)` | `if(c, x)` | the 2-argument `if` is null where `c` is false |
| `if(hasValue(B), B, 0)` (aligned) | `B` | in additive context null already behaves as 0 |
| `if(hasValue(B), 0, A)` | `if(not(hasValue(B)), A)` | emit only the meaningful branch |
| `gt(x, 0)` as a flag over dense `x` | `if(gt(x, 0), 1)` (one variable in the condition) or `if(gt(x, 0), Carrier)` | a bare comparison writes `0` wherever `x` has data [EVAL-6] |
| router ending `…, if(cN, z, 0))` | `…, if(cN, z))` | every unmatched cell would get a `0` |
| `Amount * Flag` with `Flag = 0` on some cells | seed `Flag` null there | `x * 0` writes `0`, `x * null` stays null |
| `0 + X` to lift through a parent | `if(hasValue(X), X)` | `0 + X` writes `0` wherever `X` has no cell |

Keep `0 + X` only where an explicit zero is intended — a factor that must read
`1 − 0` rather than `1 − null`.

### 5.3 Counting

There is no count rollup. **[SPARSE-2]** Count with a **1-or-null presence
flag** summed:

```fml
"Headcount Flag" { Employee, Versions, YearMonth } = if(gt("Contracted Hours IN", 0), 1)
  @readonly true
# sum over Employee = headcount; empty employees cost nothing
```

### 5.4 Carriers

A **carrier** is a variable that is present exactly where a calculation should
produce cells. Because only value-position references create cells [EVAL-4], a
carrier is how a formula obtains the right cell domain.

**[SPARSE-3]** When a branch must output a constant, or when a condition names
two or more variables, return a carrier in value position instead of a literal:

```fml
"Price Present Flag" { Item, Customer, Versions, YearMonth } = if(gt("Price", 0), "Qty Anchor")
  @readonly true
"CHECK Price Missing" { Item, Customer, Versions, YearMonth } =
  if(not(hasValue("Price Present Flag")), "Qty Anchor")
  @readonly true
```

Ways to build a carrier:

| Carrier | Formula | Domain |
|---|---|---|
| anchor from one input | `"Qty IN" * 0 + 1` | where `Qty IN` has data |
| anchor from several inputs | `("A IN" + "B IN") * 0 + 1` | the union of their cells |
| product of flags | `"Flag A" * "Flag B"` (1-or-null flags) | the intersection |
| a constant routed through an input | `"Seed IN"` holding `1` | where it is entered |

**[SPARSE-4]** A constant that must exist in cells SHOULD be held in a small
input variable and referenced, not written as a literal in a formula. The input
is named and auditable, and — unlike a literal — it anchors cells.

### 5.5 Dense products

**[SPARSE-5]** Two operands that are dense in **different** dimensions make a
product that is dense on the cross of both. Neither looks dangerous alone:

```fml
"Rate"        { Item, Versions, YearMonth }    # dense over items × months
"Rate Factor" { Customer, Versions, Years }        # dense over customers
# "Rate" * "Rate Factor" → every item-month × every customer
```

Wrapping the product in a condition removes cells but need not reduce the work
of computing it (FML §11.3, consequence 4). Multiply in a sparse carrier:

```fml
"Qty Anchor" { Item, Customer, Versions, YearMonth } = "Qty IN" * 0 + 1
  @readonly true
"Price"      { Item, Customer, Versions, YearMonth } = "Rate" * "Rate Factor" * "Qty Anchor"
  @readonly true
```

### 5.6 Review checklist

1. A literal `, 0)` closing an `if` — almost always sows zeros.
2. A bare comparison as a whole formula over a dense operand.
3. `if(hasValue(X), X, …)` in an aligned additive context — removable.
4. `* Flag` where the flag stores `0` on some cells.
5. `0 + X` used as a lift.
6. A product of operands dense in different dimensions.
7. A default taken through `hasValue` [EVAL-4].
8. A formula with only literals and context functions in value position.

---

## 6. Versions, actuals and forecasts

### 6.1 Postulates

**[VER-1]** Imports carry no `Versions` [TIME-2]. **[VER-2]** A variable is an
input or an output, never both [ARCH-3]. **[VER-3]** Formulas name no version
member except `Actual` [TIME-3]; all other routing is by data.

### 6.2 Forecast flags

Which periods of a version are actual and which are plan is data: a flag input
by version and period.

```fml
"FC Actual IN"   { Versions, YearMonth }
  @type integer
  @notes "1 = this period of this version takes actuals; empty = plan."
"FC Actual Flag" { Versions, YearMonth } = "FC Actual IN"
  @type integer
  @rollup average
  @readonly true
```

A rolling forecast moves its cut-over by editing flags, not formulas. Several
cut-overs (headcount closes earlier than cost) use several flags.

### 6.3 The merge

**[VER-4]** An output that shows actuals for actual periods and plan for plan
periods SHOULD be built from two stored halves, each the *whole* formula of its
variable, added together:

```fml
"Sales ACT part"  { Customer, Item, Versions, YearMonth } =
  if(eq("FC Actual Flag", 1), "Sales upstream")
  @readonly true
"Sales PLAN part" { Customer, Item, Versions, YearMonth } =
  if(not(eq("FC Actual Flag", 1)), "Sales Plan")
  @readonly true
"Sales OUT"           { Customer, Item, Versions, YearMonth } =
  "Sales ACT part" + "Sales PLAN part"
  @readonly true
```

`"Sales upstream"` has no `Versions` and broadcasts to every version
[EVAL-9]; the condition selects the actual periods. The single-formula form
`if(eq(flag, 1), actual, plan)` reads empty wherever the plan branch has no
cells — for instance in a freshly created version, or in actual months the
plan does not cover — because the plan is the only reference that carries the
whole grain, so it alone places the cells [EVAL-4a].

The form `if(hasDMember(Versions > Actual), actual, plan)` is valid; it
hard-wires the version routing and cannot express a rolling cut-over.

### 6.4 Scenarios and comparisons

A scenario is a `Versions` member plus the assumption inputs that differ in it.
Copying a version's inputs into a new version is a data operation, not a
formula.

**[VER-5]** Comparisons between versions or years — variance to budget, prior
year — SHOULD be made by reports placing two versions or years side by side, or
by the two-stage gate of §4.3. Models SHOULD NOT build copies of variables per
version (`"Revenue Budget"`, `"Revenue Prior Year"`).

### 6.5 Signed plans

Where an approved plan must not move when master data later changes — a
position moved to another cost centre must not alter an approved budget —
materialise the plan, at signing, into a read-only archive variable at the
reconciliation grain, on its own `Versions` member. The archive's cells *are*
the signature. Variances to actuals read the archive, not the live chain.

---

## 7. Controls, testing and validation

### 7.1 A zero control proves nothing

**[TEST-1]** A control that reads zero — a balance-sheet check, a
reconciliation difference — is not evidence of correctness on its own. It also
reads zero when:

- the money is missing from **both** sides (cells never created, [EVAL-4]);
- the defective variables are display-only subtotals that feed no control;
- the whole chain it checks evaluated to null.

Controls MUST be read together with the **positions** they are about — the
balance-sheet lines, the totals, the cell counts — and with **absolute
anchors**: totals computed independently from the source, carried into the
model and compared.

### 7.2 Control chains

```fml
# Both operands are first projected to the check grain (§4.4)
"Sales OUT at Entity"  { Entity, Versions, YearMonth } = "Sales OUT"
  @readonly true
"GL Revenue at Entity" { Entity, Versions, YearMonth } = if(hasValue("GL Revenue upstream"), "GL Revenue upstream")
  @readonly true
"CHECK Sales A"     { Entity, Versions, YearMonth } =
  if(eq("FC Actual Flag", 1), "Sales OUT at Entity" - "GL Revenue at Entity")
  @notes "Compared in actual periods only: the ledger has no plan."
  @readonly true
"CHECK Sales FINAL" { Entity, Versions, YearMonth } =
  if(gt(abs(round("CHECK Sales A", 2)), 0), "Entity Anchor")
  @notes "1 where sales and ledger revenue disagree; empty = reconciled."
  @readonly true
```

Each area ends in a sparse FINAL flag (1 or null, never 0); a green control
board is one on which every FINAL is empty. Mandatory areas for most models:
interface reconciliation (sales facts against ledger revenue), allocation
completeness (expanded total equals input total), merge integrity (output at
actual periods equals the upstream actual), balance identity (assets equal
equity and liabilities), negative-value scans, input coverage.

### 7.3 Conservation invariants

Every transformation that should preserve a total gets an invariant: an
allocation's expanded total equals its input; a workforce chain's gross plus
contributions equals its total cost; a cash-flow walk's movements equal the
change in the balance. Invariants are checked with a control chain.

> **Note.** A total that reconciles does not prove that its parts are right.
> An aggregate-then-multiply error [EVAL-8] distributes the correct total in
> the wrong proportions. Check at least one part independently.

### 7.4 How to test a variable

**[TEST-2]** Verify a variable by reading back the **stored** variable, at its
real grain, by value and by cell count. Evaluating an expression on its own at
one coordinate supplies that coordinate — the very anchoring a stored variable
may lack [EVAL-4] — and may aggregate its operands before evaluating; it can
confirm a formula that the stored variable does not compute.

**[TEST-3]** A probe variable MUST anchor on a variable that has data. A probe
built only from literals creates no cells and "returns nothing":

```fml
# Returns nothing
Probe { Region, YearMonth } = if(hasDMember(Region > North), 1, 0)
  @readonly true

# Works: the real variable anchors cells, * 0 contributes nothing
Probe { Region, YearMonth } = "Revenue" * 0 + if(hasDMember(Region > North), 1, 0)
  @readonly true
```

**[TEST-4]** Diagnose a chain by **counting cells per step** — the count of each
step against the count of its anchor — not only by comparing totals. A total
tells you that something is wrong; a cell count tells you where the grid
narrowed or exploded.

**[TEST-5]** Expected values MUST be computed independently of the model — by
hand, in a spreadsheet, from the source system — never by re-applying the
model's formula to the same drivers. Include edge cases: zero, negative, very
large, a period with exactly one populated input, the first month of a year.

### 7.5 Status boards

A **status board** shows, per entity or process, whether preconditions hold.
Make each precondition a single-concept 0/1 variable at the board's grain, and
combine with addition, which absorbs nulls:

```fml
"Plan Ready" { Entity, Versions, YearMonth } = eq("Pre Inputs" + "Pre Mapping" + "Pre Approval", 3)
  @numberFormat { type: NUMBER, custom: true, decimals: 0, formatString: "[=1]\"ready\";\"open\"" }
  @readonly true
```

`min`/`max` over flags and products of nullable flags are unreliable for this
purpose.

### 7.6 Changing a live model safely

**[TEST-6]** A change to a model in production use SHOULD be introduced as a
**no-op by construction**: the new logic gated by a flag whose else-branch is
the original formula verbatim, then activated by setting the flag after
verification:

```text
"Root" { … } = if(and(eq("Gate New Logic IN", 1), hasDMember(Class > New)), <new formula>, <original formula>)
```

With the flag empty the variable computes exactly as before. Take a snapshot
before the change, compare after, and accept only the intended deltas.

---

## 8. Performance

**[PERF-1]** The following rules SHOULD be applied at design time:

1. **Keep cells null** (§5). Sparsity is the largest lever.
2. **Align grains** (§4). An orphan dimension multiplies the work by its
   member count.
3. **Broadcast onto `Versions` with a condition, not a product.**
   `if(eq("FC Flag", 1), X)` equals `X * "FC Flag"` in value provided the flag
   stores only 1 or null, and lets an engine skip the work outside the gate.
4. **Never broadcast onto `Versions` and read through a parent in the same product.**
   Split into three stored steps: broadcast by condition; lift through the parent
   sparsely (`if(hasValue(X), X)`); multiply the now-aligned operands. Each
   step is then aligned and sparse.
5. **Multiply dense-in-different-dimensions products by a sparse carrier**
   (§5.5).
6. **Plan at the coarsest grain the business owns**, and expand late by
   allocation: keys → result → expansion (§9.8).
7. **Aggregate at source grain once** (leveling), then consume the leveled
   variable, rather than re-aggregating a fine import in many formulas.
8. **Monthly grain is the floor.** Daily, document or transaction detail stays
   in the source system.
9. **Outputs carry only the grain their consumers need.**
10. **Never produce cells densely at scale** [EVAL-31]. Compute the product of
    member counts — including `Versions` and the time dimension — for every new
    grain, and know which reference places its cells [EVAL-4a]: a formula
    with no full-grain reference, or a literal added across an orphan
    dimension, can produce that many.

**[PERF-2]** To optimise an existing model, measure first: collect per-variable
calculation time and cell counts after a full recalculation, rank by time and by
time per cell relative to the model's median, and fix the worst offenders
against the rules above. Verify each fix with disposable experiment variables
that compare duration, values, cell counts and controls — all four, not only
totals — before applying it to the real variable.


---

## 9. Modeling patterns

This section is **informative**. Each pattern gives a purpose, a dimension
design, the core variables, and the pitfalls that the pattern exists to avoid.
The patterns compose: the statement patterns (§9.2–§9.4) build on the forecast
routing of §6; consolidation (§9.6) builds on multi-entity aggregation
(§9.5).

Patterns are written with one storage convention, stated in each, and in
Style A naming (§2.2). Dimension members shown in prose (`Operating revenue`)
are illustrative.

### 9.1 Sign conventions

Choose one sign convention **per layer**, record it in `@notes` of the layer's
main variables, and verify it with a one-cell hand calculation before trusting
any total.

| Convention | Used by | Consequence |
|---|---|---|
| **All-positive** | statement scaffolds, planning inputs | assets, liabilities, equity, revenue and expense all stored positive; subtraction happens in formulas |
| **Signed (debit-positive)** | ledger data, consolidation layers | debits positive, credits negative: revenue negative, expense positive, a profit is negative; presentation needs a leading `0 -` |

To tell which convention a source uses, read one revenue cell: negative means
signed. Flip signs only for named exceptions; never flip wholesale.
A deduction stored positive needs subtracting: a capital total of 1 000 with a
loss line stored as +200 inside it is `total − 2 × line` = 600 when the stored
total added the line (1 000 = 800 + 200), and `total − line` when it did not; a
deduction already stored negative needs neither — check the stored sign first.

### 9.2 Profit and loss

**Purpose.** Planners enter the plan by account and cost centre and see actuals
as a baseline; the output splices actual and plan periods; statement subtotals
and margins are computed.

**Dimensions.** *(All-positive storage.)*

| Dimension | Level | Notes |
|---|---|---|
| `Account` | analytic | chart of accounts; shared with the balance sheet; NULL member |
| `PLLine` | synthetic, **flat** | members are the statement's real lines: `Operating revenue`, `Cost of sales`, `Other operating expenses`, `Depreciation and amortisation`, `Financial income`, `Financial expense`, `Income tax`; NULL member for unmapped accounts |
| `CostCenter` | analytic | P&L only |
| `Versions`, `YearMonth` | system | |

```fml
dimension Account from "dimensions/Account.csv"
  @parent PLLine
  @parent BSLine                  # each account populates exactly one of the two
  @null
dimension PLLine from "dimensions/PLLine.csv"
  @null
```

The populated foreign key *is* the classification: an account whose parent is a
`PLLine` member is a P&L account.

**Core variables.**

```fml
"IMPORT GL Activity" { Account, CostCenter, YearMonth }
  @folder "Import"
  @notes "Period activity per account and cost centre. Writer: ledger integration."
  @readonly true

"PL Actual upstream" { Account, CostCenter, YearMonth } = "IMPORT GL Activity"
  @folder "Import/Upstream"
  @notes "Version-free actual feeder; broadcasts to every version."
  @readonly true

"PL Plan IN" { Account, CostCenter, Versions, YearMonth } =
  if(eq("FC Actual Flag", 1), "PL Actual upstream")
  @folder "PL/Input"
  @notes "Planners own plan periods; actual periods show actuals (fenced seed)."

"PL ACT part"  { Account, CostCenter, Versions, YearMonth } =
  if(eq("FC Actual Flag", 1), "PL Actual upstream")
  @readonly true
"PL PLAN part" { Account, CostCenter, Versions, YearMonth } =
  if(not(eq("FC Actual Flag", 1)), "PL Plan IN")
  @readonly true
"PL OUT"           { Account, CostCenter, Versions, YearMonth } =
  "PL ACT part" + "PL PLAN part"
  @folder "PL/Output"
  @readonly true
```

**Subtotals** — every filter reads through the parent `PLLine` of `Account` [DIMD-6]:

```fml
"PL Gross Profit" { Account, CostCenter, Versions, YearMonth } =
    sum("PL OUT", PLLine > "Operating revenue")
  - sum("PL OUT", PLLine > "Cost of sales")
  @readonly true

"PL EBITDA" { Account, CostCenter, Versions, YearMonth } =
    "PL Gross Profit"
  - sum("PL OUT", PLLine > "Other operating expenses")
  @readonly true

"PL EBIT" { Account, CostCenter, Versions, YearMonth } =
    "PL EBITDA" - sum("PL OUT", PLLine > "Depreciation and amortisation")
  @readonly true

"PL Profit Before Tax" { Account, CostCenter, Versions, YearMonth } =
    "PL EBIT"
  + sum("PL OUT", PLLine > "Financial income")
  - sum("PL OUT", PLLine > "Financial expense")
  @readonly true

"PL Net Income OUT" { Account, CostCenter, Versions, YearMonth } =
    "PL Profit Before Tax" - sum("PL OUT", PLLine > "Income tax")
  @readonly true
```

Each subtotal holds, on each account, that account's contribution; read at any
coarser grain (by cost centre, by year, in total) it is the subtotal. A margin
against **total** revenue uses a helper without `Account` [DIMD-7]:

```fml
"PL Revenue Total" { Versions, YearMonth } = sum("PL OUT", PLLine > "Operating revenue")
  @readonly true
"PL EBITDA Margin" { Versions, YearMonth } =
  if(gt("PL Revenue Total", 0), "PL EBITDA" / "PL Revenue Total")
  @rollup formula
  @format percentage
  @readonly true
```

A ratio is neither summed nor averaged over months: at the quarter and the year
it is recomputed from the totals. FML has no standard `@rollup` value for that;
`@rollup formula` is a **Farseer extension** (FML Annex D) — it makes this variable,
and any model that uses it, an FML document with extensions [EXT-3]; the
profile restricts what may read such a variable.

**Pitfalls.** Filtering a subtotal on `Account` member names while other terms
filter on `PLLine` (AP-01). A `PLLine` member that bundles two lines a subtotal
needs (§3.4).

**Controls.** Recompute the subtotals independently from the same inputs; the
balance-sheet control cannot see P&L subtotal errors, because the subtotals feed
nothing. Check that no subtotal is an exact multiple of one line.

### 9.3 Balance sheet: overrides, collectors and a cumulative trail

**Purpose.** Plan the balance sheet line by line. *The pattern shows the
balance-sheet mechanics; for the control to read zero, cash (from the cash flow,
§9.4) and the current-year result (into retained earnings) must also be placed
on their lines, as FML Annex F does.* Mechanics: submodels (loans, capital
expenditure, receivables, payables, inventory) deliver movements or states;
planners correct with two override channels; the closing balance is one
cumulative trail from an opening anchor; actual periods take ledger balances.

**Dimensions.** *(All-positive storage.)*

```fml
dimension Account from "dimensions/Account.csv"
  @parent BSLine
dimension BSLine from "dimensions/BSLine.csv"     # analytic statement lines (30–80 members)
  @parent BSGroup
  @null
dimension BSGroup from "dimensions/BSGroup.csv"   # synthetic tree, no NULL member
  @parent BSGroup                 # a tree: Total assets ← Current / Non-current assets;
                                  #         Total equity and liabilities ← …
```

`BSGroup` is a tree because its rollup is meaningful, and it appears in no
variable grain [DIMD-10]: variables sit on `BSLine`.

**Core variables.**

```fml
# Actual side — version-free balances
"IMPORT GL Balance" { Account, YearMonth }
  @rollup closing_state
  @folder "Import"
  @readonly true
"BS Actual upstream" { BSLine, YearMonth } = "IMPORT GL Balance"
  @rollup closing_state
  @readonly true

# Plan side — opening anchor, submodel collectors, planner overrides
"BS Opening State" { BSLine, YearMonth } = "BS Actual upstream"
  @rollup closing_state
  @notes "Anchor for the plan trail: ledger balances. Reused, not imported twice."
  @readonly true

"BS Movement collector" { BSLine, Versions, YearMonth } =
  "BS Movement from Loans" + "BS Movement from Capex"
  @rollup sum
  @readonly true
"BS State collector"    { BSLine, Versions, YearMonth } = "BS State from Receivables"
  @rollup closing_state
  @readonly true

"BS Movement override IN" { BSLine, Versions, YearMonth }
  @rollup sum
"BS Closing override IN"  { BSLine, Versions, YearMonth }
  @rollup closing_state

# A state submodel contributes its month-on-month change
"BS State implied movement" { BSLine, Versions, YearMonth } =
  "BS State collector" - delay("BS State collector", 1)
  @rollup sum
  @readonly true

"BS Movement derived" { BSLine, Versions, YearMonth } =
  "BS Movement collector" + "BS State implied movement"
  @rollup sum
  @readonly true

"BS Effective movement" { BSLine, Versions, YearMonth } =
  if(hasValue("BS Movement override IN"), "BS Movement override IN", "BS Movement derived")
  @rollup sum
  @readonly true

# The ledger balance in the actual periods of each version: the trail restarts
# from it there, and a version whose actual periods are closed is not reset by
# later actuals. It carries the full grain, so it places cells beside the
# override [FML EVAL-4a].
"BS Actual anchor" { BSLine, Versions, YearMonth } =
  if(eq("FC Actual Flag", 1), "BS Opening State")
  @rollup closing_state
  @readonly true

"BS Effective anchor" { BSLine, Versions, YearMonth } =
  if(hasValue("BS Closing override IN"), "BS Closing override IN", "BS Actual anchor")
  @rollup closing_state
  @readonly true

"BS Plan State" { BSLine, Versions, YearMonth } =
  cumsum("BS Effective movement", 0, "BS Effective anchor")
  @rollup closing_state
  @readonly true

# Output — actual periods from the ledger, plan periods from the trail
"BS ACT part"  { BSLine, Versions, YearMonth } = if(eq("FC Actual Flag", 1), "BS Actual upstream")
  @rollup closing_state
  @readonly true
"BS PLAN part" { BSLine, Versions, YearMonth } = if(not(eq("FC Actual Flag", 1)), "BS Plan State")
  @rollup closing_state
  @readonly true
"BS OUT"           { BSLine, Versions, YearMonth } = "BS ACT part" + "BS PLAN part"
  @rollup closing_state
  @readonly true

# Identity
"BS Control" { Versions, YearMonth } =
  round(sum("BS OUT", BSGroup > "Total assets") - sum("BS OUT", BSGroup > "Total equity and liabilities"), 1)
  @readonly true
```

`cumsum(movement, 0, anchor)` accumulates movements and **restarts from the
anchor wherever the anchor has a value**: a closing override is both the
displayed value and the new starting point for later months.

**Placing submodel values on lines.** A submodel that does not carry `BSLine`
places its value with a **pinned transfer variable** [EVAL-19]:

```fml
"BS Movement from Loans" { BSLine = "Long-term borrowings", Versions, YearMonth } =
  "Loan Drawdowns OUT" - "Loan Repayments OUT"
  @readonly true
"BS Movement from Capex" { BSLine = "Property, plant and equipment", Versions, YearMonth } =
  "Capex Purchases OUT"
  @readonly true
"BS State from Receivables" { BSLine = "Trade receivables", Versions, YearMonth } =
  "Receivables Closing OUT"
  @rollup closing_state
  @readonly true
```

A submodel that already carries `BSLine`, or a dimension that has it as a parent, is
referenced directly.

**Pitfalls.** A balance with `@rollup sum` (twelve balances summed) [TIME-1].
A state collector placed directly in the output, which masks every correction.
An input with a formula on the plan side, which lets the opening state enter
twice. Placing values with an own-grain filter instead of a transfer variable.

**Controls.** `BS Control` is zero at every coordinate — and is read together
with the balance-sheet positions [TEST-1]. A non-zero value means a model
defect, a sign error, or an account mapped to `NULL (BSLine)`. Test one
state input, one movement input, one closing override and one movement
override, month by month.

> **Note.** `@rollup closing_state` takes the last value along time and **sums**
> along every other dimension, so a balance rolls up from lines to groups
> correctly without further work.

### 9.4 Indirect cash flow

**Purpose.** Derive the cash-flow statement from balance-sheet changes and
income-statement items, starting from profit before tax, and **reconcile it to
balance-sheet cash** — the reconciliation is the point of the pattern.

**Dimensions.**

```fml
dimension Account from "dimensions/Account.csv"
  @parent CFLine                  # which account feeds which cash-flow line
dimension CFLine from "dimensions/CFLine.csv"
  @parent CFEntryType             # classifier: Asset position | Liability position | PL position
  @parent CFSection               # presentation: Operating | Investing | Financing
```

`CFLine` is **flat** (it is in variable grains); `CFSection` provides the
statement subtotals by projection. Cash itself maps to a `CFLine` member of no
walk class, so neither delta picks it up.

**Core variables.** *(All-positive storage.)*

```fml
"CF BS Position" { CFLine, Versions, YearMonth } =
  if(or(hasDMember(CFEntryType > "Asset position"), hasDMember(CFEntryType > "Liability position")),
     "BS OUT by Account")
  @rollup closing_state
  @readonly true

"CF BS Position Prior" { CFLine, Versions, YearMonth } = delay("CF BS Position", 1)
  @rollup closing_state
  @readonly true

"CF Asset Delta" { CFLine, Versions, YearMonth } =
  if(hasDMember(CFEntryType > "Asset position"), "CF BS Position Prior" - "CF BS Position")
  @readonly true
"CF Liability Delta" { CFLine, Versions, YearMonth } =
  if(hasDMember(CFEntryType > "Liability position"), "CF BS Position" - "CF BS Position Prior")
  @readonly true

"CF PL Items" { CFLine, Versions, YearMonth } =
  sum("PL OUT by Account", CFEntryType > "PL position")
  @readonly true

"CF Profit Before Tax" { CFLine = "Profit before tax", Versions, YearMonth } = "PL Profit Before Tax"
  @readonly true

"CF Manual IN" { CFLine, Versions, YearMonth }
  @notes "Non-cash items and FX effects not derivable from balances."

"CF Indirect" { CFLine, Versions, YearMonth } =
  "CF Asset Delta" + "CF Liability Delta" + "CF PL Items" + "CF Profit Before Tax" + "CF Manual IN"
  @readonly true

"CF Net Change" { Versions, YearMonth } = "CF Indirect"
  @readonly true
"CF Net Change Prior" { Versions, YearMonth } = delay("CF Net Change", 1)
  @readonly true
"CF Beginning Cash" { Versions, YearMonth } = cumsum("CF Net Change Prior", 0, "Opening Cash Anchor")
  @rollup beginning_state
  @readonly true
"CF Ending Cash" { Versions, YearMonth } = "CF Beginning Cash" + "CF Net Change"
  @rollup closing_state
  @readonly true

"CHECK CF vs BS" { Versions, YearMonth } =
  round("CF Ending Cash" - sum("BS OUT", BSLine > "Cash and cash equivalents"), 0)
  @readonly true
```

`"BS OUT by Account"` and `"PL OUT by Account"` are the statement outputs at
account grain, projected to `CFLine` through `Account -> CFLine`, as in FML
Annex F. A balance sheet held on `BSLine`, as in §9.3, maps its lines instead:
`@parent CFLine` on `BSLine`, and `"CF BS Position"` reads `"BS OUT"`. `"Opening Cash
Anchor"` holds balance-sheet cash in the model's first period only.

**Pitfalls.** Collectors that are not gated by entry type count rollup nodes and
the NULL member. A negative gate (`not NULL`) through a parent changes meaning as
mappings are populated, and zeroes the walk while they are not [EVAL-17]. The
asset/liability sign branch is the largest source of "off by twice the
liability change". `delay` carries December into January [FUN-2], so January
reads null where December actuals are empty; such accounts need an explicit
December anchor.

**Controls.** `CHECK CF vs BS` is zero at every coordinate. If not, check in
order: the sign branch; accounts without a `CFLine` mapping; the first-month
anchor; manual-input drift.

### 9.5 Multi-entity aggregation and currency translation

**Purpose.** Several legal entities, each with its own functional currency and
local chart of accounts, reported in one currency through a group chart of
accounts. This is the foundation for consolidation.

**Dimensions.**

```fml
dimension Entity from "dimensions/Entity.csv"
  @parent EntityGroup                          # booking entities → group containers
  @parent Currency
dimension EntityGroup from "dimensions/EntityGroup.csv"
  @parent EntityGroup                          # a tree: arbitrary group depth
dimension LocalAccountE1 from "dimensions/LocalAccountE1.csv"
  @parent Account                              # one local chart per entity …
dimension LocalAccountE2 from "dimensions/LocalAccountE2.csv"
  @parent Account
dimension Account from "dimensions/Account.csv"
  @parent PLLine
  @parent BSLine
```

- Each entity keeps its **own local chart** as a dimension, with the group
  chart (`Account`) as its parent [DIMD-5]. Prefixing local codes into one shared dimension
  (`E1_4000`) is rejected: it turns mapping into string parsing and mixes
  attributes of different charts.
- **Booking entities** and **group containers** are two dimensions; containers
  form the tree.

**Core variables.**

```fml
"FX Closing Rate IN" { Entity, Versions, YearMonth }
  @rollup closing_state
  @notes "Local → reporting currency at month end; 1 for entities that report in group currency."
"FX Average Rate IN" { Entity, Versions, YearMonth }
  @rollup average

"IMPORT GL Activity E1" { LocalAccountE1, CostCenter, YearMonth, Entity = E1 }
  @folder "Import"
  @readonly true
"IMPORT GL Activity E2" { LocalAccountE2, CostCenter, YearMonth, Entity = E2 }
  @folder "Import"
  @readonly true

"GL Activity Local" { Entity, Account, CostCenter, YearMonth } =
  "IMPORT GL Activity E1" + "IMPORT GL Activity E2"
  @notes "Each import is pinned to its entity, so the sum keeps contributions apart."
  @readonly true

"PL Activity Reporting" { Entity, Account, CostCenter, Versions, YearMonth } =
  "GL Activity Local" * "FX Average Rate IN"
  @readonly true
```

The rates are keyed by `Entity` here for brevity; with many entities, key them
by `Currency` (and a `RateType`) and read them through `Entity -> Currency`
(§3.9), so that one rate serves every entity in that currency. The
entity-pinned imports are the only place where entities are listed; the
per-entity `+` list is the one extension point when an entity is added. Every
consumer reads the single merged `"GL Activity Local"`, which carries `Entity`
without naming any entity, so group totals come from
the `Entity -> EntityGroup` rollup and no formula names an entity.

**Rules.**

- Translate **once, at the end** of the plan path; all planning machinery stays
  in local currency. Balances use the closing rate, flows the average rate.
  Never translate inside a `cumsum`, which would add amounts in different
  currencies.
- Correct imported actuals with an overlay at the local, per-entity grain
  (an adjustment input and an adjusted variable, §1.5).
- Exchange rates, ownership percentages and tax rates are inputs, never literals.

**Controls.** Per-entity balance identity. One-cell FX smoke test (one rate, one
ledger cell, the expected translated value). Mapping coverage: the local trial
balance equals the group trial balance rolled through the parents; a difference
is an unmapped account.

### 9.6 Consolidation

Consolidation adds, on top of §9.5, intercompany elimination, adjustment
lanes, non-controlling interests, the translation reserve, the statement of
changes in equity and a readiness board.

**Intercompany.** A `Partner` dimension names the counterparty. It has the same
intra-group members as `Entity` but is a **separate** dimension, so one cell
carries both the booker and the counterparty:

```fml
dimension Partner from "dimensions/Partner.csv"
  @parent PartnerType             # Group | External
"IMPORT IC Activity" { Entity, Account, Partner, YearMonth }
  @folder "Import"
  @readonly true
```

Intercompany data is a partner-tagged copy of the intercompany subset only;
putting `Partner` on every ledger row would multiply the grain across millions
of non-intercompany cells. Eliminations are journal entries on a dedicated
lane, never edits of ledger data. Two rules make them right:

- **Reconcile before eliminating.** Entity A's balance with partner B is
  compared with B's balance with A; a difference beyond the agreed tolerance is
  a **mismatch**, reported as a control position, never eliminated silently.
- **Eliminate at the lowest group node that holds both.** An elimination
  between A and B is visible at that node of `EntityGroup` and above it, never
  at a node that contains only one of them; read the elimination lane through
  `EntityGroup` like every other lane.

**Adjustment lanes.** Each category of adjustment — top-side journals,
intercompany eliminations, group GAAP adjustments, reclassifications, tax — is
its own input variable, pinned to its own member of a flat `AdjustmentType`
dimension:

```fml
"Group Adjustment IN" { Entity, Account, CostCenter = "NULL (CostCenter)",
                        Versions, YearMonth, AdjustmentType = "Top side" }
"Reclass Adjustment IN" { Entity, Account, CostCenter = "NULL (CostCenter)",
                          Versions, YearMonth, AdjustmentType = Reclass }
"Adjustments Total" { Entity, Account, CostCenter, AdjustmentType, Versions, YearMonth } =
  "Group Adjustment IN" + "Reclass Adjustment IN"
  @readonly true
```

Every dimension of the consumer that the lane does not hold must be **pinned**
(here `CostCenter` to its NULL member), or the adjustment is broadcast and
multiplied by that dimension's member count [EVAL-9] — the most frequent
consolidation defect. Each lane can be rolled back, audited and edited
independently.

**Non-controlling interests.** Ownership is the group's **effective** share in
the entity — the product of the shares along the holding chain (80 % of a
subsidiary that holds 75 % is 60 %); for a direct subsidiary it is the
immediate parent's share. It is held at the grain of the movements it
multiplies; using the immediate share for an indirect holding understates
NCI:

```fml
"Ownership IN" { Entity, Versions, YearMonth }
  @rollup average
  @format percentage
"NCI Share" { Entity, Versions, YearMonth } = 1 - "Ownership IN"
  @rollup average
  @format percentage
  @readonly true
"Majority Result" { Entity, Versions, YearMonth } = "Consolidated Result" * "Ownership IN"
  @readonly true
"Minority Result" { Entity, Versions, YearMonth } = "Consolidated Result" * "NCI Share"
  @readonly true
```

`sum("Minority Result", EntityGroup > "Subgroup A")` gives NCI in the result
at any node, without per-level variables; NCI in equity is the same share of
the entity's net assets. Derive the minority share from the majority share;
two inputs drift.

**Translation reserve.** With balances at the closing rate and flows at the
average rate, the translated balance sheet no longer balances; the residual is
parked on one equity line. With signed storage, where a balanced balance sheet
sums to zero, a pinned variable with a deliberately unfiltered operand
[EVAL-18] reads the entity's whole balance sheet and writes its negative on the
reserve line:

```fml
"Translation Reserve" { Entity, Versions, YearMonth,
                        BSLine = "Translation reserve", CostCenter = "NULL (CostCenter)" } =
  0 - "Consolidated BS after Adjustments"
  @notes "Deliberately unfiltered (EVAL-18): reads the entity's whole balance sheet; signed storage."
  @readonly true
"Consolidated BS Final" { Entity, BSLine, CostCenter, Versions, YearMonth } =
  "Consolidated BS after Adjustments" + "Translation Reserve"
  @readonly true
```

The reserve is added in a **separate** final layer; folding it into the layer
it is computed from would make it circular and halve it.

Because the reserve absorbs whatever does not balance, it absorbs errors as
well. Two controls keep it honest: each entity's balance sheet balances in
local currency, **before** translation; and the reserve equals the difference
the rates explain — the result at closing less average rate, and the opening
equity at closing less historical rate — within rounding.

**Statement of changes in equity.** Two flat dimensions — `EquityComponent`
(share capital, retained earnings, reserves, NCI) and `EquityMovement` (opening,
result, OCI, contributions, dividends, closing) — form a matrix. Each movement
is a variable pinned to its (component, movement) cell; the closing balance is
a cumulative trail; the opening is the closing delayed by one period:

```fml
"Equity Movement Result" { Entity, Versions, YearMonth,
                           EquityComponent = "Retained earnings", EquityMovement = Result } =
  "Majority Result"
  @readonly true
"Equity Movements" { EquityComponent, EquityMovement, Entity, Versions, YearMonth } =
  "Equity Movement Result" + "Equity Movement OCI" + "Dividends IN"
  @readonly true
# "Equity Movement OCI" and "Dividends IN" are declared like "Equity Movement Result",
# each pinned to its own (component, movement) cell.
"Equity Movement Total" { EquityComponent, Entity, Versions, YearMonth } = "Equity Movements"
  @readonly true
"Equity Closing" { EquityComponent, Entity, Versions, YearMonth, EquityMovement = Closing } =
  cumsum("Equity Movement Total", 0, "Equity Opening Anchor")
  @rollup closing_state
  @readonly true
```

Do not gate movements with `if(hasDMember(EquityMovement > Result), …, 0)`; pin
them.

**Readiness board.** Per entity and period, single-concept 0/1 preconditions
combined by addition (§7.5):

```fml
"Ready Data Loaded"  { Entity, Versions, YearMonth } = and(hasValue("BS Feed at Entity"), hasValue("PL Feed at Entity"))
  @readonly true
"Ready Balanced"     { Entity, Versions, YearMonth } =
  eq(round("BS Local", 0), 0)
  @notes "The entity's balance sheet in local currency, before translation and the reserve: signed storage sums to zero."
  @readonly true
"Consolidation Ready" { Entity, Versions, YearMonth } =
  eq("Ready Data Loaded" + "Ready Rates" + "Ready IC Reconciled" + "Ready Balanced", 4)
  @readonly true
"Consolidated BS Published" { Entity, BSLine, Versions, YearMonth } =
  if(eq("Consolidation Ready", 1), "Consolidated BS Final")
  @readonly true
```

Lift each precondition to the board's grain if it might be missing at some
coordinates: beside a full-grain operand, a coarser precondition contributes
values only where that operand has cells [EVAL-4a].

**Stage columns.** Reports that show *before adjustments*, *adjustments* and
*after adjustments* use a flat `ReportStage` dimension and gate each
contribution by stage:

```fml
"Report Line" { Entity, Account, ReportStage, Versions, YearMonth } =
    if(hasDMember(ReportStage > Before), "Value Before")
  + if(hasDMember(ReportStage > Adjustments), "Adjustment Value")
  + if(hasDMember(ReportStage > After), "Value Before" + "Adjustment Value")
  @readonly true
```

A key figure whose grain lacks `ReportStage` shows the same number under every
stage column; give it the stage dimension.

**Single-signed result lines.** Statutory forms with separate *profit* and
*loss* lines, only one of which may carry a value, store the result as two
positive magnitudes on mutually exclusive carriers, selected by the sign of the
total computed at a grain **without** the entity dimension:

```fml
"Group Result" { Versions, YearMonth } = "Entity Result"
  @readonly true
"Group Profit Line" { Entity, Versions, YearMonth, Position = "Profit for the year" } =
  if(gt("Group Result", 0), "Entity Result")
  @readonly true
"Group Loss Line"   { Entity, Versions, YearMonth, Position = "Loss for the year" } =
  if(lt("Group Result", 0), 0 - "Entity Result")
  @readonly true
```

### 9.7 Workforce

**Purpose.** Plan personnel cost position by position, derive headcount from
contract dates, compute salary elements and employer contributions, and
reconcile to payroll and ledger actuals.

**Two grains.** Planning happens per **position**; reconciliation happens at the
grains the actuals arrive at — per **employee** (payroll) and per **account ×
cost centre** (ledger). Neither actual source carries a planned position.

**Dimensions.**

```fml
dimension Position                             # members are data, from integration
  @parent Employee
  @parent CostCenter
  @parent JobCode
dimension Employee
  @null
dimension JobCode from "dimensions/JobCode.csv"
  @parent PayGrade
dimension PayGrade from "dimensions/PayGrade.csv"
  @parent Market
dimension CostCenter from "dimensions/CostCenter.csv"
  @parent Entity
dimension SalaryElement from "dimensions/SalaryElement.csv"
  @parent ElementClass                         # Fixed | Variable | Contribution | One-off
  @parent Account                              # element → ledger account
  @parent ContributionClass                    # Liable | Exempt
```

All attributes hang off `Position` [DIMD-8]; `Employee` and `CostCenter` are
sisters through `Position`, and neither is a parent of the other [DIMD-11].
`Position` is populated by integration and declares no `@null`; vacant and
planned positions name `NULL (Employee)` as their parent.

**Headcount from dates.** Headcount is derived, never imported as a count, so
that a changed date drives the whole cost chain:

```fml
"Contract Start IN" { Position, Versions }
  @type date
  @format date
"Contract End IN"   { Position, Versions }
  @type date
  @format date
  @notes "Last day of the contract; empty for an open-ended contract."

"Planning Horizon IN" { Versions, YearMonth }
  @type integer
  @notes "1 in every month of the planning horizon."

# Carriers anchored on the start date
"Position Anchor" { Position, Versions, YearMonth } = if(hasValue("Contract Start IN"), "Planning Horizon IN")
  @notes "1 for every position with a start date, in every horizon month."
  @readonly true
"Open End Date"   { Position, Versions } = "Contract Start IN" * 0 + 2958465
  @notes "Serial number of 9999-12-31, present wherever a start date exists."
  @readonly true

"Contract Start Month" { Position, Versions } =
  date(year("Contract Start IN"), month("Contract Start IN"), 1)
  @type date
  @readonly true
"Contract End effective" { Position, Versions } =
  if(hasValue("Contract End IN"), "Contract End IN", "Open End Date")
  @type date
  @readonly true

"HC Active" { Position, Versions, YearMonth } =
  if(and(gte(currentDate(), "Contract Start Month"), lte(currentDate(), "Contract End effective")),
     "Position Anchor")
  @notes "1 in the months of the contract window, empty elsewhere."
  @readonly true
```

The default end date and the output are supplied by carriers in value position,
so a position without an end date still has cells, and months outside the
window stay null [EVAL-4], [SPARSE-3]; a test of `hasValue("Contract End IN")`
alone could never create cells. A
**proration** variable weights the first and last month by days worked
(`(daysInCurrentMonth() - day(start) + 1) / daysInCurrentMonth()`), making
headcount fractional; every per-position cost then multiplies by it.

**Salary elements.** Every cost component is a member of one `SalaryElement`
dimension. Each element is a variable **pinned** to its member, so the
collector is a plain sum, and behaviour is declared by classifiers and data
grids rather than by formula branches:

```fml
"EL101 Base Pay" { Position, SalaryElement = EL101, Versions, YearMonth } =
  "Base Salary IN" * "FTE"
  @readonly true
"EL102 Seniority" { Position, SalaryElement = EL102, Versions, YearMonth } =
  "EL101 Base Pay" * "Seniority Rate IN" * "Tenure Years"
  @readonly true
"EL301 Year End Gift" { Position, SalaryElement = EL301, Versions, YearMonth } =
  if(hasDMember(Months > "12"), "Gift Amount IN" * "HC Active")
  @readonly true

"Gross Pay" { Position, SalaryElement, Versions, YearMonth } =
  "EL101 Base Pay" + "EL102 Seniority" + "EL301 Year End Gift"
  @readonly true
```

Recurring pay scales with **FTE**; per-head payments scale with **headcount**.

**Employer contributions** are computed, never imported, on exactly the
elements that are liable:

```fml
"Contribution Base by Element" { Position, SalaryElement, Versions, YearMonth } =
  if(hasDMember(ContributionClass > Liable), "Gross Pay")
  @readonly true
"Contribution Base" { Position, Versions, YearMonth } = "Contribution Base by Element"
  @readonly true
"EL201 Employer Contribution" { Position, SalaryElement = EL201, Versions, YearMonth } =
  "Contribution Base" * "Employer Rate IN"
  @readonly true
```

The per-element intermediate is mandatory; `sum("Gross Pay" * Flag)` at
position grain would multiply aggregates [EVAL-8].

Where contributions are capped on a **cumulative annual** base, compute the
year-to-date base with a January reset (§9.10), cap it, and take the monthly
increment; a monthly cap applied to an annual regime never triggers in the
right month. Decide per contribution fund which regime applies.

**Time-varying attributes.** A cost-centre move from month N, or a fractional
split of one employee across cost centres, is a time-phased input keyed on both
dimensions (`"Allocation Weight IN" { Employee, CostCenter, Versions,
YearMonth }`), validated by a control that the weights sum to 100 %, and resolved
where cost is finally attributed — not by a live product across employees and
cost centres, which fans out.

**Conservation invariants.** Gross plus contributions equals per-position total;
the sum over cost centres equals per-employee cost; the output equals the sum of
its layers.

### 9.8 Allocation

**Purpose.** Distribute an amount held at a coarse grain to a finer grain by
drivers: overheads to products, cost-to-serve to customers, a plan tail to
customer × item by actual mix.

The canonical block has three steps:

```fml
"Opex Alloc Keys"   { Customer, Location, YearMonth } =
  if(gt("Driver Total", 0), "Driver Count" / "Driver Total")
  @readonly true
"Opex Alloc Result" { Customer, Location, Versions, YearMonth } =
  "Opex Amount" * "Opex Alloc Keys"
  @readonly true
"Opex Alloc Expanded" { Customer, Item, Versions, YearMonth } =
  "Opex Alloc Result" * "Item Share at Location" * "Item Anchor"
  @readonly true
```

Keys are read-only and guarded against a zero total (null, not a division by
zero). Expanding to a **finer** grain (here `Item`, with `@parent Location`)
is a lookup from the parent [EVAL-14]: beside a full-grain operand it supplies
values but creates no cells, and on its own it expands over every child; so the
expansion needs a key at the finer grain (`"Item Share at Location"`) and
a carrier there (`"Item Anchor"`). An output dimension that no operand reaches
is an orphan (§4.2).

When the amount is broadcast onto `Versions` and the keys lie at a different
grain reached through a parent, do not fuse both in one product [PERF-1 rule 4];
split:

```fml
"Tail Keys by Version" { Item, Customer, Versions, YearMonth } =
  if(eq("FC Plan Flag", 1), "Tail Keys")
  @readonly true
"Tail Amount at Key Grain" { Item, Customer, Versions, YearMonth } =
  if(hasValue("Tail Plan Amount"), "Tail Plan Amount")
  @readonly true
"Tail Alloc Result" { Item, Customer, Versions, YearMonth } =
  "Tail Keys by Version" * "Tail Amount at Key Grain"
  @readonly true
```

**Control.** Allocation completeness: the expanded total equals the input total.

**Top-down entry** — a planner typing an aggregate that the engine distributes —
is a different mechanism, and a matter of data entry outside the scope of this
specification (FML §1.3). Farseer's is described in its implementation profile
(FML Annex D).

### 9.9 Driver-based sales and prices

**Purpose.** Plan volume and price by customer and item, with prices derived
from realised behaviour and planners entering only the change.

```fml
# The realised price on actual periods resets the curve; on plan periods it is empty, so the curve carries
"Price Reset"  { Item, Versions, YearMonth } = if(eq("FC Actual Flag", 1), "Realised Price")
  @rollup average
  @readonly true
"Price Base"   { Item, Versions, YearMonth } = cumsum(0, 0, "Price Reset")
  @rollup average
  @readonly true
"Price Step"   { Item, Versions, YearMonth } = "Price Change IN" * "Price Base"
  @readonly true
"Price Curve"  { Item, Versions, YearMonth } = cumsum("Price Step", 0, "Price Reset")
  @rollup average
  @readonly true
```

An item without a price change has no step; its curve still runs on the
reset alone (FML §12.3, `cumsum`). Guard the realised price
on positive revenue and quantity — a negative realised price must never anchor.

The **decided** price per item adds a set price that wins over the curve, as
flag arithmetic over 1-or-null flags (`1 − null` reads 1, [EVAL-11a]):

```fml
"Price Set Flag"     { Item, Versions, YearMonth } = if(hasValue("Price Set IN"), 1)
  @rollup average
  @readonly true
"Price Curve Flag"   { Item, Versions, YearMonth } = if(hasValue("Price Curve"), 1)
  @rollup average
  @readonly true
"Price Decided Flag" { Item, Versions, YearMonth } =
  if(hasValue("Price Set IN"), "Price Set Flag", "Price Curve Flag")
  @rollup average
  @readonly true
"Price eff"          { Item, Versions, YearMonth } =
    "Price Set IN"
  + "Price Curve" * (1 - "Price Set Flag")
  @rollup average
  @readonly true
```

The customer price combines the dense item-month price with a customer
factor; without a carrier the product is dense on every item-month × customer
[SPARSE-5]. Anchor it on the planned **quantity** — an operand, not a
condition — so a price exists exactly where a quantity is planned. The
**list-price fallback** for an item with no decided price (a new item) belongs
here, on the anchor: in `"Price eff"` the item-grain list price would be a value
on cells that do not exist for such an item ([EVAL-4] consequence 5).

```fml
"Qty Anchor"   { Item, Customer, Versions, YearMonth } = "Qty IN" * 0 + 1
  @readonly true
"Price head"   { Item, Customer, Versions, YearMonth } =
    "Price eff" * "Price Factor" * "Qty Anchor"
  + "List Price" * "Price Factor" * "Qty Anchor" * (1 - "Price Decided Flag")
  @rollup average
  @readonly true
"Revenue head" { Item, Customer, Versions, YearMonth } = "Qty IN" * "Price head"
  @readonly true
```

`"Price head"` has exactly the cells of `"Qty IN"` where a price exists: the
anchor is its only full-grain operand [EVAL-4a].

Two controls belong to the chain, both returning a carrier so that they stay
sparse and read empty when healthy: **planned quantity without a price**, and,
as a warning, **planned quantity priced from the list** — list prices often
sit well above realised prices, and the fallback would otherwise hide that.

```fml
"Price Present Flag"         { Item, Customer, Versions, YearMonth } = if(gt("Price head", 0), "Qty Anchor")
  @readonly true
"CHECK Price Missing Flag"   { Item, Customer, Versions, YearMonth } =
  if(not(hasValue("Price Present Flag")), "Qty Anchor")
  @readonly true
"Price Decided Anchor"       { Item, Customer, Versions, YearMonth } = "Qty Anchor" * "Price Decided Flag"
  @readonly true
"CHECK Price From List Flag" { Item, Customer, Versions, YearMonth } =
  if(not(hasValue("Price Decided Anchor")), "Price Present Flag")
  @readonly true
```

The example `examples/sales-allocation/` builds the whole chain.

**Working capital** follows from drivers: receivables = revenue × days sales
outstanding ÷ days in period; inventory = cost of sales × days inventory
outstanding ÷ days; payables = purchases × days payables outstanding ÷ days.
Each is a balance (`@rollup closing_state`).

**Volume, price and mix bridge** between two slices A and B (for example plan
and actual), at the level where the bridge is reported — a product group, a
region — with lines `i` below it, quantities `q` and prices `p`:

- volume effect = (Σq_B − Σq_A) × p̄_A, where p̄_A = Σ(q_A · p_A) / Σq_A, the
  average price of A;
- mix effect = Σ(q_B · p_A) − Σq_B × p̄_A — B's quantities at A's prices,
  against B's total quantity at A's average price;
- price effect = Σ q_B · (p_B − p_A).

The three add up to Σ(q_B · p_B) − Σ(q_A · p_A) exactly. Mix exists only at an
aggregate: computed line by line, volume and price already close the bridge and
mix is zero. So the volume and mix effects are formulas at the reporting level
(its own grain, reading the lines by aggregation), and the price effect is
summed from the lines.

### 9.10 Year-to-date and de-cumulation

A year-to-date figure is **read**, not stored: `Years > "2026"` with
`Year to date > "06"` is January to June 2026 under the variable's `@rollup`
(FML §6.7). A stored series is needed only where a report or a formula wants
year to date month by month:

```fml
# Year to date month by month: the third argument restarts the sum each January.
# The restart needs a cell in every January, also where the result is empty there:
# "Result Carrier" is 0 wherever the entity plans (§5.4).
"Result Year Start" { Entity, Versions, YearMonth } =
  if(hasDMember(Months > "01"), "Monthly Result" + "Result Carrier")
  @readonly true
"Result YTD" { Entity, Versions, YearMonth } = cumsum("Monthly Result", 0, "Result Year Start")
  @readonly true

# Monthly values from a cumulative source; nothing after the last loaded month
"Monthly from YTD" { Entity, Versions, YearMonth } =
  if(hasValue("Source YTD"),
     if(hasDMember(Months > "01"), "Source YTD", "Source YTD" - "Source YTD Prior"))
  @readonly true
"Source YTD Prior" { Entity, Versions, YearMonth } = delay("Source YTD", 1)
  @readonly true
```

Before wrapping a source in `cumsum`, check whether it is already cumulative:
read one entity in month 1 and month 6. Accumulating a cumulative source
inflates it many times over.

### 9.11 Rendering dimensions for statutory forms

A statutory reporting form is a **rendering dimension**: its members are the
form's rows, a parent of the group chart of accounts, and a tree for the
form's own hierarchy. The mapping lives on the chart's foreign-key column.

```fml
dimension Account from "dimensions/Account.csv"
  @parent FormX2026
dimension FormX2026 from "dimensions/FormX2026.csv"
  @parent FormX2026
```

- Variables are not grained on a form dimension.
- Forms change from year to year: use **one dimension per form-year**
  (`FormX2025`, `FormX2026`) rather than validity attributes; small
  dimensions are cheap to duplicate.
- Computed rows (netted totals, ratios) are variables the report reads, not
  members.
- Coverage control: every account has a foreign key to the form dimension.

### 9.12 Frozen copies

Where an approved plan or a filed report must not move when the live model
changes, keep a read-only, formula-free twin variable at an explicit grain and
write the approved values into it at the moment of approval (§6.5). The
twin's cells are the record; it never carries a formula. The twin has the
grain of the values it records, time grain included.

---

## 10. Anti-pattern catalogue

Each entry names an anti-pattern, the failure it causes, and the correct form.
Identifiers `AP-nn` are stable and may be cited in reviews.

| ID | Anti-pattern | Failure | Correct form |
|---|---|---|---|
| AP-01 | One formula mixes an own-grain filter and a through-parent filter | wrong by an exact multiple; controls stay at zero | route every term through a parent; split the synthetic level or add a role dimension (§3.4) |
| AP-02 | Pinned output with an unfiltered read of the pinned dimension | the whole total parked on one member | filter inside the expression, or drop the pin [EVAL-18] |
| AP-03 | `Dim = Member` or `Var { … }` in a formula | an error (`FML-E0401`) | `sum(Var, Dim > Member)` [VAR-6] |
| AP-04 | Unqualified member reference (`sum(X, Q1)`) | an error (`FML-E0402`), or the wrong member where the name is ambiguous | `sum(X, Quarters > Q1)` [EXPR-8] |
| AP-05 | Literal-only formula or probe | no cells; "returns nothing" | anchor on a variable with data [EVAL-4], [TEST-3] |
| AP-06 | Default through `hasValue` (`if(hasValue(S), S, 1)`) | default never materialises; downstream products null | carrier in value position (§5.4) |
| AP-07 | Literal output gated on two or more variables | no cells | return a carrier [SPARSE-3] |
| AP-08 | `if(c, x, 0)`, router ending in `, 0)`, bare comparison over dense data | zeros sown across the grid; slow | 2-argument `if`; drop the terminal `0` (§5.2) |
| AP-09 | `if(hasValue(B), B, 0) + A` in an aligned context | redundant guard | `A + B` |
| AP-10 | A coarse term beside a full-grain operand that must supply cells of its own (`X + S`, a coarse fallback, a version-free actual next to a plan) | the coarse term appears only on the full-grain operand's cells; an empty full-grain operand empties the formula | lift or project the term to the consumer's grain, or anchor it on a carrier [EVAL-4a], [EVAL-12] |
| AP-11 | `sum(A * F)` with misaligned operands | total × count instead of a filtered sum | product variable at the finer grain, then `sum` [EVAL-8] |
| AP-12 | Flag multiplied to select a member of a dimension the result omits | the unfiltered total | two-stage gate then collapse (§4.3) |
| AP-13 | Orphan dimension in an output grain | same value on every member; huge slowdown | put the operand-carried dimension in the grain (§4.2) |
| AP-14 | Coarse variable read by a finer consumer without pinning consumer-only dimensions | value multiplied by member counts | pin the consumer dimensions the value does not vary by |
| AP-15 | Two pins on dimensions connected by a parent | ambiguous; may be rejected (`FML-W0203`) | pin the child only [VAR-7] |
| AP-16 | Balance with `@rollup sum` | year value is twelve balances | `@rollup closing_state` [TIME-1] |
| AP-17 | Percentage formula × 100 with percentage format | displayed 100× too large | hold the ratio [PROP-7] |
| AP-18 | `@format currency(EUR)` | an error (`FML-E0902`) | `@format currency` plus `@numberFormat { currency: "EUR" }` [PROP-6] |
| AP-19 | `Versions` in an import grain | actuals missing in forecast versions | version-free imports [TIME-2] |
| AP-20 | A plan version named in a formula | breaks when versions change | forecast flags [TIME-3] |
| AP-21 | `if(eq(flag, 1), actual, plan)` as one formula | output empty where plan has no cells | two stored halves [VER-4] |
| AP-22 | Input variable with an unfenced formula | planner-owned name over computed cells | rename to a calculation; or fence the seed [ARCH-3] |
| AP-23 | ` OUT` on intermediates; `IMPORT` on formulas | misleading names | §2.1 |
| AP-24 | Prose in `@desc` | breaks report row labels | `@notes` [NAME-6] |
| AP-25 | Attribute dimension in variable grains | moving an object rewrites data | a parent of the object's dimension [DIMD-8] |
| AP-26 | One dimension per site, market or entity with identical structure | model change for every new site | one dimension, a member per site [DIMD-2] |
| AP-27 | Sister dimensions, one the parent of the other; a dimension and its ancestor in one grain | rejected grains; ambiguous rollup | conformed star; clone dimension where needed [DIMD-11] |
| AP-28 | A parent added with an empty foreign-key column | everything through the parent reads null | populate in the same change [DIMD-12] |
| AP-29 | Test against a NULL member through a parent | changes meaning as keys are populated | positive test on a classifier [DIMD-14] |
| AP-30 | Tree in calculated variables' grains, ungated | phantom cells at rollup nodes; double counting | flat dimension, or gate to leaves [DIMD-10] |
| AP-31 | Member names hard-coded where a dimension could carry the distinction | formula edits for data changes | parent or data grid [DIMD-1] |
| AP-32 | Market or entity named in formulas; per-market copies of variables | new market = formula change | parameter grids and applicability flags [DIMD-15] |
| AP-33 | Product of operands dense in different dimensions | cell explosion; recalculation failure | sparse carrier [SPARSE-5] |
| AP-34 | `X * carrier` for a version broadcast; broadcast and parent hop fused | slow recalculation | condition form; split steps [PERF-1] |
| AP-35 | `0 + X` as a lift | phantom zeros | `if(hasValue(X), X)` |
| AP-36 | products to combine flags | null where any flag is missing | `eq(P1 + … + PN, N)` (§7.5) |
| AP-37 | A zero control accepted as proof | defects hidden | read positions and anchors [TEST-1] |
| AP-38 | Evaluating an expression on its own to confirm a stored variable | false confirmation | read the stored variable [TEST-2] |
| AP-39 | Deleting a member that formulas reference | formulas refer to a member that no longer exists | rename instead [DIM-7] |
| AP-40 | Entities summed by name in group formulas | an added entity is silently missing | entity dimension and rollup (§9.5) |
| AP-41 | Adjustment lane without pins for consumer dimensions | adjustment multiplied by member counts | pin every consumer dimension (§9.6) |
| AP-42 | Translation inside a `cumsum` | currencies mixed | translate once at the end (§9.5) |
| AP-43 | Comparison copies per version or year (`"Revenue Budget"`) | duplicated logic | report-level comparison; two-stage gate [VER-5] |

---

---

## Revision history

| Version | Date | Changes |
|---|---|---|
| 1.0 | (draft) | First version. |
