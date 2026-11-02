# fml-lint — reference linter and formatter for FML 1.0

`fml-lint` checks an FML model against the [FML 1.0 specification](../../spec/fml-1.0.md)
and reports the diagnostics of its Annex C. It also prints the canonical form of
a document (§5.6). It reads the documents, the member files and the model manifest
only; it needs no engine and no data. It is written in Python 3 with the standard
library only.

It is a reference implementation, written to test the specification against
real models — not a production tool.

## Use

```bash
# a model directory (documents, the member files they name, model.json), one document or one member file
python3 fml_lint.py lint <model-dir-or-file> [--profile lenient|standard|strict] [--json]

# the canonical form of a document
python3 fml_lint.py fmt <file.fml>
```

`lint` prints one line per diagnostic:

```text
examples/workforce/variables/pay.fml:45:3 FML-W1104 'EL102 Seniority' is pinned on …
```

and a count on standard error. A diagnostic whose severity the profile changes
says so: `FML-W1204 [error under strict] …`. The exit code is 1 when any
diagnostic is an error under the chosen profile, 0 otherwise, 2 on a usage error.
`--json` prints an array of `{path, line, col, code, severity, message}`.

`fmt` prints the canonical form (§5.6) — dimension declarations first, sorted by
name, each with its properties in the order `@semantic`, `@rollup`, `@parent`
(sorted by dimension, `many` before `required`), `@attribute` (in the order
written), `@null`, `@folder`, `@desc`, then any other property alphabetically;
then variables sorted by name, one header line each, every inherited property stated on its variable, no
defaults blocks, properties equal to their default omitted, names in identifier
form where valid, `Dim > Member` with a space on each side of `>`. Comments are
not information content and do not survive. `fmt` refuses a document with a
syntax error or a duplicate `@parent` target (exit 1). It satisfies [DOC-4]: `parse(fmt(parse(d)))` has the
information content of `parse(d)`; `tests/run.py` checks this on every test
vector and every example document.

### Profiles

Severities follow §15.4. Codes outside the table keep the severity their letter
gives; an `E` is never lowered.

| Check | codes | lenient | standard | strict |
|---|---|---|---|---|
| naming rules | W1201 W1202 W1203 W1205 | I | W | W |
| `@readonly` on non-inputs | W1204 | I | W | E |
| `@desc` on a variable | I1206 | — | I | W |
| parent cycles | W0701 | I | W | E |
| diamonds | I0702 | — | I | W |
| grain alignment | W1101 W1102 W1103 W1104 W1105 | I | W | E |
| sparsity | W1001 W1002 W1005 W1006 W1007 | I | W | E |
| missing `@notes` | I1208 | — | I | W |

## What it reads

| Input | Spec |
|---|---|
| every `*.fml` under the model directory (hidden directories excepted) | §5.2 |
| the member file each `dimension … from "<path>"` names, relative to the model directory; a CSV no declaration names is not read | §6.1, §6.4, [DIM-3], [DIM-10] |
| `model.json` at the root | §5.7, [DOC-5] |

Linting a single document treats it as a model of one document without a
manifest, whose directory is the folder of the document: every name must then
resolve inside that document, and `from` paths are read relative to that folder.
Linting a single member file checks its CSV form only (cells per row, unique
members, no listed NULL member); its header is checked against a declaration
only when the model is linted.

The parsers are a hand-written lexer and recursive-descent parsers for the
document grammar (Annex A.3, with the continuation rules of §4.9 and [LEX-6]),
the formula grammar (Annex A.4, with unary minus) and the member-file format
(Annex A.5: RFC 4180 quoting with quoted line breaks, no comments, no blank
lines, no trimming, multi-parent `|` cells).

## Implemented diagnostics

| Area | Codes |
|---|---|
| C.1 lexical and syntax | E0101 E0102 E0103 E0104 E0105 E0106 E0107 |
| C.2 declarations | E0201 E0202 W0203 W0204 E0205 E0206 E0207 E0208 E0209 |
| C.3 resolution | E0301 E0302 E0303 |
| C.4 formulas | E0401 W0403 E0404 E0405 E0406 E0407 I0408 E0410 |
| C.5 dependencies | E0501 |
| C.6 dimensions and parents | E0603 W0606 E0607 E0608 E0609 E0610 E0612 E0613 E0614 E0615 E0616 E0617 W0701 I0702 W0703 W0704 E0705 |
| C.7 properties and formats | I0901 E0902 E0903 I0905 W1401 W1402 |
| C.8 modelling rules | W1001 W1002 I1003 W1004 W1005 W1006 W1007 W1101 W1102 W1103 W1104 W1105 W1107 W1201 W1202 W1203 W1204 W1205 I1206 W1207 I1208 W1301 W1302 W1303 |

How the less obvious ones are decided:

- **Dimension declarations** — `dimension <name>` with an inline list
  `{ … }` (which may span lines inside the braces), `from "<path>"` or no
  source, then its property lines (§6.1). `dimension` is reserved at the start
  of a statement: a variable named `dimension` is written `"dimension"` (E0105
  otherwise). `link` and `time` are no longer reserved; a retired
  `link A -> B` or `time X` statement is E0104 with a hint to `@parent` or
  `@semantic time`.
- **E0207** — a declaration naming a system dimension (`YearMonth`, `Years`,
  `Months`, `Quarters`, `Half years`, `Year to date`, `Versions`). This also
  covers what E0602 used to catch: a model cannot give a system dimension a
  parent, because it cannot declare one.
- **E0208** — a grain entry, a `@parent` target or a member reference naming a
  dimension that is neither declared nor a system dimension, and a member file
  whose header names an undeclared dimension. A member reference whose
  "dimension" is a variable stays E0303. **E0209** — a second declaration of a
  dimension, reported at the second.
- **Dimension properties** (DIM-13) — `@parent <Dim> [many] [required]`,
  `@attribute <name> <type>` (`number`, `integer`, `boolean`, `string`,
  `date`), `@null` (the one property without a value), `@semantic time`,
  `@rollup none`, `@folder <string>`, `@desc <string>`. Any other value is
  E0903; any other property is I0901 (preserved). A property given twice is
  W0204, including the same `@attribute` name given twice (the last occurrence
  is used). A duplicate `@parent` target is **E0707**, even with identical
  modifiers; both `lint` and `fmt` reject it [PARENT-4].
- **@semantic time** — a declared time dimension counts as a time dimension for
  E0206 and E0407; it does not satisfy the date context functions (E0407,
  [FUN-8]). One without a member source is not E0607 under `membersComplete`,
  and references to its members are not checked (they are data).
- **E0612 / E0613 / E0614 / E0615** — a `from` file that does not exist
  (reported at the path); an inline list on a dimension with `@parent` or
  `@attribute`; an attribute named like a parent of the same dimension or
  `@description`; `NULL (<Dim>)` listed inline or as a member-file row.
- **E0705** — a member-file header cell that is not exactly one `@parent` or
  `@attribute` name of the declaration (exact case), `@description` anywhere
  but second, a column given twice, a header naming another declared
  dimension, and a `@parent` or `@attribute` without its column (reported at
  the property).
- **E0616 / E0617** — a parent cell naming several members (`|`) for a parent
  declared without `many`; an empty parent cell for a parent declared
  `required`. Both only for member files: for a dimension without a source the
  engine checks them when members are written.
- **W0606** — a declared dimension that is the parent of another dimension
  through a `@parent` that is not `required`, and that does not declare
  `@null`. A tree (a dimension that is its own parent) and a time dimension are
  exempt. Reported at the parent's declaration.
- **W0703** — a `@parent` whose member-file column is empty in every row.
- **W1107** — a variable reference (in value or condition position) whose
  source carries, free, a dimension declared `@rollup none` that the consumer's
  grain does not carry and that no `sum` filter around the reference names.
  Aggregation through a parent of that dimension is caught the same way.
- **E0302** — a member named in a filter, a `hasDMember` argument or a pinned
  grain entry that the member files do not list, a `YearMonth` or `Years` member
  outside the manifest's horizon, or a `Versions` member that is neither `Actual`,
  `Plan` nor listed in the manifest — only when the manifest sets
  `membersComplete` (§15.1, §5.7). A system-dimension member that is malformed
  (`Months > "13"`, `Quarters > Q5`, `YearMonth > "2026-13"`) is reported
  always: those dimensions are fully defined by §6.7. A NULL member
  `NULL (<Dim>)` exists only when the declaration has `@null` [DIM-5]. The
  members of a dimension are those of its inline list or member file; a
  dimension without a source has unknown members.
- **E0610** — a parent cell naming a member the parent's member source does
  not list (its NULL member only with `@null`); for a parent without a member
  source, only under `membersComplete`.
- **E0607** — an empty inline list or a member file without rows; also a
  dimension without a member source when the manifest sets `membersComplete`.
- **E0404 / E0405 / W0403** — a `sum` filter (and, by the same rule, a
  `hasDMember` argument) that is a member reference or a selector over member
  references is accepted; a variable, a comparison or any other value is E0404;
  a bare dimension name is E0405; any other bare name is an unqualified member
  reference, W0403.
- **E0105** is also used where Annex C has no code of its own: a member reference
  outside a member-accepting argument (§10.3), `A > B` or `A == B` between values
  [EXPR-3], `-3` directly after an operand [LEX-5], an unquoted reserved word
  as a name (§4.5), a property after a formula on the same line [VAR-1], a
  `from` without a string, extra text after a quoted member-file cell, a `"`
  inside an unquoted cell, a blank line in a member file [DIM-3].
- **E0107** is also used for a file that is not valid UTF-8 (§4.1, [DIM-10]).
- **E0206** — two time dimensions in one grain (`YearMonth`, `Years`, `Months`
  or a declared one), or a reading level (`Quarters`, `Half years`,
  `Year to date`).
- **E0407** — a time-series function in a variable with no *free* time dimension
  (`YearMonth`, `Years`, `Months` or a declared one); a pinned
  `YearMonth = "…"` or `Day = "…"` does not count. Also a date context function
  in a variable whose grain (free or pinned) lacks the dimension it reads:
  `YearMonth` for `currentDate` and `daysInCurrentMonth`, `YearMonth` or
  `Months` for `currentMonth`, `YearMonth` or `Years` for `currentYear`
  [FUN-8].
- **W0704** — `@parent B` on `A` where a third dimension has both `A` and `B`
  as direct parents (the shape of [DIMD-11]'s example). Longer converging paths
  are reported as diamonds, I0702.
- **I0702** — reported once per pair, at the dimension where the paths split
  and the one where they first meet.
- **W1004** — `@rollup sum` (stated, inherited or by default) on a variable whose
  name contains "balance", or whose `@notes` speak of "a/the/closing/opening
  balance" (not "balance sheet"); names with movement, change, delta, flow or
  check are exempt.
- **W1005** — a three-argument `if` whose condition contains `hasValue` and
  exactly one of whose branches is a constant. A two-argument `if(hasValue(X), 1)`
  is the flag of [EVAL-5], not a default.
- **W1001 / W1006** — no variable reference in value position (§11.3, Annex B),
  except the single-variable condition of [EVAL-5]; W1006 when an `if` with
  literal branches has two or more variables in its condition.
- **W1101** — a free output dimension that no operand carries, reaches by
  aggregation or reaches by lookup. `Versions` is exempt: a version-free operand
  read by every version is the intended pattern of [TIME-2].
- **W1102** — an `if` whose two branches are single references, one carrying the
  whole output grain and one not.
- **W1103** — `sum` over a product or quotient of references with different grains.
- **W1104** — a pinned variable with a value-position operand that carries the
  pinned dimension (or a dimension that reaches it) as a *free* dimension, outside
  a `sum` filtered on a dimension connected to it. An operand pinned on the same
  dimension holds one member and is not reported.
- **W1105** — a formula with a `sum` filter on its own grain and one on a
  dimension reached through a parent from its grain [EVAL-23].
- **W1201–W1207, I1208** — by the markers of Guide §2: `IMPORT ` / `IMPORT_`,
  ` IN` / `_IN`, ` OUT` / `_OUT`. W1202 is a formula-less, not read-only,
  non-import variable without the suffix, or `IN` in the middle of a name;
  W1203 is ` OUT` on a variable without a formula — an input or an import
  (Guide §2.1 lets other variables read an output);
  W1207 accepts a top-level two-argument `if` as a fenced seed; I1208 applies to
  formula-less variables and to ` IN` / ` OUT` variables without non-empty
  `@notes`.
- **W1401** — `numberFormat.type` (or the family `@format` sets) against
  `formatString`: a PERCENTAGE string without `%`, a NUMBER or CURRENCY string
  with `%`, or, without `custom: true`, a string other than the one [FMT-1]
  derives from type and decimals.
- **W1402** — a percentage variable whose formula multiplies by the literal 100.

## Skipped diagnostics

| Code | Why |
|---|---|
| E0402 | the engine form of W0403; a linter reports W0403 [EXPR-8] |
| E0409 | raised by an engine asked to evaluate an extension it lacks |
| W0604 | needs the history of a change (a deleted member) |
| W0601 | a member file is read only through a declaration, and declaring a system dimension is E0207, so a member file for a system dimension cannot occur |
| E0602 | a model cannot declare a system dimension (E0207), so it cannot change one |
| E0611 | one declaration names one file and a dimension is declared once (E0209), so two member files for one dimension cannot occur |
| E0706 | withdrawn: `many` replaces the cardinality annotation |
| E0605 | `YearMonth` and `Years` members are defined by the manifest's horizon, which is contiguous by construction; an invalid horizon is E0608 |
| I0904 | the linter recognises no implementation profile; extensions are reported as I0408, I0901 and I0905 instead |
| W1106 | needs to know which operands are dense, which is data |
| W1501, W1502 | need cell estimates from data (§23) |

The engine-stage rules of §11 are not linted at all; `tests/eval/` checks them
against an evaluator.

## Licence

The code in `tools/` and `tests/` is licensed under the Apache License 2.0 ([`tools/LICENSE`](../LICENSE)).
The specification it implements is licensed under CC BY 4.0 (see
[`NOTICE`](../../NOTICE)). This tool implements the Financial Modeling Language
(FML) specification by Farseer, version 1.0.
