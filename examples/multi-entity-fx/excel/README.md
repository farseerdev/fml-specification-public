# Multi-entity model with currency translation — Excel translation

The workbook [`multi-entity-fx.xlsx`](./multi-entity-fx.xlsx) is the
[FML to Excel Translation](../../../spec/fml-excel-1.0.md) of the
[multi-entity example](../), rendered with [`sample-data.json`](sample-data.json)
and verified against [`targets.json`](targets.json).

What this example adds:

| Construct | Where |
|---|---|
| a model without `Versions` | the whole workbook (companion FML §12) |
| entity-pinned imports on separate local charts, added into one group-chart variable | `PL Local`, `BS Local` |
| a lookup through two parents at once (`Entity -> Currency`, `Account -> RateType`) | `PL Reporting`, `BS Reporting` |
| a difference computed at entity grain and placed on one account by a pinned transfer | `Translation Difference`, `Translation Reserve` |
| aggregation from entities to the group through a parent | `Group Revenue`, `Group Net Result` |

## 1. Excerpt

| | |
|---|---|
| Rendered version | none — the model has no `Versions` |
| Periods | `2027-01`, `2027-02` |
| Entities | E1 (EUR, the reporting currency) and E2 (USD) |

## 2. Sheets and key columns

| Sheet | Key columns |
|---|---|
| `Import` | `LocalAccountE1`, `Entity`, `LocalAccountE2` |
| `Inputs` | `Currency`, `RateType` |
| `Group` | `Entity`, `Account`, `EntityGroup` |
| `Controls` | `Entity` |

## 3. Translations worth reading

- **`PL Local`** = `"IMPORT GL Activity E1" + "IMPORT GL Activity E2"`. Each
  import is pinned to its entity and reaches `Account` through its own local
  chart, so each term is a `SUMIFS` over the helper column
  `LocalAccountE1→Account` (or `E2`) with the row's `Entity` and `Account` as
  criteria. On an E1 row the E2 term finds nothing and drops out.
- **`PL Reporting`** = `"PL Local" * "FX Rate IN"`. The rate is looked up with
  two helper columns on the `PL Reporting` rows, `Entity→Currency` and
  `Account→RateType`:
  `SUMIFS(⟨FX Rate IN⟩, ⟨FX Rate IN.Currency⟩, <helper Entity→Currency>, ⟨FX Rate IN.RateType⟩, <helper Account→RateType>)`.
  Changing an account's rate type on the `Dimensions` sheet retranslates it.
- **`Translation Reserve`** — a pinned transfer of `Translation Difference`;
  its row has `Account` = 3900 in the key column.
- **`Group Revenue`** — aggregation from `Entity` to `EntityGroup` through the
  helper `Entity→EntityGroup`, with the `PLLine` filter on the helper
  `Account→PLLine`.

## 4. Expected `Notes` entries

| Variable | Kind | Code |
|---|---|---|
| (workbook) | assumption | `MAPPING-ONE-WAY` |

## 5. Verification targets

| | 2027-01 | 2027-02 | Working |
|---|---|---|---|
| `Group Revenue` | 2 840.00 | 3 102.00 | 1 000 + 2 000 × 0.92; 1 100 + 2 200 × 0.91 |
| `Group Net Result` | 760.00 | 896.00 | 300 + 500 × 0.92; 350 + 600 × 0.91 |
| `Translation Difference`, E2 | 100.00 | 78.00 | 3 000 × 0.90 − (1 000 × 0.90 + 1 500 × 0.85 + 500 × 0.85) |
| `Translation Difference`, E1 | 0 | 0 | the reporting currency |
| `BS Reporting OUT`, E2, 1000 Cash | 2 700.00 | 3 256.00 | at the closing rate |
| `PL Reporting OUT`, E2, 5000 | 1 380.00 | 1 456.00 | at the average rate |

`CHECK BS Local A`, `CHECK BS Reporting A` and `CHECK Mapping A` are 0 for both
entities in both months.

Retained earnings are translated at the historical rate here for brevity; a
production model translates the current-year result at the average rate. The
translation reserve absorbs the difference either way.

## 6. Verification

| Level (companion FML §14) | Result |
|---|---|
| 14.1 Well-formed | opens in Microsoft Excel; 238 formula cells carry cached values; no error values |
| 14.2 Controls and targets | 22 checks |
| 14.3 Two evaluations | Microsoft Excel: 22/22 pass · independent evaluator (Python `formulas`): 22/22 pass |
| 14.4 Engine | not performed — the model has not been evaluated by an engine with data |

A workbook that passes these levels is a faithful translation of the documents;
it does not prove the model.
