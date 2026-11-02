# FML to Excel Translation

## Companion Specification — Version 1.0 (Draft)

*An open specification developed by Farseer*

| | |
|---|---|
| **Version** | 1.0 — draft |
| **Status** | Draft |
| **Companion to** | [Financial Modeling Language (FML) Specification 1.0](fml-1.0.md) |
| **Copyright** | © 2026 Farseer d.o.o., Zagreb, Croatia |
| **License** | [Creative Commons Attribution 4.0 International (CC BY 4.0)](../LICENSE) |

This companion specification is part of the Financial Modeling Language (FML)
open specification, originally developed and published by Farseer. It may be
freely used, copied, implemented, and adapted, including for commercial
purposes, provided that appropriate attribution is given to Farseer and any
modifications are clearly identified.

---

## Abstract

This document defines how an FML model is **translated into a spreadsheet
workbook** in the Office Open XML format (`.xlsx`) — a workbook in which every
computed figure is a live Excel formula, every input is an editable cell, every
dimension mapping is data in the workbook, and everything that could not be
translated is listed rather than approximated. It is written so that an
automated agent can produce such a workbook from FML documents and member files
by following it step by step, and so that a program implementing it produces
workbooks that agree with one another.

Section references of the form §11.8 or rule identifiers such as [EVAL-23]
refer to the FML Specification 1.0. Identifiers defined in this document carry
the prefix `X-`.

---

## Table of contents

1. [Purpose and scope](#1-purpose-and-scope)
2. [Conformance](#2-conformance)
3. [The fidelity principle](#3-the-fidelity-principle)
4. [Workbook structure](#4-workbook-structure)
5. [The time axis](#5-the-time-axis)
6. [Rows and coordinates](#6-rows-and-coordinates)
7. [Translating references and alignment](#7-translating-references-and-alignment)
8. [Translating filters](#8-translating-filters)
9. [Representing null](#9-representing-null)
10. [Function translation](#10-function-translation)
11. [Properties](#11-properties)
12. [Versions and the forecast flag](#12-versions-and-the-forecast-flag)
13. [What is not translated](#13-what-is-not-translated)
14. [Verification](#14-verification)
15. [Agent procedure](#15-agent-procedure)

- [Annex X-A — Template notation](#annex-x-a--template-notation)
- [Annex X-B — Translation quick reference](#annex-x-b--translation-quick-reference)
- [Annex X-C — Notes sheet entries](#annex-x-c--notes-sheet-entries)

---

## 1. Purpose and scope

### 1.1 Purpose

An FML model is written once and holds at every coordinate of every grain. A
spreadsheet is written cell by cell. Translating the first into the second
lets a model be read, checked and shared by anyone with a spreadsheet program,
lets a reviewer trace a figure to its inputs by clicking, and gives an
independent second computation of the model's numbers.

### 1.2 Scope

This document defines:

- the sheets, rows and columns of a translated workbook;
- how variable references, alignment, parents and filters become cell
  references and lookup formulas;
- the translation of every function of FML 1.0 §12, and of the functions of
  the Farseer Implementation Profile (§10.4), since Farseer models use them;
- how null, properties, versions and the forecast flag are represented;
- what must be listed instead of translated;
- how a translated workbook is verified;
- a procedure for agents.

This document does not define:

- translation in the other direction (workbook to FML);
- presentation sheets designed for reading — statements laid out as a report.
  A renderer MAY add them, built only from references to the sheets defined
  here;
- spreadsheet formats other than `.xlsx`, although the formulas are
  intentionally restricted to functions that common spreadsheet programs share.

### 1.3 The excerpt of the model

A workbook renders a **finite excerpt** of a model: a chosen version, a chosen
range of periods, and the members that the member files list. Everything
outside the excerpt is absent from the workbook and is stated as such on the
`Notes` sheet.

---

## 2. Conformance

The key words of BCP 14 (RFC 2119, RFC 8174) apply as in FML 1.0 §2.1.

| Class | A conforming member of this class… |
|---|---|
| **Translated workbook** | has the structure of Section 4, translates every translatable variable as specified, and lists every other variable on its `Notes` sheet (§13). |
| **Renderer** | is a program or an agent that produces translated workbooks from FML documents and member files, and performs the verification of Section 14. |

A renderer MAY support only a subset of FML. Every variable outside its subset
MUST be rendered without a formula and listed (§13). A renderer that silently
approximates a formula is not conforming, whatever else it does.

---

## 3. The fidelity principle

**[X-FID-1]** A translated workbook reconstructs the **values** that the FML
semantics define for the model, at the coordinates it renders. It does not
reconstruct the engine's **behaviour**.

The difference matters, and the `Notes` sheet MUST state it:

| The engine | The workbook |
|---|---|
| creates a cell only where an operand anchors it [EVAL-4] | always has a cell; null is represented explicitly (§9) |
| may hold a cell at a rollup node of a tree [EVAL-16] | shows a rollup node as the sum of its children (§13) |
| evaluates a measure (a Farseer extension) in the reader's context | evaluates a measure at the coordinates the renderer chooses (§13) |
| recomputes asynchronously; Farseer may defer `@calculateOnDemand` variables (an extension) | recomputes on every change |

**[X-FID-2]** A renderer MUST apply the normative rules of FML 1.0 Section 11
when it translates — in particular alignment [EVAL-7]–[EVAL-9], projection and
lookup through parents [EVAL-13], [EVAL-14], the filter rule [EVAL-23] and the
pin rule [EVAL-18]. A workbook that applies spreadsheet intuition instead (a
`SUMIF` that intersects where FML broadcasts) computes a different model.

**[X-FID-3]** Where FML 1.0 leaves a behaviour *implementation-defined*, the
renderer applies the choice of the target engine's implementation profile and
lists the assumption on the `Notes` sheet (Annex X-C).

**[X-FID-4]** Because a workbook always has somewhere to write, it cannot show
the defects that come from cells not existing — a probe made of literals, a
default taken through `hasValue`, a cash-flow walk with no cells. A workbook
that agrees with its own formulas proves the translation, not the model. Only a
comparison with values computed by an engine (§14.4) tests the model.

---

## 4. Workbook structure

### 4.1 Sheets

**[X-WB-1]** A translated workbook contains the following sheets, in this order:

| # | Sheet | Content |
|---|---|---|
| 1 | `Notes` | what the workbook is, the excerpt (§1.3), the fidelity statement (§3), every assumption and every untranslated variable (Annex X-C) |
| 2 | `Dimensions` | one member block per non-system dimension: members, descriptions and foreign-key columns (§4.3) |
| 3 … n | one sheet per **block** | the variables of the block, laid out as in §5 and §6 |
| last | `Source` | the FML documents verbatim, one document after another, each under its file name |

A **block** is a top-level folder of the model (the first segment of `@folder`)
or, for variables without a folder, the document in which they are declared.
Sheet names are the block names, truncated to 31 characters with the
characters `\ / ? * [ ] :` replaced by `_`, and made unique.

Block sheets SHOULD follow the order of the model's pipeline: foundation,
imports, inputs, calculations, outputs, controls (FML Modelling Guide §1.2).

### 4.2 Names

**[X-WB-2]** The renderer MUST define these workbook-level names:

| Name | Refers to |
|---|---|
| `dim_<Dimension>` | the member column of the dimension's block on `Dimensions` |
| `fk_<Child>_<Parent>` | the foreign-key column from `<Child>` to `<Parent>` on `Dimensions` |
| `period_year`, `period_month` | the year and month header rows of the block sheets' period columns (§5.1) |

Dimension names are made valid Excel names by replacing every character other
than letters, digits and `_` with `_`.

### 4.3 The `Dimensions` sheet

**[X-WB-3]** Each non-system dimension is rendered as a block of columns: the
member name, the description, and one column per foreign key, in the order of
the member file (FML 1.0 §6.4). A multi-parent foreign-key cell is rendered as
one row per parent, with the member name repeated, and the `Notes` sheet states
that the dimension has multi-parent members.

**[X-WB-4]** Foreign-key cells SHOULD carry a data-validation list whose source
is the parent dimension's `dim_<Parent>` name, so that a reader can change a
mapping in the workbook and see every figure that reads through the parent move
(§8.2). The `Notes` sheet states that a mapping changed in the workbook does
not travel back to the model.

### 4.4 Block sheets

A block sheet has two header rows, then the variables of the block in
declaration order, each preceded by a label row:

```text
     A               B          C          D …        P          Q …
1    <block name>
2    Variable        Account    CostCenter 2026       2027 …                (year row)
3                                          12         01  02 … 12   01 …    (month row)
4    PL Plan Pre Tax                                                         (label row)
5    PL Plan Pre Tax 4000       CC100      =…         =…  =…
6    PL Plan Pre Tax 5000       CC200      =…         =…
```

- Column A holds the variable name on every row of the variable.
- **Key columns** follow, one per non-time dimension used by any variable of
  the sheet, in a fixed order: the order of first appearance in the grains of
  the sheet's variables. A row leaves blank the key columns of dimensions its
  variable does not carry.
- **Period columns** follow the key columns (§5).
- **Helper columns** (§8.2) follow the period columns, separated by one empty
  column, and are hidden.

---

## 5. The time axis

### 5.1 Period columns

**[X-TIME-1]** The `YearMonth` members of the excerpt are rendered as
**contiguous** columns, one per period, in calendar order across year
boundaries. Row 2 holds the `Years` member each column belongs to (`2027`) and
row 3 its `Months` member (`01` … `12`), so that a column is read as the
intersection of the two (FML 1.0 §6.7): the column of `"2027-03"` shows `2027`
over `03`. No total column interrupts the months.

Contiguity is what lets a shift by `n` periods be a column offset by `n`
([`delay`], §10.3) and a running total be a reference to the previous column
([`cumsum`]).

**[X-TIME-2]** If the model enters opening balances in a period before the
first period of interest (FML 1.0 Annex F enters them in the month before the
first plan month), that period is rendered as the first period column, labelled
with its real year and month. It is a period like any other, not a special
"Opening" column.

### 5.2 Year totals

**[X-TIME-3]** Year totals are rendered in a separate block of columns to the
right of the last period column, one column per year of the excerpt. The
total of a variable's row for a year is derived from the variable's `@rollup`
(FML 1.0 [PROP-4], [EVAL-28]):

| `@rollup` | Year total |
|---|---|
| `sum` | `SUM` of the year's month cells |
| `closing_state` | the year's **last** month cell |
| `beginning_state` | the year's **first** month cell |
| `average` | `AVERAGE` of the year's month cells that are not null |
| `min`, `max` | `MIN`, `MAX` of the year's month cells |
| `formula` (Farseer extension) | the variable's formula translated with every operand replaced by its own year total |
| `none` | empty |

A year that is only partly in the excerpt is totalled over the months present,
and its header says *partial*.

A variable of `@type date` has **no** year total when its rollup is `sum` or
`average`: a sum or a mean of dates is not a date, and a spreadsheet cannot
display the result.

### 5.3 Variables without months

A variable whose time dimension is `Years` is rendered with one value per year,
written in **every** month column of that year: the first month holds the value
(an input, or the formula), and the other months reference the first. A
variable whose time dimension is `Months` — a seasonal profile — holds its
value in the first column of each month of the year, and the same month of
every later year references it. A variable without a time dimension is
rendered in every period column, all referencing the first. This makes broadcast to months [EVAL-9] an ordinary
same-column reference everywhere else in the workbook.

### 5.4 Period context

The context functions of FML 1.0 §12.5 read the header rows:

| FML | Excel |
|---|---|
| `currentYear()` | `VALUE(<col>$2)` |
| `currentMonth()` | `VALUE(<col>$3)` |
| `currentDate()` | `DATE(currentYear, currentMonth, 1)` |
| `daysInCurrentMonth()` | `DAY(EOMONTH(currentDate, 0))` |

A renderer SHOULD add two hidden header rows holding these as numbers and
reference them, rather than re-parsing the labels in every formula.

---

## 6. Rows and coordinates

### 6.1 One row per coordinate

**[X-ROW-1]** A variable is rendered as one row per **coordinate of its
non-time grain** — one combination of members of its grain dimensions other
than `Versions` and its time dimension. A pinned dimension [VAR-5] is a key
column holding the pinned member on every row of the variable.

**[X-ROW-2]** The renderer chooses which coordinates to render:

- for an **input or import** variable, the coordinates that hold data in the
  excerpt, or — when the workbook is a template without data — every
  combination of members listed in the member files, excluding NULL members;
- for a **calculated** variable, the coordinates at which the FML semantics
  produce a cell for the rendered data (the anchoring rule [EVAL-4] applied to
  the operands' rendered rows — under FML 1.0 [EVAL-4a], only the rows of the
  references that carry the whole grain when there are any), plus, for a
  template, every combination that any operand could produce.

**[X-ROW-3]** A variable with no non-time dimension is rendered as one row.

### 6.2 Size

**[X-ROW-4]** If a variable's rows would exceed 100 000, or its rendered grid
would exceed 10 million cells, the renderer MUST NOT render it; it lists it as
untranslated with its estimated cell count (FML 1.0 [EVAL-31]). A spreadsheet has
1 048 576 rows and 16 384 columns, and is unusable long before.

### 6.3 Measures (Farseer extension)

A measure — a variable with an empty grain, a Farseer extension (FML 1.0 §8.3,
Farseer Implementation Profile) — has no coordinates of its own. It is rendered as one
row on the sheet of its block, evaluated over the whole excerpt for each period
(every `sum(…)` of its formula becomes the sum of the operand's whole block for
that column). The `Notes` sheet states that the measure is shown at the total
level only.

---

## 7. Translating references and alignment

### 7.1 Notation

Templates in this document use the notation of Annex X-A:

| Notation | Means |
|---|---|
| `⟦V⟧` | the cell of variable `V` in the **same period column**, at the row of `V` whose key columns match the current row's keys on the dimensions `V` carries |
| `⟦V⟧ₜ₋ₖ` | the same, `k` period columns to the left |
| `⟨V⟩` | the period column range of all rows of `V`, in the current column |
| `⟨V.D⟩` | the key column range of dimension `D` over all rows of `V` |
| `⟨V.D→P⟩` | the helper column range holding, for each row of `V`, the member of `P` that its `D` member reaches (§8.2) |
| `$D` | the current row's key cell for dimension `D` |

A renderer writes real cell addresses. The notation exists so that this
document can state each rule once.

### 7.2 The four cases

For an operand `V` in the formula of `T` (FML 1.0 §11.4–§11.6), compare `V`'s
non-time grain `G(V)` with `T`'s `G(T)`.

**[X-REF-1] Aligned** — `G(V)` = `G(T)`. The operand is a direct reference to
`V`'s row with the same keys:

```text
⟦V⟧                         e.g.  ='Revenue'!F12
```

**[X-REF-2] Broadcast** — `G(V)` ⊂ `G(T)`, and no dimension of `T` is reached
from `V` (FML 1.0 [EVAL-9]). The operand is a direct reference to the row of `V`
whose keys match the current row on the dimensions `V` carries. Because the
renderer knows both layouts, it writes the address directly:

```text
"Sales Revenue" { Product, … } * "FX Rate IN" { … }      →   =F12*Inputs!F7
```

**[X-REF-3] Aggregation** — `V` carries dimensions that `T` does not carry
(directly, or because `V`'s dimension is a child of `T`'s through parents,
[EVAL-8], [EVAL-13]). The operand is the aggregate of `V`'s rows that match the
current row, under `V`'s `@rollup`:

| `V`'s `@rollup` along non-time dimensions | Template |
|---|---|
| `sum`, `closing_state`, `beginning_state` (these sum along non-time dimensions, FML 1.0 [PROP-4]) | `SUMIFS(⟨V⟩, criteria…)` |
| `average` | `AVERAGEIFS(⟨V⟩, criteria…)` |
| `min`, `max` | `MINIFS`, `MAXIFS` |

with one criterion per dimension of `T`:

- `⟨V.D⟩, $D` where `V` carries `D` itself;
- `⟨V.C→D⟩, $D` where `V` carries a child `C` of `D` (a helper column, §8.2).

```text
"PL Plan at PLLine" { PLLine, CostCenter, … } = "PL Plan IN"   # PL Plan IN { Account, CostCenter, … }
→  =SUMIFS(⟨PL Plan IN⟩, ⟨PL Plan IN.Account→PLLine⟩, $B9, ⟨PL Plan IN.CostCenter⟩, $C9)
```

**[X-REF-4] Lookup** — `T` carries a child `C` of a dimension `P` that `V`
carries (FML 1.0 [EVAL-14]). The operand is `V`'s value at the parent of the
current row's `C` member; for a multi-parent member, the sum over its parents:

```text
"Cost of Goods Sold" { Product, … } = "Sales Revenue" * "COGS Rate IN"   # COGS Rate IN { ProductGroup, … }
→  =⟦Sales Revenue⟧*SUMIFS(⟨COGS Rate IN⟩, ⟨COGS Rate IN.ProductGroup⟩, ⟨parent of $B12 in ProductGroup⟩)
```

where `⟨parent of $B12 in ProductGroup⟩` is `XLOOKUP($B12, dim_Product,
fk_Product_ProductGroup)` — or, preferably, a helper column on `T`'s rows
(§8.2).

The cases combine: an operand can be aggregated over one dimension and looked
up through another. The renderer then writes one `SUMIFS` whose criteria cover
every dimension of `T`.

### 7.3 Pinned variables

**[X-REF-5]** A pinned variable [VAR-5] has its pinned dimension as a key column
holding the pinned member. As an operand it is aligned on that dimension:
`SUMIFS` criteria on the pinned dimension match only the pinned member, so a
collector of pinned transfer variables (FML 1.0 §11.5) becomes a sum of
`SUMIFS` terms each of which is non-zero only on its own member.

**[X-REF-6]** Inside a pinned variable, every operand that carries the pinned
dimension is aggregated over **all** its members — the pin writes, it does not
read [EVAL-18]. The renderer MUST NOT add a criterion for the pinned dimension
to such an operand.

### 7.4 Inputs and imports

**[X-REF-7]** Input and import variables are rendered as constant cells: the
data of the excerpt, or blank in a template. Their cells are **unlocked** and
styled as inputs (§11.3). A calculated variable whose `@readonly` is false and
that the excerpt shows with entered values (FML 1.0 [VAR-8]) is rendered with
the entered values as constants in those cells and the formula elsewhere; the
`Notes` sheet lists the cells.

---

## 8. Translating filters

### 8.1 Own grain versus through a parent

**[X-FIL-1]** A filter `sum(X, D > m)` in the formula of `T` is translated
according to FML 1.0 [EVAL-23]:

| Where `D` is | Translation |
|---|---|
| in `T`'s own grain | `SUMIFS(⟨X⟩, ⟨X.D⟩, "m", other criteria…)` — **no** criterion matching `D` to the current row. The result is the same on every member of `D`: a broadcast. |
| reached from `T`'s grain through a parent (from `T`'s dimension `C`) | `SUMIFS(⟨X⟩, ⟨X.C→D⟩, "m", ⟨X.C⟩, $C, other criteria…)` — the current row's `C` member is kept as a criterion, so the result is this row's slice. |
| neither in `T`'s grain nor reached from it | `SUMIFS(⟨X⟩, ⟨X.D⟩ or ⟨X.E→D⟩, "m", other criteria…)` — a plain filtered aggregate. |

"Other criteria" are the alignment criteria of [X-REF-3] for every other
dimension of `T`.

```text
"PL Gross Profit" { Account, CostCenter, … } =
    sum("PL OUT", PLLine > "Operating revenue") - sum("PL OUT", PLLine > "Cost of sales")

→  =SUMIFS(⟨PL OUT⟩, ⟨PL OUT.Account→PLLine⟩, "Operating revenue", ⟨PL OUT.Account⟩, $B14, ⟨PL OUT.CostCenter⟩, $C14)
   -SUMIFS(⟨PL OUT⟩, ⟨PL OUT.Account→PLLine⟩, "Cost of sales",     ⟨PL OUT.Account⟩, $B14, ⟨PL OUT.CostCenter⟩, $C14)
```

**[X-FIL-2]** Several filters add several criteria. Two filters on different
members of one dimension produce two criteria on the same range, which no row
satisfies: the result is null, as in FML [EVAL-21].

**[X-FIL-3]** A filter on a member that has descendants in a tree includes the member and all its descendants [EVAL-22]. The renderer
adds a helper column holding, for each row, the **path** of ancestors of its
member (`|Total assets|Current assets|Cash|`), and translates the filter as a
wildcard criterion on that column: `"*|Current assets|*"`.

The path of each member is computed on the `Dimensions` sheet from the
**parent** column only, by nesting one lookup per level of the tree
(`"|"&XLOOKUP(XLOOKUP(m,…),…)&"|"&XLOOKUP(m,…)&"|"&m&"|"`), to the depth of the
deepest member. A path column that looks up its own column is a circular
reference.

**[X-FIL-4]** A member selector as a filter — `sum(X, or(Region > East, Region >
Adriatic))` — is the sum of one `SUMIFS` per member for `or`;
for `and` over different dimensions, one `SUMIFS` with both criteria; for
`not(D > m)`, a criterion `"<>m"`.

### 8.2 Helper columns

**[X-FIL-5]** For every parent `P` of a dimension `C` that a translation reads
through, the renderer adds a hidden helper column to the rows of each variable
carrying `C`, holding the member of `P` that the row's `C` member reaches:

```text
=XLOOKUP($B5, dim_Account, fk_Account_PLLine, "")
```

For a parent chain `C -> P -> G`, the helper holds the end of the chain, nesting the
lookups. Because helpers read the `Dimensions` sheet, changing a mapping there
moves every figure that reads through it (§4.3).

**[X-FIL-6]** The renderer SHOULD NOT inline `XLOOKUP` inside `SUMIFS`
criteria; a criterion range must be a range, and helper columns keep formulas
readable and fast.

### 8.3 `hasDMember`

**[X-FIL-7]** `hasDMember(D > m)` is translated as a test of the current row:

| Where `D` is | Translation |
|---|---|
| in `T`'s grain | `$D="m"` |
| reached through a parent from `T`'s `C` | `<helper C→D of the current row>="m"` |
| a tree (subtree) | `ISNUMBER(SEARCH("|m|", <path helper>))` |
| `Versions` | resolved statically for the rendered version (§12): `TRUE` or `FALSE` |
| `Months`, `Years` | `<col>$3="m"`, `<col>$2="m"` |
| `YearMonth` | both rows: `"2027-03"` is `AND(<col>$2="2027",<col>$3="03")` |

Several arguments are combined with `AND`.

---

## 9. Representing null

### 9.1 The rule

**[X-NULL-1]** Null is represented by an **empty-string result** (`""`) in a
formula cell and by an **empty cell** among constants. Zero is `0`. The two
MUST NOT be conflated by the renderer: a translated formula that yields `0`
where FML yields null is a defect.

**[X-NULL-2]** Because `""` is text, arithmetic on a cell that may hold `""`
fails in a spreadsheet. The renderer therefore emits the null-faithful forms of
FML 1.0 [EVAL-11]:

| FML | Excel template |
|---|---|
| a reference `x` alone (the whole formula, or a branch of `if`) | `IF(ISNUMBER(x),x,"")` — a reference to an empty cell yields `0` in a spreadsheet, not null |
| `a + b`, `a - b` | `IF(COUNT(a,b)=0,"",N(a)+N(b))` (with `-` for subtraction) |
| `a * b` | `IF(COUNT(a,b)<2,"",a*b)` |
| `a / b` | `IF(OR(COUNT(b)=0,N(b)=0),"",N(a)/b)` — a null numerator over a value is `0` (FML 1.0 [EVAL-11]) |
| `if(c, a)` | `IF(c,a,"")` |

`COUNT` counts numbers only, so it is 0 for a reference to `""` or to an empty
cell. Three refinements keep the forms correct and short:

- **Sums are n-ary.** A chain `a + b - c + …` is one formula,
  `IF(COUNT(a,b,c,…)=0,"",N(a)+N(b)-N(c)…)`, never nested pairwise; nesting
  repeats every operand inside every guard and grows exponentially.
- **A literal term is never null.** If a sum contains a literal (`1 - x`), it
  has no null guard: `1 - x` is `1` where `x` is empty (FML 1.0 [EVAL-11a]).
- **An operand with no row is null as a constant.** It is dropped from a sum,
  and it makes a product `""`. The renderer never writes `""` as an operand of
  `N()` or arithmetic. The forms compose: an inner product is itself an argument of an outer
`COUNT`, which counts it when it is a number and not when it is `""`. Longer sums generalise: `IF(COUNT(a,b,c)=0,"",N(a)+N(b)-N(c))`.

**[X-NULL-3]** A renderer MAY instead declare the **simplified profile** —
null treated as zero throughout, with plain `+ - * /` — if it states so in the
first lines of the `Notes` sheet. A simplified workbook reproduces totals but
not the distinction between null and zero; it SHOULD be used only for models
that are dense in practice.

**[X-NULL-4]** `SUMIFS`, `AVERAGEIFS`, `MINIFS` and `MAXIFS` ignore text, so
`""` cells drop out of aggregates as nulls do in FML. A `SUMIFS` that matches no
number returns `0`; where FML would produce no cell (no matching operand row
has a number), the renderer wraps it:
`IF(COUNTIFS(⟨V.D⟩,…,⟨V⟩,"<>")=0,"",SUMIFS(…))` — or, in the simplified
profile, leaves it.

### 9.2 Anchoring

**[X-NULL-5]** A renderer applies the anchoring rule [EVAL-4] when it chooses
the rows of a calculated variable ([X-ROW-2]): a row at which no value-position
operand has a cell is not rendered at all. Within a rendered row, a period cell
at which no value-position operand has a number is `""`: the whole formula is
wrapped in `IF(COUNT(<its placing references>)=0,"",…)`. The placing
references are those that carry the whole output grain, when the formula has
any; otherwise every value-position reference (FML 1.0 [EVAL-4a]). This guard
is applied once, to the whole formula — not to sub-expressions, which follow the
arithmetic of §9.1.

When the formula is an `if` with a literal output and exactly one variable in
its condition, the rows and cells come from that variable (FML 1.0 [EVAL-5]):
`if(hasValue("Price Curve"), 1)` has a row for every item that has a curve. A literal-only formula
therefore renders as **no rows**, and the `Notes` sheet says why
(Annex X-C, `NO-CELLS`).

---

## 10. Function translation

The tables use `x`, `a`, `b` for translated operands and `c` for the current
period column. Every function of FML 1.0 §12 is listed. **Level** is one of:

- **direct** — an Excel function with the same meaning;
- **template** — a formula pattern defined here;
- **partial** — translated under a stated assumption, listed on `Notes`;
- **none** — not translated; the variable is listed (§13).

### 10.1 Mathematical

| FML | Level | Excel |
|---|---|---|
| `round(x, d)` | direct | `ROUND(x, d)` |
| `floor(x)` | direct | `INT(x)` (rounds toward minus infinity, as `floor`) |
| `ceil(x)` | direct | `-INT(-x)` |
| `abs(x)` | direct | `ABS(x)` |
| `power(b, e)` | direct | `POWER(b, e)` |
| `max(a, b)` | template | `IF(COUNT(a,b)=0,"",MAX(a,b))` |
| `min(a, b)` | template | `IF(COUNT(a,b)=0,"",MIN(a,b))` |

`MAX` and `MIN` ignore text, so a null argument is skipped, as in FML (FML 1.0
§12.1).

### 10.2 Aggregation

| FML | Level | Excel |
|---|---|---|
| `sum(x)` | template | §7.2 [X-REF-3] |
| `sum(x, filters…)` | template | §8.1 |
| `avg(x, n)` | template | `SUM(⟦x⟧ₜ₋ₙ : ⟦x⟧ₜ₋₁)/n` — the `n` columns before `c`, a value (possibly `0`) in every column that has a window (FML 1.0 §12.2); columns before the first period count as null |
| `avg(x, n, 1)` | template | `IF(COUNT(w)=0,"",SUM(w)/(n+1-MATCH(TRUE,INDEX(ISNUMBER(w),0),0)))` with `w` = `⟦x⟧ₜ₋ₙ : ⟦x⟧ₜ₋₁` — the divisor counts the window from its first populated column (FML 1.0 §12.2), not the populated columns |

`n` MUST be a literal for translation; a variable window is **partial** (the
renderer evaluates it per column and writes the range it implies).

### 10.3 Accumulation and time shift

| FML | Level | Excel, in period column `c` |
|---|---|---|
| `cumsum(x)` | template | first column: `x`; later: `IF(COUNT(⟦self⟧ₜ₋₁,x)=0,"",N(⟦self⟧ₜ₋₁)+N(x))` |
| `cumsum(x, f)` | template | later columns: `N(⟦self⟧ₜ₋₁)*(1+f*)+N(x)`, null-wrapped as above, where the factor carries forward (FML 1.0 §12.3): `f*` = `IFERROR(LOOKUP(9.99E+307,⟦f⟧₀ : ⟦f⟧ₜ),0)`, the last number in the factor's row up to `c`; a literal factor is used as is |
| `cumsum(x, f, s)` | template | `IF(ISNUMBER(s), s, <the cumsum(x, f) form>)` |
| `delay(x, n)`, `n` a whole number | template | `⟦x⟧ₜ₋ₙ`; `""` where `c − n` is before the first period |
| `delay(x, n)`, `n` fractional | template | as a whole number, with `n` rounded half up, towards +∞ (`INT(n+0.5)`, so −2.5 becomes −2; FML 1.0 §12.3) — `ROUND` rounds a half away from zero and MUST NOT be used |
| `spread(x, n, d)` | template | `SUM(⟦x⟧ₜ₋ₙ₋ᵈ₊₁ : ⟦x⟧ₜ₋ᵈ)/n`, the range clipped at the first period |

`⟦self⟧ₜ₋₁` is the variable's own cell in the previous column. **[X-FN-1]** A
`cumsum` that is not the whole formula of its variable MUST be translated by
introducing a hidden helper row for the accumulated series, named
`<variable> · cumsum`, and referencing it.

**[X-FN-2]** Year boundaries: because months are contiguous ([X-TIME-1]),
`delay` and `cumsum` carry values from December into January, as FML 1.0
[FUN-2] specifies. The renderer still lists `DELAY-YEAR` whenever a model uses
`delay` or `cumsum` over more than one year; under FML 1.0 the entry records
specified behaviour, not an assumption.

**[X-FN-3]** Arguments other than the first (window lengths, shifts, rates) are
translated when they are literals. When they are variables, the translation is
**partial**: the renderer evaluates the argument per column and writes the
resulting offsets, and lists the variable (`VARIABLE-ARG`).

### 10.4 Farseer extensions

`spread_days` and the growth functions are not part of FML; they are Farseer
extensions (FML 1.0 §2.5, Farseer Implementation Profile §5). They are
translated here because Farseer models use them. `spread_days` distributes over
days; growth functions extend values **entered** in the excerpt (FML 1.0
[VAR-8]).

| FML | Level | Excel |
|---|---|---|
| `spread_days(x, n, d)` | partial | per-month day shares computed by the renderer and written as a weighted `SUMPRODUCT` of earlier columns |
| `mom(p)` | template | entered cells as constants; every later cell `IF(COUNT(⟦self⟧ₜ₋₁)=0,"",⟦self⟧ₜ₋₁*(1+p))` |
| `qoq(p)` | template | entered cells as constants; a cell every third month after the last entered one, `⟦self⟧ₜ₋₃*(1+p)`; `""` in between |
| `yoy(p)` | template | as `qoq`, every twelfth month, `⟦self⟧ₜ₋₁₂*(1+p)` |
| `predictAverage(x)` | partial | entered cells as constants; every other cell `AVERAGE` of `x` over the earlier periods without an entered value, written as an explicit list of those cells. A value typed into the workbook later is not recognised as "entered" (`ENTERED-ONLY`). |

### 10.5 Logic and comparison

| FML | Level | Excel |
|---|---|---|
| `if(c, a)` | template | `IF(c, a, "")` |
| `if(c, a, b)` | template | `IF(c, a, b)` — where `c` may be null, see below |
| `eq(a, b)` … `lte(a, b)` in a condition | direct | `a=b`, `a>b`, `a>=b`, `a<b`, `a<=b`; where both operands may be null, `eq`, `gte` and `lte` become `AND(COUNT(a,b)>0, N(a)=N(b))` etc. — two nulls compare false (FML 1.0 [EVAL-26]) |
| comparison in value position | template | `--(N(a)>N(b))`, with the both-null form above: 1 or 0, never null; the anchoring guard of [X-NULL-5] decides whether the cell exists (FML 1.0 [EVAL-6], [EVAL-26]) |
| `and`, `or`, `not` in a condition | direct | `AND`, `OR`, `NOT` |
| `and`, `or` in value position | template | `IF(COUNT(a,b,…)=0,"",--AND(…))` — null where every operand is null; `not` as `--NOT(…)`, `1` for a null operand (FML 1.0 [EVAL-26]) |
| `hasValue(x)` | direct | `ISNUMBER(x)` in a condition; `IF(ISNUMBER(x),1,"")` in value position (1 or null, FML 1.0 [EVAL-6]) |
| `hasDMember(…)` | template | §8.3 |

**[X-FN-4]** A null operand of a condition reads as `0`, so a condition whose
operands may be null is translated with each operand wrapped in `N(…)` —
`IF(N(a)>N(b), …)` — and a null `hasValue` is false (FML 1.0 [EVAL-25],
[EVAL-26]). Whether the cell exists is decided by the anchoring guard of
[X-NULL-5], not by the condition. A renderer MAY omit `N(…)` when every operand
is known to be non-null at that cell.

### 10.6 Dates

| FML | Level | Excel |
|---|---|---|
| `date(y, m, d)` | template | `DATE(y, m, d)`, each argument that may be fractional wrapped in `ROUND(…, 0)` — FML rounds, `DATE` truncates |
| `edate(d, n)` | direct | `EDATE(d, n)` |
| `year(d)`, `month(d)`, `day(d)` | direct | `YEAR`, `MONTH`, `DAY` |
| `currentDate()` … `daysInCurrentMonth()` | template | §5.4 |

Date serial numbers in FML use the same 1900 date system as Excel, so date
values need no conversion. The workbook MUST use the 1900 date system. `DATE`
rolls out-of-range months and days over as FML's `date` does. A function of a
null date is null (FML 1.0 [FUN-5]); the translation keeps it null.

### 10.7 Member selectors

Member selectors in a `sum` filter (FML 1.0 §12.6) are translated by
expanding the selector (§8.1 [X-FIL-4]). Compound members are a Farseer
extension (Farseer Implementation Profile §6.3); member files cannot carry them,
so a renderer does not see them.

---

## 11. Properties

### 11.1 Number formats

**[X-PROP-1]** Each period cell of a variable carries the number format derived
from its properties:

| FML | Excel number format |
|---|---|
| no format property | `#,##0.00` |
| `@format percentage` | `0.00%` (the value is the ratio, [PROP-7]) |
| `@format currency` | `#,##0.00` with the currency symbol of `@numberFormat.currency`, if given |
| `@format date` | `yyyy-mm-dd` |
| `@decimals n` | the decimal part adjusted to `n` places |
| `@numberFormat { formatString: "…" }` | `formatString` as given — it is already a spreadsheet format |

### 11.2 Text properties

`@notes` becomes a cell comment on the variable's label row. `@desc`, if
present, becomes the label row's text after the variable name. `@folder`
decides the sheet (§4.1).

### 11.3 Inputs and protection

**[X-PROP-2]** Cells of input and import variables are unlocked and filled with
a light input colour; every other cell is locked. The renderer SHOULD NOT turn
on sheet protection (the reader decides), but MUST make the distinction
visible.

### 11.4 Flags with no spreadsheet meaning

The Farseer extensions `@active`, `@useHierarchy`, `@calculateOnDemand`,
`@optimizeCalculation`, `@zConstraint` and
`@topDownMapping` have no spreadsheet equivalent; a variable that carries one
is rendered normally. A variable with `@calculateOnDemand true` is also listed
(`ON-DEMAND`), because in the engine its consumers read null until it is
explicitly computed.

---

## 12. Versions and the forecast flag

**[X-VER-1]** A workbook renders **one** `Versions` member, the **rendered
version**, named on the `Notes` sheet. `Versions` is not a key column.

- Inputs carrying `Versions` take the rendered version's values.
- Variables without `Versions` (imported actuals) are rendered as they are;
  they broadcast to the rendered version.
- `hasDMember(Versions > Actual)` is `TRUE` if the rendered version is
  `Actual` and `FALSE` otherwise, written as a literal.
- Forecast flags (`"FC Actual IN"`) are inputs like any other: a row of 1 and
  empty cells over the periods. The merge pattern of FML 1.0 [VER-4] then
  translates mechanically.

**[X-VER-2]** A renderer MAY render several versions as several workbooks, or
as several copies of the block sheets suffixed with the version name. It MUST
NOT mix versions on one row.

---

## 13. What is not translated

**[X-NT-1]** A variable is rendered **without a formula**, with its rows and its
input-style cells left empty, and listed on the `Notes` sheet with a reason
code (Annex X-C), when:

- it uses a function at level **none**, or a form the renderer does not
  support;
- it references a variable that is not translated (the reason propagates to
  every dependent, and each dependent is listed);
- its size exceeds [X-ROW-4];
- its time dimension is declared `@semantic time` (FML 1.0 §6.9): the
  workbook's period columns are `YearMonth`.

**[X-NT-2]** The following are translated with a **listed assumption** rather
than refused:

| Construct | Assumption | Code |
|---|---|---|
| a tree in a calculated variable's grain | rollup nodes show the sum of their children; the engine may also hold a cell of its own there [EVAL-16] | `ROLLUP-NODE` |
| a test against a NULL member through a parent | the NULL member is read like any other member; members with an empty key sit in it (FML 1.0 [EVAL-15], [EVAL-17]) | `NULL-THROUGH-PARENT` |
| `delay` / `cumsum` across years | values carry across year boundaries (specified by FML 1.0 [FUN-2]) | `DELAY-YEAR` |
| a measure | evaluated at the total of the excerpt | `MEASURE-TOTAL` |
| a variable argument to a time function | evaluated per column | `VARIABLE-ARG` |
| `predictAverage` | only cells entered in the excerpt count as entered | `ENTERED-ONLY` |
| `@calculateOnDemand true` | computed normally in the workbook | `ON-DEMAND` |
| a multi-parent foreign key | rendered as one row per parent | `MULTI-PARENT` |

**[X-NT-3]** Nothing is approximated silently. If a renderer is unsure whether
a translation is exact, it lists the variable.

---

## 14. Verification

A renderer MUST verify every workbook it produces. Verification has four
levels; the first two are mandatory, the third is recommended, and the fourth
is performed whenever engine values are available.

### 14.1 The workbook is well-formed

1. The file opens in a spreadsheet program, or in a reader that does not
   recalculate, without error.
2. Every formula cell carries a **cached value** — the result of evaluating it
   — so that readers that do not recalculate show numbers, not blanks. The
   workbook is also marked for full recalculation on open.
3. No formula evaluates to an error (`#VALUE!`, `#REF!`, `#DIV/0!`, `#N/A`).
4. Every defined name of [X-WB-2] resolves.

### 14.2 The workbook agrees with itself and with the model's controls

1. Every control variable of the model (FML Modelling Guide §7) evaluates to its passing
   value in every rendered period — and the **positions** it checks are
   populated: balance-sheet lines, totals and cell counts are non-empty
   [TEST-1]. A control reading zero over an empty sheet is a failure.
2. Every conservation invariant the model states (allocation totals, collector
   totals) holds.
3. Independently computed expectations, where the model or its documentation
   provides them, match.

### 14.3 Two independent evaluations

The values checked at levels 14.1 and 14.2 SHOULD be computed twice, by two
independent evaluators — a spreadsheet program and an independent formula
evaluator — and both SHOULD pass. They disagree on edge cases a single one
hides (a function one of them does not implement, text arithmetic, a circular
reference one of them tolerates).

### 14.4 The workbook agrees with an engine

When values computed by an engine for the same model, version, periods and
data are available, the renderer compares them cell by cell and reports four
counts:

| Bucket | Meaning |
|---|---|
| **MATCHES** | the workbook reproduces the engine's value |
| **DIFFERS** | a different number — always a finding. A difference at a rollup node is reported separately (`ROLLUP-NODE`). |
| **ENGINE ONLY** | the engine has a cell the workbook does not render — typically a rollup-node cell or a NULL member |
| **WORKBOOK ONLY** | the workbook has a value where the engine created no cell — the anchoring rule [EVAL-4]; investigate: either the renderer missed a null, or the model has a cell-creation defect |

**[X-VER-3]** A renderer MUST NOT claim that a workbook "matches the model"
unless level 14.4 was performed and DIFFERS is zero. With levels 14.1–14.3
only, it claims that the workbook is a faithful translation of the documents,
and states that the model itself was not tested.

---

## 15. Agent procedure

An agent translating an FML model into a workbook follows these steps and
reports each step's outcome.

1. **Read** the FML documents, `dimensions.fml` and the member files. Record the
   excerpt: rendered version, periods, data source (engine export, sample data,
   or none).
2. **Classify** every variable: import, input, calculated, measure. Order them
   by dependency (FML 1.0 [EVAL-29]).
3. **Decide translatability** of every variable using Section 10 and Section
   13. Propagate "not translated" to dependents. Collect assumptions.
4. **Plan the sheets** (§4.1) and the key columns of each sheet (§4.4).
5. **Plan the rows** of each variable (§6), applying the anchoring rule to
   calculated variables.
6. **Plan helper columns**: every parent a translation reads through ([X-FIL-5]),
   and a path column for every tree used in a filter.
7. **Write** `Dimensions`, then the block sheets in dependency order, then
   `Notes` and `Source`. Write each formula from its template; never write a
   formula the templates do not cover.
8. **Evaluate** every formula and write its cached value.
9. **Verify** (§14), with two independent evaluators. Fix the renderer, not the assertion, when a check fails.
10. **Report**: the workbook, the list of untranslated variables and
    assumptions (the `Notes` content), the verification level reached and its
    results, and what was not verified.

An agent MUST NOT:

- change the model to make it translatable — it translates what is written,
  and lists what it cannot;
- replace a filter, a lookup or an aggregation by a simpler spreadsheet
  formula that "looks right";
- report a passing control without the positions it checks (§14.2).

---

## Annex X-A — Template notation

| Notation | Definition |
|---|---|
| `⟦V⟧` | cell of `V`, same period column, row of `V` with keys matching the current row on `G(V)` |
| `⟦V⟧ₜ₋ₖ` | as `⟦V⟧`, `k` period columns earlier |
| `⟦self⟧ₜ₋₁` | the current variable's cell in the previous period column |
| `⟨V⟩` | period-column range over all rows of `V`, current column |
| `⟨V.D⟩` | key-column range of dimension `D` over all rows of `V` |
| `⟨V.C→P⟩` | helper-column range over all rows of `V`: the member of `P` reached from the row's `C` member |
| `$D` | key cell of dimension `D` on the current row |
| `<col>$2`, `<col>$3` | year and month header cells of the current period column |

## Annex X-B — Translation quick reference

| FML construct | Excel |
|---|---|
| aligned reference | direct cell reference |
| broadcast (operand coarser) | direct reference to the operand's matching row |
| aggregation (operand finer, or child through a parent) | `SUMIFS` / `AVERAGEIFS` with criteria on every dimension of the target |
| lookup (target is child through a parent) | reference via helper column of parent members |
| filter on own grain | `SUMIFS` with the filter criterion and no context criterion for that dimension |
| filter through a parent | `SUMIFS` with the filter on the helper column **and** the row's own member |
| pinned variable | key column fixed to the pinned member |
| `if(c, a)` | `IF(c, a, "")` |
| `a + b` | `IF(COUNT(a,b)=0,"",N(a)+N(b))` |
| `a * b` | `IF(COUNT(a,b)<2,"",a*b)` |
| `cumsum(x, 0, s)` | `IF(ISNUMBER(s), s, N(prev)+N(x))` |
| `delay(x, n)` | reference `n` columns to the left |
| `spread(x, n, d)` | `SUM(range of earlier columns)/n` |
| `hasDMember(D > m)` | `$D="m"` or helper column test |
| `hasValue(x)` | `ISNUMBER(x)` |
| year total | from `@rollup`: `SUM`, last month, first month, `AVERAGE` |

## Annex X-C — Notes sheet entries

The `Notes` sheet begins with:

1. the title "Translated from FML", the source file names and their date;
2. the rendered version and periods, and the data source;
3. the null profile — null-faithful (§9.1) or simplified ([X-NULL-3]);
4. the fidelity statement (§3), verbatim or equivalent;
5. the verification level reached (§14) and its results.

It continues with one row per finding. Kind is `not translated`,
`assumption` or `information`:

| Column | Content |
|---|---|
| Variable | the variable's name |
| Kind | `not translated` or `assumption` |
| Code | one of the codes below |
| Detail | one sentence: what, and why |

| Code | Kind | Meaning |
|---|---|---|
| `UNSUPPORTED-FUNCTION` | not translated | a function at level *none*, or a form the renderer does not support |
| `DEPENDS-ON-UNTRANSLATED` | not translated | references a variable that is not translated |
| `TOO-LARGE` | not translated | exceeds [X-ROW-4] |
| `CUSTOM-TIME` | not translated | its time dimension is declared `@semantic time` |
| `NO-CELLS` | not translated | the formula can never create a cell (for example a literal-only formula) |
| `NO-DATA` | information | the variable has no cells for the rendered data: its operands have no data in the excerpt |
| `ROLLUP-NODE` | assumption | [X-NT-2] |
| `NULL-THROUGH-PARENT` | assumption | [X-NT-2] |
| `DELAY-YEAR` | assumption | [X-NT-2] |
| `MEASURE-TOTAL` | assumption | [X-NT-2] |
| `VARIABLE-ARG` | assumption | [X-NT-2] |
| `ENTERED-ONLY` | assumption | [X-NT-2] |
| `ON-DEMAND` | assumption | [X-NT-2] |
| `MULTI-PARENT` | assumption | [X-NT-2] |
| `MAPPING-ONE-WAY` | assumption | a mapping changed in the workbook does not travel back to the model |
