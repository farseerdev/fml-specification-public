# Workforce model — Excel translation

The workbook [`workforce.xlsx`](./workforce.xlsx) is the
[FML to Excel Translation](../../../spec/fml-excel-1.0.md) of the
[workforce example](../), rendered with the sample data in
[`sample-data.json`](sample-data.json) and verified against
[`targets.json`](targets.json).

What this example adds to the first two:

| Construct | Where |
|---|---|
| headcount derived from contract dates with `currentDate()` and an open-end carrier | `Headcount` |
| salary elements pinned to their members and collected by a plain sum | `Pay` |
| classification as data: `hasDMember(ContributionClass > Liable)` through a parent | `Contribution Base by Element` |
| a raise from a month number with `currentMonth()` | `Raise Applies`, `Raise Factor` |
| projection over two parents at once (`SalaryElement -> Account`, `Position -> CostCenter`) | `HR Cost OUT` |
| a version-free import projected onto closed periods before a subtraction (FML 1.0 [EVAL-4a], [EVAL-12]) | `Payroll Variance OUT` |
| date-valued variables (`@type date`) and their year totals | `Headcount` |

## 1. Excerpt

| | |
|---|---|
| Rendered version | `Plan` |
| Periods | `2027-01` – `2027-12`; `2027-01` is a closed period (`FC Actual IN` = 1) |
| Data | [`sample-data.json`](sample-data.json): six positions — a manager, an assistant leaving in June, a part-time head, a hire in April, a planner leaving in February, a vacancy filled in September |

## 2. Sheets and key columns

| Sheet | Key columns | Holds |
|---|---|---|
| `Foundation` | — | forecast flag, planning horizon |
| `Import` | `Employee`, `SalaryElement` | payroll actuals |
| `Inputs` | `Position`, `PayGrade` | contract data and assumptions |
| `Headcount` | `Position` | the date chain and FTE |
| `Pay` | `Position`, `SalaryElement` | raise, salary elements, contributions, total cost |
| `Outputs` | `Account`, `CostCenter`, `Employee`, `SalaryElement` | ledger-grain cost, headcount, payroll variance |
| `Controls` | — | conservation checks |

## 3. Translations worth reading

- **`HC Active`** — two variables in the condition, so the output is the carrier
  `Position Anchor`, not a literal (FML 1.0 [SPARSE-3]):
  `=IF(COUNT(<start month>,<end effective>)<2,"",IF(AND(DATE(C$4,C$5,1)>=<start month>,DATE(C$4,C$5,1)<=<end effective>),<anchor>,""))`.
  Months outside the contract window are empty, not zero.
- **`Contract End effective`** — `if(hasValue("Contract End IN"), "Contract End IN", "Open End Date")`.
  For a position without an end date the input has no row, so the true branch
  is null and the formula takes the carrier `Open End Date` (9999-12-31).
- **`EL101 Base Pay` … `EL301 Year End Gift`** — each pinned to its own
  `SalaryElement` member: one row per position, with the pinned member in the
  `SalaryElement` key column. `Gross Pay` is then a sum in which each term has a
  row only on its own member (companion spec [X-REF-5]).
- **`Contribution Base by Element`** — `hasDMember(ContributionClass > Liable)`
  becomes a test of the row's helper column `SalaryElement→ContributionClass`
  ([X-FIL-7]); changing an element's class on the `Dimensions` sheet changes the
  contribution base.
- **`HR Cost OUT`** — one `SUMIFS` over `Total Cost` with two helper criteria,
  `SalaryElement→Account` and `Position→CostCenter`.
- **Year totals of dates** — `Contract Start Month` and `Contract End effective`
  have no year total: a sum of dates is not a date (companion FML §5.2).

## 4. Expected `Notes` entries

| Variable | Kind | Code |
|---|---|---|
| (workbook) | assumption | `MAPPING-ONE-WAY` |

The excerpt covers one year, so no `DELAY-YEAR` entry is needed.

## 5. Verification targets

Computed independently of the renderer, from the sample data:

| Month | Headcount CC100 | Headcount CC200 | FTE | Total cost | Cost per FTE |
|---|---|---|---|---|---|
| 2027-01 | 2 | 2 | 3.5 | 12 386.28 | 3 538.94 |
| 2027-02 | 2 | 2 | 3.5 | 12 386.28 | 3 538.94 |
| 2027-03 | 2 | 1 | 2.5 | 9 010.11 | 3 604.04 |
| 2027-04 | 2 | 2 | 3.5 | 11 340.11 | 3 240.03 |
| 2027-07 | 1 | 2 | 2.5 | 8 983.14 | 3 593.26 |
| 2027-09 | 2 | 2 | 3.5 | 12 463.00 | 3 560.86 |
| 2027-12 | 2 | 2 | 3.5 | 13 663.00 | 3 903.71 |
| **Year** | | | | **136 821.26** | |

- Headcount per cost centre counts positions, so P003 (half time) counts 1 while
  contributing 0.5 FTE.
- The raise applies from July: P001's base pay is 3 000 to June and 3 090 from
  July.
- Year-end gifts in December, per head: 300 + 400 + 200 + 300 = 1 200 on
  account 6010.
- Payroll variance in 2027-01: E03 base pay 2 300 paid against 2 250 planned (+50);
  every other element 0; empty in 2027-02 – 2027-12 (open periods).
- `CHECK Ledger A` and `CHECK Contribution A` are 0 in every month.

## 6. Verification

| Level (companion FML §14) | Result |
|---|---|
| 14.1 Well-formed | opens in Microsoft Excel; 2 187 formula cells carry cached values; no error values |
| 14.2 Controls and targets | 71 checks |
| 14.3 Two evaluations | Microsoft Excel: 71/71 pass · independent evaluator (Python `formulas`): 71/71 pass |
| 14.4 Engine | not performed — the model has not been evaluated by an engine with data |

A workbook that passes these levels is a faithful translation of the documents;
it does not prove the model.
