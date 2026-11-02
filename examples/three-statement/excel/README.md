# Three-statement model — Excel translation

This document specifies the workbook that the
[FML to Excel Translation](../../../spec/fml-excel-1.0.md) companion
specification produces from the [three-statement example model](../). An agent
or a program that follows the companion specification should produce a
workbook of this shape, and its verification should reach the values in §7.

The workbook [`three-statement.xlsx`](./three-statement.xlsx) in this folder follows this description;
see §8 for how it was verified.

## 1. Excerpt

| | |
|---|---|
| Rendered version | `Plan` |
| Periods | `2026-12` (opening month) to `2027-12` — 13 period columns |
| Year totals | `2026` (partial: 2026-12 only), `2027` |
| Data | the sample data of §6 |
| Null profile | null-faithful (§9.1 of the companion specification) |

## 2. Sheets

| # | Sheet | From |
|---|---|---|
| 1 | `Notes` | §5 below |
| 2 | `Dimensions` | the seven member files |
| 3 | `Foundation` | `@folder "Foundation"` |
| 4 | `Import` | `@folder "Import"` and `"Import/Upstream"` |
| 5 | `Inputs` | `@folder "Inputs"` |
| 6 | `PL` | `@folder "PL/Plan"` |
| 7 | `BS` | `@folder "BS/Plan"` |
| 8 | `Statements` | `@folder "Statements"` |
| 9 | `Controls` | `@folder "Controls"` |
| 10 | `Source` | the eight FML documents, verbatim |

Key columns per block sheet (order of first appearance in the grains):

| Sheet | Key columns |
|---|---|
| `Foundation` | — |
| `Import` | `Account`, `CostCenter` |
| `Inputs` | `Product`, `ProductGroup`, `CostCenter`, `Account` |
| `PL` | `Product`, `Account`, `CostCenter` |
| `BS` | `Account` |
| `Statements` | `Account`, `CostCenter` |
| `Controls` | — |

Period columns follow the key columns; year totals follow the periods after
one empty column; helper columns follow after another empty column.

## 3. Helper columns

| Sheet | Rows of | Helper | Formula on row `r` |
|---|---|---|---|
| `PL` | `Cost of Goods Sold` | `Product→ProductGroup` | `=XLOOKUP($B r, dim_Product, fk_Product_ProductGroup, "")` |
| `PL` | `PL Plan Pre Tax` | `Account→PLLine` | `=XLOOKUP($C r, dim_Account, fk_Account_PLLine, "")` |
| `Inputs` | `Opening Balances IN` | `Account→BSLine` | `=XLOOKUP($E r, dim_Account, fk_Account_BSLine, "")` |
| `BS` | `BS Plan` | — | not needed |
| `Statements` | `PL OUT` | `Account→PLLine` | as above |
| `Statements` | `PL Plan` (read from `PL`) | `Account→PLLine` | helper on the `PL` rows of `PL Plan` |
| `Statements` | `BS OUT` | `Account→BSLine→BSGroup` path | `="|"&<ancestors of the BSLine member in BSGroup, root first>&"|"` — e.g. `|Total assets|Current assets|` for `Cash` |

The path for `BSGroup` is computed by the renderer from `BSLine.csv` and
`BSGroup.csv` and may be written as a lookup chain or, for a fixed tree, as a
second helper block on `Dimensions` holding each `BSLine` member's path.

## 4. Variables

Notation as in Annex X-A of the companion specification. `c` is the current
period column. "Null-wrapped" means the null-faithful form of §9.1.

### 4.1 `Foundation`

| Variable | Rows | Formula in column `c` |
|---|---|---|
| `FC Actual IN` | 1 | input: `1` in `2026-12`, empty elsewhere |
| `FC Actual Flag` | 1 | `=IF(ISNUMBER(⟦FC Actual IN⟧),⟦FC Actual IN⟧,"")` |

### 4.2 `Import`

| Variable | Rows | Formula |
|---|---|---|
| `IMPORT GL Activity` | accounts × cost centres with data (none in the sample) | input |
| `IMPORT GL Balance` | balance-sheet accounts | input |
| `PL Actual upstream` | as `IMPORT GL Activity` | `=IF(ISNUMBER(⟦IMPORT GL Activity⟧),⟦IMPORT GL Activity⟧,"")` |
| `BS Actual upstream` | as `IMPORT GL Balance` | same form |

### 4.3 `Inputs`

Every variable is an input row. Year-grained inputs (`COGS Rate IN`,
`Average Monthly Cost IN`, `Interest Rate IN`, `Tax Rate IN`, `DSO Days IN`,
`DPO Days IN`) hold the value in the first month of each year, and the other
months reference it (§5.3 of the companion specification).

### 4.4 `PL`

| Variable | Rows | Case | Formula in column `c` |
|---|---|---|---|
| `Sales Revenue` | P100, P200, P300 | aligned | `=IF(COUNT(⟦Sales Volume IN⟧,⟦Unit Price IN⟧)<2,"",⟦Sales Volume IN⟧*⟦Unit Price IN⟧)` |
| `Cost of Goods Sold` | P100, P200, P300 | aligned × lookup | `=IF(COUNT(⟦Sales Revenue⟧)=0,"",⟦Sales Revenue⟧*SUMIFS(⟨COGS Rate IN⟩,⟨COGS Rate IN.ProductGroup⟩,<helper Product→ProductGroup>))` |
| `PL Revenue to Account` | (4000, CC100) | pinned; aggregation over `Product` | `=IF(COUNT(⟨Sales Revenue⟩)=0,"",SUM(⟨Sales Revenue⟩))` |
| `PL COGS to Account` | (5000, CC200) | same | `=IF(COUNT(⟨Cost of Goods Sold⟩)=0,"",SUM(⟨Cost of Goods Sold⟩))` |
| `Personnel Cost` | CC100, CC200, CC300 | aligned | `=IF(COUNT(⟦Headcount IN⟧,⟦Average Monthly Cost IN⟧)<2,"",⟦Headcount IN⟧*⟦Average Monthly Cost IN⟧)` |
| `PL Personnel to Account` | (6000, CC100/CC200/CC300) | pinned `Account`; aligned on `CostCenter` | `=IF(ISNUMBER(⟦Personnel Cost⟧),⟦Personnel Cost⟧,"")` |
| `Depreciation` | 1 | `spread` + reference | `=IF(COUNT(<Capex IN from max(first, c−60) to c−1>,⟦Existing Depreciation IN⟧)=0,"",SUM(<same range>)/60+N(⟦Existing Depreciation IN⟧))`; in the first period column the range is empty and only the second term remains |
| `PL Depreciation to Account` | (6900, CC300) | pinned | `=IF(ISNUMBER(⟦Depreciation⟧),⟦Depreciation⟧,"")` |
| `Loan Movement` | 1 | aligned | `=IF(COUNT(⟦Loan Drawdown IN⟧,⟦Loan Repayment IN⟧)=0,"",N(⟦Loan Drawdown IN⟧)-N(⟦Loan Repayment IN⟧))` |
| `Opening Loans` | 1 | filtered aggregate | `=IF(COUNTIFS(⟨Opening Balances IN.Account→BSLine⟩,"Borrowings",⟨Opening Balances IN⟩,"<>")=0,"",SUMIFS(⟨Opening Balances IN⟩,⟨Opening Balances IN.Account→BSLine⟩,"Borrowings"))` |
| `Loan Balance` | 1 | `cumsum(x, 0, s)` | `=IF(ISNUMBER(⟦Opening Loans⟧),⟦Opening Loans⟧,IF(COUNT(⟦self⟧ₜ₋₁,⟦Loan Movement⟧)=0,"",N(⟦self⟧ₜ₋₁)+N(⟦Loan Movement⟧)))`; first column: `⟦self⟧ₜ₋₁` is absent |
| `Loan Balance Prior` | 1 | `delay(x, 1)` | `=IF(ISNUMBER(⟦Loan Balance⟧ₜ₋₁),⟦Loan Balance⟧ₜ₋₁,"")`; first column: `""` |
| `Interest Expense` | 1 | product | `=IF(COUNT(⟦Loan Balance Prior⟧,⟦Interest Rate IN⟧)<2,"",⟦Loan Balance Prior⟧*⟦Interest Rate IN⟧/12)` |
| `PL Interest to Account` | (7000, CC300) | pinned | reference form |
| `PL Plan Pre Tax` | union of its operands' rows: (4000, CC100), (5000, CC200), (6000, ×3), (6100/6200, cost centres with data), (6900, CC300), (7000, CC300) | collector | on each row, the null-wrapped sum of the operands that **have a row with these keys**; e.g. row (6100, CC300): `=IF(COUNT(⟦Other Opex IN⟧)=0,"",N(⟦Other Opex IN⟧))`; row (4000, CC100): `=IF(COUNT(⟦PL Revenue to Account⟧)=0,"",N(⟦PL Revenue to Account⟧))` |
| `PBT Plan` | 1 | filtered aggregates (no `Account` in its grain) | `=IF(COUNT(⟨PL Plan Pre Tax⟩)=0,"",SUMIFS(⟨PL Plan Pre Tax⟩,⟨…Account→PLLine⟩,"Operating revenue")-SUMIFS(…,"Cost of sales")-SUMIFS(…,"Personnel expenses")-SUMIFS(…,"Other operating expenses")-SUMIFS(…,"Depreciation and amortisation")-SUMIFS(…,"Financial expense"))` |
| `Income Tax` | 1 | `max` × input | `=IF(COUNT(⟦PBT Plan⟧,⟦Tax Rate IN⟧)<2,"",MAX(⟦PBT Plan⟧,0)*⟦Tax Rate IN⟧)` |
| `PL Tax to Account` | (8000, CC300) | pinned | reference form |
| `Net Income Plan` | 1 | difference | `=IF(COUNT(⟦PBT Plan⟧,⟦Income Tax⟧)=0,"",N(⟦PBT Plan⟧)-N(⟦Income Tax⟧))` |
| `PL Plan` | rows of `PL Plan Pre Tax` plus (8000, CC300) | collector | as `PL Plan Pre Tax` |

### 4.5 `BS`

| Variable | Rows | Formula in column `c` |
|---|---|---|
| `Revenue Plan Total` | 1 | `SUMIFS` over `PL Plan` with `Account→PLLine` = `"Operating revenue"`, null-wrapped with `COUNTIFS` |
| `Purchases Plan Total` | 1 | sum of two such `SUMIFS` (`"Cost of sales"`, `"Other operating expenses"`) |
| `Opening Cash`, `Opening Receivables`, `Opening Fixed Assets`, `Opening Payables`, `Opening Share Capital`, `Opening Retained Earnings` | 1 each | as `Opening Loans`, with `"Cash"`, `"Trade receivables"`, `"Property, plant and equipment"`, `"Trade payables"`, `"Share capital"`, `"Retained earnings"` |
| `Receivables from DSO` | 1 | `=IF(COUNT(⟦Revenue Plan Total⟧,⟦DSO Days IN⟧)<2,"",⟦Revenue Plan Total⟧*⟦DSO Days IN⟧/30)` |
| `Receivables Plan` | 1 | `=IF(ISNUMBER(⟦Opening Receivables⟧),⟦Opening Receivables⟧,IF(ISNUMBER(⟦Receivables from DSO⟧),⟦Receivables from DSO⟧,""))` |
| `Receivables Prior` | 1 | `delay` form |
| `Receivables Change` | 1 | null-wrapped difference of `Receivables from DSO` and `Receivables Prior` |
| `Payables from DPO`, `Payables Plan`, `Payables Prior`, `Payables Change` | 1 each | as the receivables rows |
| `Fixed Asset Movement` | 1 | null-wrapped `Capex IN − Depreciation` |
| `Fixed Assets Plan`, `Share Capital Plan`, `Retained Earnings Plan` | 1 each | `cumsum(x, 0, s)` form, as `Loan Balance` |
| `Net Cash Flow` | 1 | `=IF(COUNT(a,b,c,d,e,f,g)=0,"",N(a)+N(b)-N(c)+N(d)-N(e)+N(f)+N(g))` over `Net Income Plan`, `Depreciation`, `Receivables Change`, `Payables Change`, `Capex IN`, `Loan Movement`, `Share Capital Movement IN` |
| `Cash Plan` | 1 | `cumsum(x, 0, s)` form |
| `BS … to Account` (seven) | one row each, on accounts 1000, 1100, 1500, 2000, 2500, 3000, 3100 | reference form of its source |
| `BS Plan` | the seven account rows | collector: on each row the reference form of the one transfer that has that account |

### 4.6 `Statements`

| Variable | Rows | Formula in column `c` |
|---|---|---|
| `PL Actual upstream` | (on `Import`) | — |
| `PL ACT part` | rows of `PL Actual upstream` (none in the sample) | `=IF(N(⟦FC Actual Flag⟧)=1,IF(ISNUMBER(⟦PL Actual upstream⟧),⟦PL Actual upstream⟧,""),"")` |
| `PL PLAN part` | rows of `PL Plan` | `=IF(NOT(N(⟦FC Actual Flag⟧)=1),IF(ISNUMBER(⟦PL Plan⟧),⟦PL Plan⟧,""),"")` |
| `PL OUT` | union of the two | collector of the two parts |
| `PL Gross Profit` | rows of `PL OUT` | filter **across a link** ([X-FIL-1]): `=SUMIFS(⟨PL OUT⟩,⟨PL OUT.Account→PLLine⟩,"Operating revenue",⟨PL OUT.Account⟩,$B r,⟨PL OUT.CostCenter⟩,$C r)-SUMIFS(⟨PL OUT⟩,⟨PL OUT.Account→PLLine⟩,"Cost of sales",⟨PL OUT.Account⟩,$B r,⟨PL OUT.CostCenter⟩,$C r)`, null-wrapped with the matching `COUNTIFS` |
| `PL EBITDA`, `PL EBIT`, `PL Profit Before Tax`, `PL Net Income OUT` | rows of `PL OUT` | the same form; the reference to the previous subtotal is aligned (same row) |
| `Gross Margin Pct` | 1 per version (grain `Versions, YearMonth`; `@rollup none`) | `PL Gross Profit` aggregated to the row over `SUMIFS(⟨PL OUT⟩,⟨…Account→PLLine⟩,"Operating revenue")`, null where the denominator is empty or zero |
| `BS Actual upstream` | (on `Import`) | — |
| `BS ACT part`, `BS PLAN part`, `BS OUT` | balance-sheet account rows | as the P&L parts |

`PL Gross Profit` keeps the row's own `Account` and `CostCenter` as criteria:
each row holds its own account's contribution, and the rows add up to gross
profit. Dropping the `Account` criterion would put the full gross profit on
every row — the own-grain behaviour, which is not what the formula says.

### 4.7 `Controls`

| Variable | Rows | Formula in column `c` |
|---|---|---|
| `CHECK BS A` | 1 | `=IF(COUNT(⟨BS OUT⟩)=0,"",ROUND(SUMIFS(⟨BS OUT⟩,<path helper>,"*|Total assets|*")-SUMIFS(⟨BS OUT⟩,<path helper>,"*|Total equity and liabilities|*"),2))` |
| `CHECK BS FINAL` | 1 | `=IF(ISNUMBER(⟦CHECK BS A⟧),IF(ABS(⟦CHECK BS A⟧)>0,⟦CHECK BS A⟧*0+1,""),"")` |

### 4.8 Year totals

From each variable's `@rollup`: flows (`PL …`, movements, `Net Cash Flow`,
`Depreciation`) sum their months; balances (`… Plan`, `Loan Balance`,
`BS OUT`, `Opening …`) take the last month; rates (`COGS Rate IN`,
`Unit Price IN`, `FC Actual Flag`) average; `Gross Margin Pct` (`@rollup
none`) has no year total (companion FML §5.2).

## 5. Expected `Notes` entries

| Variable | Kind | Code | Detail |
|---|---|---|---|
| `Loan Balance`, `Loan Balance Prior`, `Receivables Prior`, `Payables Prior`, `Fixed Assets Plan`, `Share Capital Plan`, `Retained Earnings Plan`, `Cash Plan`, `Depreciation` | assumption | `DELAY-YEAR` | the excerpt crosses from 2026 into 2027; values carry across the boundary |
| (workbook) | assumption | `MAPPING-ONE-WAY` | mappings changed on `Dimensions` do not travel back to the member files |
| `PL Actual upstream`, `PL ACT part` | information | `NO-DATA` | the sample data has no P&L actuals, so these have no rows |

No variable is untranslated.

## 6. Sample data

All amounts in thousands, all-positive storage.

**`2026-12` (opening month)**

| Input | Coordinate | Value |
|---|---|---|
| `FC Actual IN` | — | 1 |
| `Opening Balances IN` and `IMPORT GL Balance` | 1000 Cash | 500 |
| | 1100 Trade receivables | 300 |
| | 1500 Property, plant and equipment | 1 200 |
| | 2000 Trade payables | 200 |
| | 2500 Borrowings | 800 |
| | 3000 Share capital | 600 |
| | 3100 Retained earnings | 400 |

**Every month of `2027`**

| Input | Coordinate | Value |
|---|---|---|
| `Sales Volume IN` | P100 / P200 / P300 | 100 / 50 / 20 |
| `Unit Price IN` | P100 / P200 / P300 | 10 / 25 / 40 |
| `Headcount IN` | CC100 / CC200 / CC300 | 3 / 5 / 2 |
| `Other Opex IN` | 6100 CC300 / 6200 CC100 | 50 / 20 |
| `Existing Depreciation IN` | — | 20 |
| `Loan Repayment IN` | — | 10 |
| `Capex IN` | `2027-03` only | 120 |

**`2027` (year-grained)**

| Input | Coordinate | Value |
|---|---|---|
| `COGS Rate IN` | Hardware / Services | 0.60 / 0.30 |
| `Average Monthly Cost IN` | every cost centre | 4 |
| `Interest Rate IN` | — | 0.06 |
| `Tax Rate IN` | — | 0.20 |
| `DSO Days IN` | — | 15 |
| `DPO Days IN` | — | 30 |

`Loan Drawdown IN` and `Share Capital Movement IN` are empty.

## 7. Verification targets

**Level 14.2** — `CHECK BS A` is `0` in every period column, and `BS OUT`
holds seven populated balance-sheet rows in every period.

**Hand-computed values for `2027-01`:**

| Variable | Value | Working |
|---|---|---|
| `Revenue Plan Total` | 3 050 | 100·10 + 50·25 + 20·40 |
| cost of sales (PLLine) | 1 590 | (1 000 + 1 250)·0.6 + 800·0.3 |
| personnel | 40 | (3 + 5 + 2)·4 |
| other operating expenses | 70 | 50 + 20 |
| `Depreciation` | 20 | no capex before 2027-01; existing 20 |
| `Interest Expense` | 4 | 800·0.06 / 12 |
| `PBT Plan` | 1 326 | 3 050 − 1 590 − 40 − 70 − 20 − 4 |
| `Income Tax` | 265.2 | 1 326·0.2 |
| `Net Income Plan` | 1 060.8 | |
| `Receivables Plan` | 1 525 | 3 050·15 / 30 |
| `Payables Plan` | 1 660 | (1 590 + 70)·30 / 30 |
| `Net Cash Flow` | 1 305.8 | 1 060.8 + 20 − 1 225 + 1 460 − 0 − 10 |
| `Cash Plan` | 1 805.8 | 500 + 1 305.8 |
| `Fixed Assets Plan` | 1 180 | 1 200 + 0 − 20 |
| `Loan Balance` | 790 | 800 − 10 |
| `Retained Earnings Plan` | 1 460.8 | 400 + 1 060.8 |
| total assets | 4 510.8 | 1 805.8 + 1 525 + 1 180 |
| total equity and liabilities | 4 510.8 | 1 660 + 790 + 600 + 1 460.8 |
| `PL Gross Profit`, summed over its rows | 1 460 | 3 050 − 1 590 |

The same targets, in machine-readable form, are in [`targets.json`](targets.json).

## 8. Verification

The workbook in this folder was produced from the FML documents, the member
files and [`sample-data.json`](sample-data.json) by a renderer that follows the
companion specification, and checked against [`targets.json`](targets.json).

| Level (companion FML §14) | Result |
|---|---|
| 14.1 Well-formed | opens in Microsoft Excel; 2 233 formula cells carry cached values; no error values |
| 14.2 Controls and targets | 135 checks — controls, populated positions, row counts and hand-computed values |
| 14.3 Two evaluations | Microsoft Excel: 135/135 pass · independent evaluator (Python `formulas`): 135/135 pass |
| 14.4 Engine | not performed — the model has not been evaluated by an engine with data |

A workbook that passes these levels is a faithful translation of the documents;
it does not prove the model.
