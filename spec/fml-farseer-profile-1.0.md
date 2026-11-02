# Financial Modeling Language (FML) — Farseer Implementation Profile

## Companion Document — Version 1.0 (Draft)

*An informative companion to the FML Specification 1.0*

| | |
|---|---|
| **Version** | 1.0 — draft |
| **Status** | Informative. Describes one implementation; defines nothing a conforming FML document must use |
| **Date** | 2026-10-15 |
| **Editor** | Zrinko Dolic (Farseer) |
| **Companion to** | [Financial Modeling Language (FML) Specification 1.0](fml-1.0.md) |
| **Copyright** | © 2026 Farseer d.o.o., Zagreb, Croatia |
| **License** | [Creative Commons Attribution 4.0 International (CC BY 4.0)](../LICENSE) |

---

## 1. Scope

FML originated as the text format of the Farseer planning platform, which is the
reference implementation of the FML Specification (FML §1.4). Farseer accepts
more than the standard: properties, a `@rollup` value, functions,
dimension-table columns and variables with an empty grain that are tied to how Farseer stores, enters and computes
values. FML §2.5 permits such **extensions** [EXT-1] and requires every
implementation to document them in an **implementation profile**. This document
is Farseer's.

It contains:

- the Farseer extensions — what each one does, and the rules that keep a model
  that uses it correct (Sections 2–6);
- the mapping between FML and Farseer's model interchange format (Section 7);
- Farseer's choices where the specification leaves a behaviour
  implementation-defined (Section 8);
- the rules an authoring agent follows when its target is Farseer (Section 9),
  and the diagnostics and anti-patterns for the extensions (Section 10).

**Portability.** A document that uses any construct of Sections 2–6 is an FML
document **with Farseer extensions** [EXT-3]. It loads and evaluates in
Farseer; another conforming processor preserves the constructs [EXT-2] but need
not evaluate them.

Every behaviour stated in this document was measured on Farseer with probe
models. Rules carry identifiers of the form **[FP-n]**; diagnostics that only a
Farseer-aware linter reports carry the prefix `FSR-` (Section 10).

---

## 2. Variable properties

| Property | Value | Default |
|---|---|---|
| `@optimizeCalculation` | boolean | `true` |
| `@calculateOnDemand` | boolean | `false` |
| `@active` | boolean | `true` |
| `@useHierarchy` | boolean | `true` |

### 2.1 `@optimizeCalculation`

`true` (default) allows Farseer's calculation optimiser, which may reuse results
and skip recomputation. `false` forces fresh computation and SHOULD be used only
on narrow projection variables (FML Modelling Guide §4.4) whose source is written by
integrations and must be re-read after every load. It MUST NOT be used as a
remedy for misaligned grains (FML Modelling Guide §4): disabling the optimiser on the
**consumer** of a misaligned operand is slow and hides the defect (FP-AP-1); the
remedy is a projection intermediate [GRAIN-3]. It is not a first-line
performance tool (FML Modelling Guide §8).

### 2.2 `@calculateOnDemand`

`true` defers computation of the variable until an explicit request is made.
Until then the variable holds no cells, and **every variable that reads it
reads null**. Farseer does not recompute a calculate-on-demand variable except
on explicit request.

**[FP-1]** `@calculateOnDemand true`:

- MUST NOT be set on a variable into which values are entered or imported
  [FP-2];
- SHOULD NOT be set unless the model owner has explicitly accepted it for that
  variable, with its consequences explained;
- MUST NOT be chosen autonomously by an authoring agent (Section 9).

**[FP-2]** A calculate-on-demand variable holds computed values only: each
explicit recomputation replaces its cells. Values MUST NOT be entered into, or
imported into, a calculate-on-demand variable.

It exists to break very long calculation chains. A separate application step
that writes results into a stored variable is usually the simpler means to the
same end. Where a chain reads null, check whether a variable it reads is
calculate-on-demand and has not yet been computed.

### 2.3 `@active` and `@useHierarchy`

Farseer stores both flags on the variable and returns them in its model export
(Section 7.1). Neither changes a value that Farseer computes or returns:

- a variable with `@active false` is computed exactly as with `@active true`,
  is recomputed when its sources change, and is read by its consumers; an
  input with `@active false` accepts entered values, and its consumers read
  them;
- a variable with `@useHierarchy false` gives the same values as with
  `@useHierarchy true` when it is read at a parent member through a parent, under
  `sum`, at `Quarters` and at the year, by formulas and by direct reads alike,
  whether it is an input or calculated.

**[FP-9]** Authors MUST NOT use `@active false` to take a variable out of
calculation, or `@useHierarchy false` to stop its aggregation: neither has that
effect. A variable that must stop computing is given no formula or deleted; a
value that must not aggregate is given `@rollup none` (FML §9.4.2).

---

## 3. Top-down entry: `@zConstraint` and `@topDownMapping`

Farseer lets a planner type a value at an aggregate coordinate and distributes
it to the leaves. Entry is outside the scope of the FML Specification (FML
§1.3); this section describes it because two properties configure it and
because it creates cells.

| Property | Value | Default | Purpose |
|---|---|---|---|
| `@zConstraint` | boolean | `false` | constrained top-down entry (user-interface label "Constrained Light Top Down") |
| `@topDownMapping` | string | none | configuration string of top-down entry; processors preserve it verbatim [PROP-12] |

**[FP-3] (top-down entry)** A value entered at an aggregate coordinate of a
writable variable — a year or quarter instead of a month, a member of a parent
dimension, a dimension left unspecified — is distributed over the leaf
cells under that coordinate. The leaves that hold a cell — **zeros included** —
are the **template**:

1. Template leaves are scaled in proportion to reach the entered value; leaves
   without a cell receive nothing.
2. If every template leaf holds `0`, the value is spread evenly over the
   template leaves only: zeros in `a` and `b`, then `90` at the total, gives
   `45` and `45`, and nothing in `c`; a year written as `120` over zeros in
   `"2026-01"` and `"2026-02"` gives `60` and `60`.
3. If no leaf holds a cell, the value is spread evenly over every leaf —
   divided among them for `@rollup sum`, repeated on each for `average`,
   `closing_state` and `beginning_state`. The NULL member and the children of
   several parents are leaves like any other.
4. Entering `0` sets the template leaves to `0`; entering an empty value
   deletes every leaf.
5. At a node of a tree the value is spread evenly over the
   node and its descendants, whatever they hold. A stored input then holds a
   cell at that rollup node (FML [EVAL-16]).

**`@zConstraint true`** refuses case 3: a value may be entered at an aggregate
coordinate only where a template exists ("Please enter template before data
entry"). Cases 1, 2, 4 and 5 are the same with and without the flag.

**Guidance.** Top-down entry is a different mechanism from allocation (FML Modelling Guide
§9.8). Variables that accept it SHOULD set `@zConstraint true`, so that an
aggregate cannot be written over leaves that hold nothing — without the flag
such a write fabricates an even spread (case 3); an input form must still reach
the full grain to seed the leaves. Percentages and averages MUST NOT be entered
top-down.

---

## 4. Measures and `@rollup formula`

### 4.1 Measures

A variable with an empty grain `{ }` is a **measure** (FML §8.3 leaves an empty
grain to profiles).

```fml
"EBITDA Margin" { } = EBITDA / Revenue
  @format percentage
"BS Check" { }      = sum("BS Amount", BSSide > Assets) - sum("BS Amount", BSSide > "Equity and liabilities")
```

**[FP-4]** A measure has no cells of its own. When read, it is evaluated in the
context of the reader — a report cell, or a coarser aggregate — and its grained
operands, wrapped in `sum`, are aggregated to that context. References to
grained variables in a measure's formula SHOULD be wrapped in `sum(…)`.

**[FP-5]** A measure is a **leaf** of the dependency graph. A measure MAY read
grained variables. A grained calculated variable MUST NOT read a measure:
Farseer rejects the model ("Calculation formula cannot reference measures",
`FSR-E0101`), whatever the variable's `@rollup`. A measure MAY read another
measure only if no other operand of that formula has a grain.

**[FP-6]** Time-series functions MUST NOT be applied to a measure
(`FSR-E0102`), and a measure cannot hold stored values: values cannot be
entered into or imported into it (`FSR-E0103`). A quantity that must be written
needs at least a minimal grain such as `{ Versions, YearMonth }`.

Measures suit top-level ratios and key figures read directly by reports —
margins, cost-income ratios, identity checks.

### 4.2 `@rollup formula`

Farseer accepts one `@rollup` value beyond those of FML §9.4.2: `formula`, the
variable's formula evaluated at the coarser grain — for ratios that must be
recomputed from totals, not averaged.

```fml
"PL EBITDA Margin" { Versions, YearMonth } =
  if(gt("PL Revenue Total", 0), "PL EBITDA" / "PL Revenue Total")
  @rollup formula
  @format percentage
  @readonly true
```

**[FP-7]** A variable with `@rollup formula` **stores no cells**. It is evaluated
only when it is read directly — by a report, a sheet or an export — at the leaf
grain as at every coarser grain, where its operands are aggregated first (`A`
30 + 50 + 70 over `B` 2 + 5 + 10 reads `150 / 17` for the quarter and the
year).

- **Every formula that reads it reads null**, at its own grain as at a coarser
  one; `sum` over it reads null too (`FSR-W0201`).
- On a direct read the formula is evaluated by [EVAL-11] with one difference: a
  **quotient whose numerator is null is null**, where a stored formula gives
  `0`. `if(gt(B, 0), A / B)` therefore reads null in a period without `A`, and at
  a year whose closing `A` is empty; `A + B`, `B - A`, `A * B` and `A + 1`
  read as [EVAL-11] says.
- Values entered into a writable formula-rollup variable are stored; formulas
  that read it see **only** those entered cells. A direct read shows an entered
  value in place of the formula at its month and in the quarter that contains
  it, while the year is still recomputed from the operands.

So `@rollup formula` belongs on display ratios that nothing reads and nobody
enters. A ratio another formula needs is computed again in that formula from
its operands.

---

## 5. Functions

Farseer implements every function of FML §12 and the functions of this
section.

| Function | Signature | Requires | Value-position args | Notes |
|---|---|---|---|---|
| `spread_days` | `spread_days(x, n [, d])` | `YearMonth` | `x` | as `spread`, in days |
| `mom` | `mom(p)` | `YearMonth` | — | from an entered start value |
| `qoq` | `qoq(p)` | `YearMonth` | — | a cell every 3rd month |
| `yoy` | `yoy(p)` | `YearMonth` or `Years` | — | a cell every 12th month, or every year |
| `predictAverage` | `predictAverage(x)` | `YearMonth` | `x` | running mean of `x` where nothing is entered; exactly one argument |
| `hasTags` | `hasTags(m…)` | — | none | legacy synonym of `hasDMember` |

### 5.1 `spread_days`

**Syntax** `spread_days(expr, days [, delay_days])` · **Requires** `YearMonth`.

**Result** As `spread` (FML §12.3), with the period and the delay in **days**;
each month receives the share corresponding to its number of days.

```fml
"Prepaid Release" { Contract, Versions, YearMonth } = spread_days("Prepayment IN", 365, 15)
```

`spread_days` is a time-series function (FML [FUN-6]), and it MUST NOT be applied to a measure [FP-6].

### 5.2 Growth and prediction

Growth functions extend a **starting value entered** in some period through the
following periods. They are the whole formula of a writable variable into which
the planner types the starting value, and they rely on FML [VAR-8]: an entered
value in a cell of a calculated variable is the value of that cell, and the
formula supplies the cells that have no entered value.

| Function | Requires | Result |
|---|---|---|
| `mom(p)` | `YearMonth` | each month = previous month × (1 + p) |
| `qoq(p)` | `YearMonth` | one cell every third month from the starting value, × (1 + p) each time; no cells in between |
| `yoy(p)` | `YearMonth` or `Years` | one cell every twelfth month (every year on `Years`) from the starting value, × (1 + p) each time; no cells in between |
| `predictAverage(x)` | `YearMonth` | every period without an entered value holds the running mean of `x` over the periods so far; a literal `x` holds the literal |

```text
mom(0.1), 100 entered in 2026-02:  2026-01=·  2026-02=100  2026-03=110  2026-04=121  2026-05=133.1  …
```

```fml
"Customers IN" { Segment, Versions, YearMonth } = mom(0.02)
  @notes "Enter the starting customer count; later months grow by the monthly rate"
```

**[FP-8] (growth)**

1. A later entered value restarts the series from itself.
2. The rate `p` may be a variable. Where it is null, the last earlier rate that
   had a value is used. Where no earlier rate exists, the series stops after
   the entered value and resumes only from a later entered value.
3. `predictAverage` takes exactly one argument; `predictAverage()` and
   `predictAverage(x, n)` are rejected. A value entered where `x` has data
   replaces it and leaves the mean; a value entered where `x` is null joins
   the mean (`x` = 10, 20, 60 in `"2026-01"`–`"2026-03"`, empty in `"2026-04"`
   and `"2026-05"`, 500 entered in `"2026-05"`: the five months read 10, 15, 30,
   30, 500, and `"2026-06"` reads 124).
4. Other formulas read an entered value of a growth variable only at a
   coordinate where the growth formula itself has a cell: a value entered to
   restart a series is visible to them, the starting value of a series is not.
5. A growth variable is the one permitted exception, besides a fenced seed, to
   FML [ARCH-3] (an input carries no formula). Growth functions MUST NOT be
   applied to a measure [FP-6].

### 5.3 `hasTags`

`hasTags` is a legacy synonym of `hasDMember` (FML §12.4), with the same
arguments and result. New documents SHOULD use `hasDMember`; a processor that
emits FML for a Farseer model MAY rewrite `hasTags` to `hasDMember`.

---

## 6. Dimensions and members

### 6.1 Time and system dimensions

Farseer stores time in **two** grain dimensions, `Years` and `Months`, and has
no `YearMonth` dimension. FML's single time dimension [VAR-9] maps onto them:

| FML | Farseer |
|---|---|
| a grain with `YearMonth` | a grain with `Years` and `Months` |
| a grain with `Years` | a grain with `Years` |
| a grain with `Months` | a grain with `Months` |
| the member `"2026-03"` | the coordinate `Years > Y2026`, `Months > M3` |
| the member `"2026"` of `Years` | `Y2026` — Farseer's year names carry a mandatory `Y` prefix |
| the member `"03"` of `Months` or `Year to date` | `M3` — Farseer's month names are `M1` … `M12` |
| the filter `YearMonth > "2026-03"`, the pin `YearMonth = "2026-03"` | the two filters, or the two pins, `Years > Y2026` and `Months > M3` |

**[FP-12]** A processor that loads an FML document into Farseer, or emits one
from a Farseer model, applies this mapping in both directions. Farseer also
accepts grains that FML does not: more than one time dimension other than the
pair above, or a reading level — `Quarters`, `Half years`, `Year to date` — in
a grain. These grains are **deprecated** in Farseer and have no FML form; a
processor that meets one in a Farseer model reports it (`FML-E0206`) instead of
emitting it. A variable that carries `Year to date` in its grain holds, over a
`closing_state` source, a value only at `M12`.

Farseer provides every system dimension of FML §6.7 apart from `YearMonth`,
including the optional `Half years` and `Year to date`. The members of
`Versions` beyond `Actual` and `Plan` — for example `Budget`, `Forecast`,
`Q1F` — are defined in Farseer, not in a document. Farseer extends the `Years`
range one year at a time at either end.

### 6.2 Member activation

A Farseer dimension table has an `ACTIVE` column (Section 7.2). FML member files
cannot carry it: Farseer's tooling writes `true` for a new member and keeps the
value Farseer holds for an existing one, so a member is deactivated in Farseer
itself.

**[FP-10] (inactive members)** While a member's `ACTIVE` is `false`:

1. every read leaves it out — the member has no cells, `sum` drops its values,
   a filter on it and a formula reading it see nothing, and a direct read at it
   is null;
2. a write to it is refused ("No cells to update");
3. a formula that names it in qualified form (`Dim > Member`) is accepted and
   reads nothing.

Deactivation hides the member's stored values; it does not delete them.
Setting `ACTIVE` back to `true` restores them in every consumer. A model SHOULD
NOT keep data on a member it deactivates: the data vanishes from every total
without an error.

### 6.3 Compound members

A Farseer dimension table also has a `FORMULA` column. A member whose `FORMULA`
holds a member selector — `or`, `and`, `not` over members, written qualified or
not — is a **compound member**. Farseer stores the selector as sent. FML member
files cannot carry the column.

**[FP-11]** No calculation sees a compound member's selector: a filter on the
compound member and a formula reading it see nothing, a direct read at it is
null, a sum over the dimension leaves it out, and a write to it is refused.
Models SHOULD NOT rely on compound members in formulas; a combination of
members is expressed as a member selector in the `sum` filter (FML §12.6).

### 6.4 Template member files

Farseer's tooling accepts, beside a dimension's member file, a file named
`<Dimension>.template.csv`: a structure-only template for a project. When both
`<Dimension>.csv` and `<Dimension>.template.csv` exist, the tooling uses the
former and ignores the latter, and it never deletes a template file.

---

## 7. Interchange format

This section maps FML constructs to the fields of Farseer's model interchange
format, for implementers of tooling that converts between the two.

### 7.1 Variables

| FML | Interchange field | Notes |
|---|---|---|
| variable name | `name` | |
| free grain dimensions | `tables` (ordered list of dimension names) | an empty list is a measure; `YearMonth` is the two entries `Years`, `Months` (Section 6.1) |
| pinned grain entries | `members` (list of `[dimension, member]`) | a pinned dimension appears only here |
| formula | `formula` | absent formula is `null`, never `""` |
| `@type number` / `integer` / `string` / `date` / `boolean` | `dataType`: `DECIMAL` / `INTEGER` / `STRING` / `DATE` / `BOOLEAN` | |
| `@rollup` | `rollupType`: `SUM`, `AVERAGE`, `MIN`, `MAX`, `NONE`, `FORMULA`, `CLOSING STATE`, `BEGINNING STATE` | `last` → `CLOSING STATE`, `first` → `BEGINNING STATE` |
| `@format`, `@decimals`, `@numberFormat` | `numberFormat` object (FML §14) | required in full on every load (Section 8) |
| `@folder "A/B"` | `folderPath`: `["Variables", "A", "B"]` | the `Variables` root is implicit in FML |
| `@desc` | `description` | |
| `@notes` | `notes` | |
| `@readonly` | `readonly` | |
| `@active`, `@useHierarchy`, `@optimizeCalculation`, `@calculateOnDemand`, `@zConstraint` | same-named booleans | defaults `true`, `true`, `true`, `false`, `false` |
| `@numberValidation` | `numberValidation { min, max }` | |
| `@topDownMapping` | `topDownMapping` (string or null) | |

### 7.2 Dimensions and parents

| FML | Interchange |
|---|---|
| dimension declaration | table with columns `PRIMARY_KEY`, `FORMULA`, `ORDER`, `ACTIVE`, `DESCRIPTION`, and one `FOREIGN_KEY` per `@parent` |
| `@parent P` on the declaration of `C` | `FOREIGN_KEY` column on `C` with `foreignKeyTableName: P` |
| member row | `[name, formula, order, active, description, fk…]`; each FK cell a list of parent members (several only under `@parent … many`) |
| `@null` | the member row `NULL (<Dimension>)` |
| `@folder` on the declaration | table `folderPath`, rooted at `Dimensions` |
| system dimensions | never declared, and never included in the tables of a load |

### 7.3 Canonical property order and file extension

In canonical form (FML §5.6, item 4) the Farseer properties follow the
standard ones, in this order: `@active`, `@useHierarchy`,
`@optimizeCalculation`, `@calculateOnDemand`, `@zConstraint`,
`@topDownMapping`. Farseer's current tooling emits them in that order but
places the standard `@numberValidation` between `@zConstraint` and
`@topDownMapping`. FML documents use
the extension `.fml`; Farseer's tooling also reads and writes `.fsl`.

---

## 8. Implementation-defined behaviour

### 8.1 Farseer's choices

FML §2.3 requires an engine to document its choice wherever the specification
leaves a behaviour implementation-defined.

| Behaviour | FML | Farseer |
|---|---|---|
| `@numberFormat` on load | §14.1 | the model API requires the complete object on every variable and fills in nothing; Farseer's tooling sends `currency: EUR`, `unit: ONES`, `negatives: SIGNED`, `polarity: POSITIVE`, 2 decimals, `custom: false` where a document states none |
| `@numberFormat` value sets | §14.1 | closed lists: `type` `NUMBER`, `PERCENTAGE`, `CURRENCY`, `DATE`; `unit` `ONES`, `THOUSANDS`, `MILLIONS`, `BILLIONS`, `AUTO`; `negatives` `SIGNED`, `UNSIGNED`, `EXPLICIT`; `polarity` `POSITIVE`, `NEGATIVE`; `currency` from a closed set of codes (not every ISO 4217 code). A value outside these lists is refused on load; accepted values are stored as sent, and `formatString` is kept as sent rather than recomputed |
| further `@numberFormat` fields | [FMT-2] | `unit` (display scale), `negatives` (style of negative numbers) and `polarity` (whether an increase is favourable, used to colour variances), with the value sets above |
| default currency | §14.1 | `EUR`, sent by Farseer's tooling |
| `type` and entry | [FMT-1] | `type` also governs entry: a `PERCENTAGE` variable accepts `15` as `0.15` |
| further `Versions` members | [DIM-6] | defined in Farseer (Section 6.1) |
| renaming and deleting a member that formulas name | [DIM-7] | formula references are kept by identity, so renaming a member or a variable carries every formula that refers to it along. Delete a member only once no formula names it |
| a grain with a dimension and its ancestor, or an interconnected pair | [VAR-3a] | refused when the model is loaded |
| a double pin on dimensions connected by a parent | [VAR-7] | rejected as ambiguous |
| entered values in a calculated variable | [VAR-8] | supported |
| an entry at a rollup node | [EVAL-16] | accepted and spread over the node and its descendants (Section 3, [FP-3] case 5) |
| fiscal year | §6.7 | a workspace setting for the first month of the financial year; FML 1.0 models assume calendar years |
| a function of a null date | [FUN-5] | Farseer returns a value rather than null; models test a date that may be missing with `hasValue` before taking it apart, which gives the same result on every engine |
| grain entries separated by a line break without a comma | §4.9 | accepted |
| threshold for reporting dense cell production | [EVAL-31] | Farseer's model analysis estimates the cells of each variable and warns on deep formula chains, high amplification and cross-join fan-out; Farseer-aware linting reports `FML-W1502` above 10⁷ estimated cells |

### 8.2 Loading and tooling

- The grain of a variable that already holds stored values is changed only
  after those values are cleared.
- `@format currency(EUR)` and an unqualified member reference are refused on
  load (FML [PROP-6], [EXPR-8]).
- A load places a variable in the folder it states. Farseer's tooling states no
  folder for a variable without `@folder`, so that loading it leaves an
  existing variable where it is (FML [PROP-10]).
- Farseer's tooling applies defaults blocks by FML [PROP-3] when it loads a
  model, and a model read back from Farseer states every property on each
  variable, as the canonical form does (FML §5.6).
- Farseer's views show `@desc` as the row label of a variable wherever they
  show descriptions — which is why FML [PROP-11] asks authors to leave it empty.

---

## 9. Authoring agents targeting Farseer

An authoring agent whose model will be loaded into Farseer follows, in addition
to the FML Agent Authoring Protocol:

1. **MUST NOT** set `@calculateOnDemand true` on its own initiative. It MAY
   *propose* it for a long calculation chain, stating loudly what can go
   wrong — downstream variables read null until an explicit recalculation, and
   the variable cannot hold entered or imported values [FP-2] — and MAY apply it
   only on an explicit request from the model owner for that variable [FP-1].
   This is an action that requires explicit approval (FML Agent Protocol §7).
2. **MUST NOT** set `@optimizeCalculation false` except on a projection whose
   source is written by an integration (Section 2.1).
3. **MUST NOT** reference a measure, or a `@rollup formula` variable, from a
   grained formula [FP-5], [FP-7].
4. **MUST NOT** set `@active false` or `@useHierarchy false` to change what a
   variable computes [FP-9].
5. SHOULD use the standard construct where one expresses the same thing —
   `hasDMember` rather than `hasTags` — and lists, with every delivery, each
   Farseer extension the model uses [EXT-3].

Self-review (FML Agent Protocol §5) adds: no `@calculateOnDemand` without an explicit owner
request [FP-1]; no grained formula reads a measure or a `@rollup formula`
variable [FP-5], [FP-7]; no data is kept on a member that is to be deactivated
[FP-10].

---

## 10. Diagnostics and anti-patterns

A linter that checks Farseer models reports, in addition to FML Annex C (where
`FML-I0904` reports each use of a Farseer extension on request [EXT-3]), the
following. Their codes carry the prefix `FSR-`, outside the FML catalogue:

| Code | Condition | Rule | `lenient` | `standard` | `strict` |
|---|---|---|---|---|---|
| FSR-E0101 | a grained variable reads a measure | FP-5 | E | E | E |
| FSR-E0102 | a time-series function applied to a measure | FP-6 | E | E | E |
| FSR-E0103 | values written to a measure | FP-6 | E | E | E |
| FSR-W0201 | a variable reads a `@rollup formula` variable | FP-7 | W | W | E |
| FSR-W0203 | `@calculateOnDemand true` without recorded owner approval | FP-1 | W | W | E |
| FSR-W0202 | `@active false` or `@useHierarchy false` on a variable | FP-9 | I | W | W |

For Farseer targets, the `strict` profile also raises the naming rules of FML Modelling Guide
§2.1 and `@desc` set on a variable (FML §15.4) to errors: Farseer's views show
`@desc` as a row label (Section 8.2).

| # | Anti-pattern | Symptom | Remedy |
|---|---|---|---|
| FP-AP-1 | `@optimizeCalculation false` on a consumer to hide misalignment | slow, hides the defect | projection intermediate [GRAIN-3] |
| FP-AP-2 | `@calculateOnDemand true` chosen by the author; data entered into such a variable | consumers read null until it is computed; entered data replaced | opt-in only, never with data [FP-1] |
| FP-AP-3 | a formula reads a `@rollup formula` variable | reads null everywhere | compute the ratio again from its operands [FP-7] |
| FP-AP-4 | data on a member that is then deactivated | the data drops out of every total until the member is active again | move the data first, then deactivate [FP-10] |

---

## Revision history

| Version | Date | Changes |
|---|---|---|
| 1.0 | (draft) | First version. |
