# fml2xlsx — reference renderer for the FML to Excel Translation

`fml2xlsx` renders an FML model as a workbook of live Excel formulas, following
the [FML to Excel Translation](../../spec/fml-excel-1.0.md) companion
specification. It is generic: it reads the FML documents, the member files and a
sample-data file, and knows nothing about any particular model. The workbooks
in [`examples/*/excel/`](../../examples/) were produced and verified with it.

It is a reference implementation of the companion specification, written to
test the specification against real models — not a production tool.

## Use

```bash
pip install -r requirements.txt

# render one model
python3 fml2xlsx.py <model-dir> <sample-data.json> <out.xlsx>

# render, evaluate and verify every example
python3 build_examples.py

# also evaluate in Microsoft Excel (macOS) and refresh the shipped workbooks'
# cached values from the values Excel computed
python3 build_examples.py --excel
```

A model directory has the layout of the examples: `dimensions.fml` (the
dimension declarations), `variables/*.fml` and the member files under
`dimensions/`. The renderer reads every `.fml` document under the directory
(FML spec §5.2) and each member file through the `from` path of its
declaration (§6.4); a CSV that no declaration names is not read.

## Files

| File | Role |
|---|---|
| `fmlparse.py` | parser for FML documents (FML spec §4–§9, Annex A): dimension declarations with their member source, `@parent` (with `many` and `required`), `@attribute`, `@null` and `@semantic time` (§6.1, §7); variables, with each defaults block applied to the variables below it, in its own document |
| `fml2xlsx.py` | the renderer: reads the member files as RFC 4180 CSV (§6.4), gives a dimension declared `@null` its NULL member with the parents of §6.5, then rows by the anchoring rule, references, filters, null-faithful arithmetic, functions, sheets (companion spec §4–§13) |
| `verify.py` | reads a workbook by variable, keys and period and checks a `targets.json` (companion spec §14.1–§14.2) |
| `calc_formulas.py` | evaluates a workbook with the independent Python evaluator `formulas` (§14.3) |
| `excel_values.py`, `dump.js` | read the values Microsoft Excel computed from an open workbook (macOS, JavaScript for Automation) |
| `inject_cache.py` | writes those values into the formula cells as cached values, keeping the formulas (§14.1 item 2) |
| `build_examples.py` | runs all of the above over every example |

## Targets

`targets.json` lists values to check:

```json
{
  "values":     [{"var": "Cash Plan", "period": "2027-01", "expect": 1805.8},
                 {"var": "PL Gross Profit", "period": "2027-01", "expect": 1460, "sum_rows": true},
                 {"var": "Price head", "keys": {"Customer": "C03", "Item": "I03"}, "period": "2027-03", "expect": 1.44}],
  "all":        [{"var": "CHECK BS A", "rule": "zero"}, {"var": "BS OUT", "rule": "populated"}],
  "row_counts": [{"var": "BS OUT", "rows": 7}]
}
```

`expect: null` asserts an empty cell. `sum_rows` sums the variable's rows that
match `keys`. Rules are `zero`, `empty` and `populated`, applied to every period
cell of the variable. Targets should be computed independently of the renderer.

## Limits

- The excerpt renders one version; `delay` must have a whole, literal number of
  periods; `spread_days`, `avg`, the growth functions and `predictAverage` are
  not translated — a variable that uses them is listed on the `Notes` sheet.
- A measure has no year total.
- A variable whose grain holds a time dimension declared `@semantic time`
  (FML spec §6.9) is not translated: the workbook's period columns
  are `YearMonth`. It is listed on the `Notes` sheet as `CUSTOM-TIME`, keeps its
  label row with no rows and no formula, and every variable that references it,
  directly or through others, is listed as `DEPENDS-ON-UNTRANSLATED` and
  rendered the same way (companion spec [X-NT-1]). The declared dimension's
  members still appear on the `Dimensions` sheet.
- A dimension declared without a member source (its members are data, FML
  spec [DIM-12]) has no members in the workbook. Attribute columns are shown on
  the `Dimensions` sheet but no formula reads them. `@rollup none` on a
  dimension is not enforced.

### Known deviations from the specification

The conformance vectors in [`tests/eval/`](../../tests/eval/) found places
where the renderer's translation disagrees with FML; they are listed, with the
affected targets, in [`tests/eval/skip.json`](../../tests/eval/skip.json). In
short:

- **Cells per row, not per cell.** The renderer decides which rows a variable
  has, and then writes a formula into every period of each row. A formula
  whose cells depend on the period — a literal branch ([EVAL-5], [EVAL-4]
  consequence 2), a lower-grain term beside an empty full-grain one
  ([EVAL-4a] rule 1) — can show a value in a period where FML has no cell.
- **Unary minus** is translated as `0 - x`, which is `0` where `x` is null
  ([EXPR-2] keeps it null).
- **Not translated:** a multi-parent foreign key [PARENT-2], a formula whose
  only operand is a lookup [EVAL-14], `or()` selectors and two filters on one
  dimension [EVAL-21], a calculated variable held by `Years` that reads a
  monthly one [EVAL-28], and `avg`.

The four examples do not use these constructs in the affected way, and their
workbooks are verified (each `excel/README.md`).
- Excel cannot save workbooks from automation inside its sandbox on macOS, which
  is why `--excel` reads the computed values from the open workbook instead of
  saving it.
