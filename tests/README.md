# FML 1.0 conformance suite

Test vectors for implementations of the [FML 1.0 specification](../spec/fml-1.0.md):
parsers, linters, formatters and engines. Every expected result is derived from
the specification text, not from an implementation.

```bash
python3 tests/run.py               # everything
python3 tests/run.py --no-eval     # without the evaluation vectors
python3 tests/run.py --verbose     # also list what passed and what was skipped
FML_EVAL_PYTHON=/path/to/python python3 tests/run.py   # a Python with openpyxl and formulas
```

`run.py` runs the syntax and model vectors through the reference linter
([`tools/fml-lint`](../tools/fml-lint/)), the evaluation vectors through the
reference renderer ([`tools/fml2xlsx`](../tools/fml2xlsx/)) and its independent
evaluator, lints every example model and checks the canonical-form round trip
[DOC-4] on every example document. A further check pins the dimension
declarations in the canonical form and the information content (§5.5, §5.6
item 1): `fmt` puts them first, sorted by name, with their properties in the
canonical order, the round trip keeps them, and the retired `link` and `time`
statements are rejected. It prints a summary and exits non-zero on any
failure. Without a Python that has `openpyxl` and `formulas` it skips rendering
and says so.

## Layout

```text
tests/
  syntax/valid/*.fml        conforming documents
  syntax/invalid/*.fml      documents that must produce given diagnostics
  models/<case>/            multi-file models with expect.json
  eval/<case>/              evaluation vectors, in the layout of examples/
  eval/skip.json            assertions the reference renderer cannot check yet
  run.py
```

### Syntax vectors

Each file is one document, linted as a model of one document: every name it uses
resolves inside it, so each declares the dimensions it uses [DOC-6].

- `valid/` — must produce **no error** under `standard`. An optional first-line
  `# expect: FML-I0408, …` lists warnings or information it must produce (the
  extensions of `v14-extensions.fml`, for example). Each must also survive the
  round trip: `parse(fmt(parse(d)))` has the information content of `parse(d)`
  (§5.5), and `fmt` is idempotent.
- `invalid/` — the first line is `# expect: FML-Exxxx[, FML-…]`, the codes the
  document must produce. An optional `# may: FML-…` line lists errors an
  implementation is allowed to report in addition, as a consequence of the first
  (error recovery is not specified). Any other error fails the vector. Warnings
  and information beyond the `expect` line are allowed. Files are named after the
  first expected code; vectors whose code is a warning (`w…`) or information
  (`i…`) cover the modelling rules of Annex C.8 and the graph rules of §7.5.

What they cover: names and string escapes (§4.5–§4.6, [LEX-1]–[LEX-4]),
comments, numbers and [LEX-5] (a negative literal against subtraction, a
negative literal at the start of a line), unary minus [EXPR-2], every
continuation point of §4.9 and [LEX-6], reserved words (`dimension` among them;
`time` and `link` are plain names now), BOM and CR LF, UTF-8, dimension
declarations (§6.1: inline lists on one line and across lines, `from`, no
source, every property of [DIM-13]; `FML-E0207` for a system dimension,
`FML-E0208` for an undeclared dimension in a grain, a `@parent` or a filter,
`FML-E0209`, `FML-E0612` for a missing member file, `FML-E0613`, `FML-E0614`,
`FML-E0615` for an inline NULL member, `FML-W0606`, `FML-W1107` for a read
across `@rollup none`, the retired `link` and `time` statements as
`FML-E0104`), parents (§7: `many`, `required`, trees, a parent that is a system
dimension, duplicate targets as `FML-E0707` in every profile and refused by
`fmt`), declared time dimensions (§6.9, [DIM-11]: `@semantic time`,
time-series functions along a declared dimension, a declared dimension beside
`YearMonth` as `FML-E0206`), grains with pins,
one time dimension per grain and no reading level [VAR-9], properties of every value kind, inline properties [VAR-1],
defaults blocks [PROP-3], every standard function and its arity (§12), member
references and filters (§10.3–§10.4, [EVAL-20]), and every static Annex C code
the reference linter implements (its README lists them).

### Model vectors

`models/<case>/` holds `dimensions.fml` (the dimension declarations),
`variables/*.fml`, the member files under `dimensions/` that the declarations
name, and usually `model.json`. `expect.json`:

```json
{
  "description": "what the case pins",
  "profile": "standard",
  "diagnostics": [{"code": "FML-E0302", "file": "variables/model.fml", "line": 10}],
  "exit": {"lenient": 0, "standard": 0, "strict": 1},
  "counts": {"lenient": 2, "standard": 4, "strict": 4}
}
```

The diagnostics reported under `profile` must equal `diagnostics` as a multiset of
(code, file, line); columns and messages are not compared. `exit` (optional) gives
the expected exit code of `fml_lint.py lint` per profile, `counts` (optional) the
number of diagnostics each profile reports. The cases cover the manifest (§5.7:
invalid JSON, unknown version, partial or reversed horizon, missing or mistyped
fields, unknown fields preserved), `membersComplete` and its absence (§15.1),
member-file rules (m10: [DIM-3], [DIM-10], [DIM-12], [PARENT-4]: header columns,
cells per row, a listed NULL member, a blank line, a header naming another
dimension, a missing file, a CSV no declaration names), parents in member files
(m14: `many`, `required`, `@null`, [PARENT-2], [PARENT-3]), resolution across
documents and [DOC-3], dependency cycles, profiles (§15.4), and declared time
dimensions under `membersComplete` (§6.9: a day member file in period order with
its `YearMonth` parent; a time dimension without a member source).

### Evaluation vectors

`eval/<case>/` has the layout of the examples: `model.json`, `dimensions.fml`
(the dimension declarations, where the case uses a dimension other than the
system dimensions), `variables/*.fml`, the member files under `dimensions/`
that the declarations name, `excel/sample-data.json` and `excel/targets.json`,
in the formats of
[`tools/fml2xlsx/README.md`](../tools/fml2xlsx/README.md):

- `sample-data.json` — `periods` (the horizon, ISO `YYYY-MM`), the rendered
  `version` where the case uses `Versions`, and the input cells per variable:
  `values` by period, `from` + `value` (every period from that one), or `years`
  (a `Years` variable). A `Months` variable is keyed by the months of the first
  year of the horizon.
- `targets.json` — `values`: `{var, keys?, period, expect}`; `expect: null`
  asserts **no cell**; `period` is a `YearMonth` member, or `"<year> Total"` for a
  read at that year (§6.7, [EVAL-28]), or `"<year>"` for a variable held by
  `Years`. `row_counts`: `{var, rows}`, the number of distinct non-time key
  combinations at which the variable has at least one cell.

Each case's document begins with a comment that states its data and the rule
it pins; the expected values are worked out by hand from that rule.

| Case | Pins |
|---|---|
| e01-null-vs-zero | [EVAL-3] null is not 0; [EVAL-4a] a literal adds a value, never a cell |
| e02-anchoring-literals | [EVAL-4] consequences 1 and 3, [EVAL-5] |
| e03-hasvalue-default | [EVAL-4] consequence 2, [EVAL-25] with a carrier |
| e04-full-grain-rule | [EVAL-4a] rules 1 and 2, [EVAL-12] |
| e05-aggregation-to-parent | [EVAL-13] projection to a parent, [EVAL-15] empty key → NULL member |
| e05b-multi-parent | [PARENT-2] a member with two parents (`@parent Group many`) counts under each |
| e06-lookup-from-parent | [EVAL-14] lookup beside a full-grain operand |
| e06b-lookup-alone | [EVAL-14] a lone lookup has a cell on every child whose parent has a value |
| e07-filters-own-vs-across | [EVAL-23] own-grain filter broadcasts, a filter through a parent intersects |
| e07b-filters-and-selectors | [EVAL-21] filters on one dimension intersect; `or` unites |
| e08-null-arithmetic | [EVAL-11], [EVAL-11a], unary minus |
| e08b-unary-minus-null | [EXPR-2] `-x` keeps x's cells |
| e09-conditions-and-null | [EVAL-24]–[EVAL-26], [EVAL-6] |
| e10-time-aggregation | [EVAL-28], [PROP-4]: sum, closing_state and beginning_state strictly, average |
| e10b-years-consumer | [EVAL-28] a variable held by `Years` reading a monthly one |
| e10c-closing-state-ended-member | [PROP-4a], [EVAL-28] a balance over several products at a year: each product's December, a product whose data ends in March contributes nothing |
| e11-years-read-monthly | [EVAL-28a] `Years` and `Months` variables read by a monthly one |
| e12-time-series-year-boundary | [FUN-2], [FUN-6a], half-up shifts, `cumsum` with a factor, `spread` |
| e13-pinned-grain | [EVAL-18] a pin writes, [EVAL-19] transfer, aligned collector (§11.5) |
| e14-math-functions | [FUN-7] round half away from zero, negative digits; `max`/`min` skip null; [FUN-5] date functions of null |
| e15-moving-average-edges | §12.2 `avg`, [FUN-6a] its window at the start of the horizon, `skip_nulls` |
| e16-monthly-in-yearly | [EVAL-4a] the calendar exception: a monthly reference carries `Years`; a region-free term adds only its value |

`eval/skip.json` lists the assertions the reference renderer cannot check: a
construct it does not translate (`unsupported`), a translation that disagrees with
the rule (`deviation`), or its Python evaluator disagreeing with Excel
(`evaluator`). The expected values stay the specification's; `run.py` only
leaves those assertions out when it uses fml2xlsx. An engine runs every vector in
full.

## Using the vectors in another implementation

- **A parser or formatter** parses every `syntax/valid` file without error,
  rejects every `syntax/invalid` file with an `E` code on its `expect` line, and
  satisfies the round trip on `syntax/valid` and `examples/`.
- **A linter** reports the codes of each `expect` line, and for `models/` the
  exact diagnostics of `expect.json` (file and line). A linter that implements
  fewer checks than the reference linter can filter `expect.json` to its codes.
- **An engine** loads each `eval/` case with its sample data as stored cells,
  evaluates it, and compares every target: a number within 0.005, `null` as the
  absence of a cell, `row_counts` as the number of key combinations holding a
  cell, `"<year> Total"` as the read at `Years > "<year>"`. Skip nothing.

## Licence

The contents of `tests/` — the runner and the test vectors — are licensed under
the Apache License 2.0 ([`tools/LICENSE`](../tools/LICENSE)), as the repository README
states for `tools/` and `tests/`.
