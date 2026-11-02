# Sales and allocation model — Excel translation

This document specifies the workbook that the
[FML to Excel Translation](../../../spec/fml-excel-1.0.md) companion
specification produces from the [sales and allocation example](../), with
sample data and hand-computed values to verify against. The workbook [`sales-allocation.xlsx`](./sales-allocation.xlsx) in this folder follows this
description; see §8 for how it was verified.

What this example adds to the first one:

| Construct | Where |
|---|---|
| a carried price with a reset (`cumsum(0, 0, s)`, `cumsum(x, 0, s)`) | `Pricing` |
| flag arithmetic over 1-or-null flags (`1 − null` reads 1) | `Price eff` |
| a quantity anchor that confines a customer price to planned quantities | `Qty Anchor`, `Price head` |
| lookups from a parent | `Cost to Serve Keys`, `Cost to Serve Result` |
| broadcast of a coarser total across a finer grain | `Item Mix Keys` |
| sparse controls that return an anchor, and a count at board grain | `Controls` |

## 1. Excerpt

| | |
|---|---|
| Rendered version | `Plan` |
| Periods | `2026-12` (actual) and `2027-01` – `2027-03` (plan) — 4 period columns |
| Year totals | `2026` (partial: 2026-12), `2027` (partial: 2027-01 – 2027-03) |
| Data | the sample data of §6 |
| Null profile | null-faithful |

## 2. Sheets and key columns

| # | Sheet | Key columns |
|---|---|---|
| 1 | `Notes` | — |
| 2 | `Dimensions` | — |
| 3 | `Foundation` | — |
| 4 | `Import` | `Customer`, `Item`, `Location` |
| 5 | `Inputs` | `Customer`, `Item`, `Location` |
| 6 | `Pricing` | `Item`, `Customer` |
| 7 | `Revenue` | `Customer`, `Item` |
| 8 | `Cost to Serve` | `Customer`, `Location`, `Item` |
| 9 | `Margin` | `Customer`, `Item` |
| 10 | `Controls` | `Customer`, `Item` |
| 11 | `Source` | — |

## 3. Helper columns

| Sheet | Rows of | Helper | Used by |
|---|---|---|---|
| `Cost to Serve` | `Orders OUT` | `Customer→Location` | `Orders by Location` (aggregation to the parent) |
| `Cost to Serve` | `Cost to Serve Keys`, `Cost to Serve Result` | `Customer→Location` | lookups of `Orders by Location` and `Location Opex OUT` |

## 4. Variables

Notation as in Annex X-A of the companion specification; `c` is the current
period column. Only the translations that differ in kind from example 1 are
written out; merged outputs (`… ACT part`, `… PLAN part`, `… OUT`) follow
example 1 §4.6 exactly.

### 4.1 `Pricing`

| Variable | Rows | Formula in column `c` |
|---|---|---|
| `Net Revenue by Item`, `Qty by Item` | I01–I04 with actuals | aggregation over `Customer`: `=IF(COUNTIFS(⟨V.Item⟩,$B r,⟨V⟩,"<>")=0,"",SUMIFS(⟨V⟩,⟨V.Item⟩,$B r))` |
| `Realised Price` | as above | `=IF(COUNT(⟦Net Revenue by Item⟧,⟦Qty by Item⟧)<2,"",IF(AND(⟦Net Revenue by Item⟧>0,⟦Qty by Item⟧>0),⟦Net Revenue by Item⟧/⟦Qty by Item⟧,""))` |
| `Price Reset` | as above | `=IF(N(⟦FC Actual Flag⟧)=1,IF(ISNUMBER(⟦Realised Price⟧),⟦Realised Price⟧,""),"")` |
| `Price Base` | as above | `cumsum(0, 0, s)`: `=IF(ISNUMBER(⟦Price Reset⟧),⟦Price Reset⟧,IF(ISNUMBER(⟦self⟧ₜ₋₁),⟦self⟧ₜ₋₁,""))` |
| `Price Step` | items with a reset | `Price Change IN * Price Base`: the change where one is entered, empty on every other month |
| `Price Curve` | items with a reset | `cumsum(x, 0, s)`: `=IF(ISNUMBER(⟦Price Reset⟧),⟦Price Reset⟧,IF(COUNT(⟦self⟧ₜ₋₁,⟦Price Step⟧)=0,"",N(⟦self⟧ₜ₋₁)+N(⟦Price Step⟧)))` |
| `Price Set Flag`, `Price Curve Flag` | items | `=IF(ISNUMBER(⟦Price Set IN⟧),1,"")`, likewise for the curve |
| `Price Decided Flag` | items | `=IF(ISNUMBER(⟦Price Set IN⟧),⟦Price Set Flag⟧,IF(ISNUMBER(⟦Price Curve Flag⟧),⟦Price Curve Flag⟧,""))` |
| `Price Fallback Item` | I01–I04 | reference form of `IMPORT List Price` (no time dimension: the value in every period column, §5.3) |
| `Price eff` | items with a set price or a curve (I01–I03) | flag arithmetic, null-faithful: `N(⟦Price Set IN⟧)+N(⟦Price Curve⟧)*(1-N(⟦Price Set Flag⟧))`, guarded on its full-grain operands |
| `Price Factor` | C01–C05 | `=IF(COUNT(⟦Customer Discount IN⟧)=0,"",1-⟦Customer Discount IN⟧)` |
| `Qty Anchor` | (customer, item) pairs with planned quantity | `=IF(ISNUMBER(⟦Qty Plan IN⟧),⟦Qty Plan IN⟧*0+1,"")` |
| `Price head` | rows of `Qty Anchor` | `⟦Price eff⟧*⟦Price Factor⟧*⟦Qty Anchor⟧ + ⟦Price Fallback Item⟧*⟦Price Factor⟧*⟦Qty Anchor⟧*(1-N(⟦Price Decided Flag⟧))`, each product null-faithful — `Price eff` is broadcast across customers and `Price Factor` across items; the anchor, the only full-grain operand, gives the rows (FML 1.0 [EVAL-4a]) |

Two points an agent gets wrong without this specification:

- **`Price head` has exactly the rows of `Qty Anchor`.** Rendering it over every
  item × customer is the dense product the anchor exists to prevent (FML 1.0
  [SPARSE-5]); in a workbook it shows prices for combinations nobody plans.
- **`1 − N(flag)` reads 1 when the flag is empty.** The flags hold 1 or null,
  never 0, so the fallback term vanishes exactly where a set price or a curve
  exists.
- **The list-price fallback lives on `Price head`, not on `Price eff`.** In
  `Price eff` the item-level list price would only be a value on the cells of
  the set price and the curve, and a new item has neither (FML 1.0 [EVAL-4],
  consequence 5); on `Price head` the quantity anchor places the cell.

### 4.2 `Revenue`

| Variable | Rows | Formula |
|---|---|---|
| `Net Revenue Plan` | rows of `Qty Anchor` | `=IF(COUNT(⟦Qty Plan IN⟧,⟦Price head⟧)<2,"",⟦Qty Plan IN⟧*⟦Price head⟧)` |
| `Net Revenue OUT`, `Sales Qty OUT` and their parts | union of actual and plan rows | example 1 §4.6 |

### 4.3 `Cost to Serve`

| Variable | Rows | Formula |
|---|---|---|
| `Orders by Location` | WH1, WH2 | aggregation to the parent: `=SUMIFS(⟨Orders OUT⟩,⟨Orders OUT.Customer→Location⟩,$C r)`, null-wrapped |
| `Cost to Serve Keys` | C01–C05 | lookup: `=IF(COUNT(⟦Orders OUT⟧)=0,"",IF(SUMIFS(⟨Orders by Location⟩,⟨Orders by Location.Location⟩,<helper Customer→Location>)>0,⟦Orders OUT⟧/SUMIFS(⟨Orders by Location⟩,⟨Orders by Location.Location⟩,<helper Customer→Location>),""))` |
| `Cost to Serve Result` | C01–C05 | `=IF(COUNT(⟦Cost to Serve Keys⟧)=0,"",SUMIFS(⟨Location Opex OUT⟩,⟨Location Opex OUT.Location⟩,<helper Customer→Location>)*⟦Cost to Serve Keys⟧)` |
| `Net Revenue at Customer` | C01–C05 | aggregation over `Item` |
| `Item Mix Keys` | rows of `Net Revenue OUT` | `=IF(COUNT(⟦Net Revenue OUT⟧,⟦Net Revenue at Customer⟧)<2,"",IF(⟦Net Revenue at Customer⟧>0,⟦Net Revenue OUT⟧/⟦Net Revenue at Customer⟧,""))` — the customer total is broadcast to each of the customer's items |
| `Cost to Serve OUT` | rows of `Item Mix Keys` | `=IF(COUNT(⟦Cost to Serve Result⟧,⟦Item Mix Keys⟧)<2,"",⟦Cost to Serve Result⟧*⟦Item Mix Keys⟧)` |

### 4.4 `Margin`

| Variable | Rows | Formula |
|---|---|---|
| `COGS OUT` | rows of `Sales Qty OUT` | product with `Unit Cost IN` (broadcast across customers and months) |
| `Contribution OUT` | union of its operands' rows | `=IF(COUNT(a,b,c)=0,"",N(a)-N(b)-N(c))` over `Net Revenue OUT`, `COGS OUT`, `Cost to Serve OUT` |
| `Contribution Margin Pct` | 1 per version (grain `Versions, YearMonth`; `@rollup formula`, a Farseer extension) | `Contribution OUT` aggregated to the row over `Net Revenue OUT` aggregated to the row, null where the denominator is empty or zero; the year total is recomputed from the operands' year totals |

### 4.5 `Controls`

| Variable | Rows | Formula |
|---|---|---|
| `CHECK Allocation A` | 1 | `=IF(COUNT(⟨Cost to Serve OUT⟩,⟨Location Opex OUT⟩)=0,"",ROUND(SUM(⟨Cost to Serve OUT⟩)-SUM(⟨Location Opex OUT⟩),2))` |
| `CHECK Allocation FINAL` | 1 | as `CHECK BS FINAL` in example 1 |
| `Price Present Flag` | rows of `Qty Anchor` | `=IF(AND(ISNUMBER(⟦Price head⟧),N(⟦Price head⟧)>0),⟦Qty Anchor⟧,"")` |
| `CHECK Price Missing Flag` | rows of `Qty Anchor` | `=IF(ISNUMBER(⟦Price Present Flag⟧),"",⟦Qty Anchor⟧)` |
| `CHECK Price Missing FINAL` | 1 | `=IF(COUNT(⟨CHECK Price Missing Flag⟩)=0,"",SUM(⟨CHECK Price Missing Flag⟩))` |
| `Price Known Anchor` | rows of `Qty Anchor` | `=IF(COUNT(⟦Qty Anchor⟧,⟦Price Decided Flag⟧)<2,"",⟦Qty Anchor⟧*⟦Price Decided Flag⟧)` |
| `CHECK Price Fallback Flag`, `… FINAL` | as the missing-price pair | with `Price Known Anchor` in place of `Price Present Flag` |

## 5. Expected `Notes` entries

| Variable | Kind | Code | Detail |
|---|---|---|---|
| `Price Base`, `Price Curve` | assumption | `DELAY-YEAR` | the carry crosses from 2026 into 2027 |
| `Price Reset` | assumption | — | relies on enumeration by condition (FML 1.0 [EVAL-6a]); in the workbook the flag row decides directly |
| (workbook) | assumption | `MAPPING-ONE-WAY` | |

No variable is untranslated.

## 6. Sample data

**`2026-12` — actuals** (`FC Actual IN` = 1)

| Customer | Item | `IMPORT Sales Qty` | `IMPORT Net Revenue` |
|---|---|---|---|
| C01 | I01 | 100 | 100 |
| C04 | I01 | 200 | 200 |
| C02 | I02 | 50 | 100 |
| C05 | I02 | 150 | 300 |
| C03 | I03 | 80 | 120 |

`IMPORT Orders`: C01 10, C02 5, C03 5, C04 20, C05 10.
`IMPORT Location Opex`: WH1 120, WH2 180.
`IMPORT List Price` (no period): I01 1.20, I02 2.40, I03 1.80, I04 3.00.

**`2027-01` – `2027-03` — plan inputs, the same in each month unless stated**

| Customer | Item | `Qty Plan IN` |
|---|---|---|
| C01 | I01 | 120 |
| C02 | I02 | 60 |
| C03 | I03 | 100 |
| C04 | I01 | 220 |
| C04 | I04 | 50 |
| C05 | I02 | 160 |

| Input | Values |
|---|---|
| `Price Change IN` | I01: 0.05 in `2027-02` only |
| `Price Set IN` | I03: 1.60 in `2027-03` only |
| `Customer Discount IN` (2027) | C01 0, C02 0, C03 0.10, C04 0, C05 0.05 |
| `Unit Cost IN` (2026 and 2027) | I01 0.50, I02 1.00, I03 0.70, I04 1.50 |
| `Orders Plan IN` | C01 12, C02 6, C03 6, C04 24, C05 12 |
| `Location Opex Plan IN` | WH1 150, WH2 250 |

The zero discounts are entered, not left empty: `Price Factor = 1 − discount`
has no cell where the discount is empty, and `CHECK Price Missing Flag` would
then flag every planned quantity of that customer.

Item I04 has no actual sales, so it has no realised price and no curve: it is
priced from the list.

## 7. Verification targets

**Prices (`Price eff`)**

| Item | 2026-12 | 2027-01 | 2027-02 | 2027-03 | Source |
|---|---|---|---|---|---|
| I01 | 1.00 | 1.00 | 1.05 | 1.05 | realised 300/300, +5 % of 1.00 from 2027-02 |
| I02 | 2.00 | 2.00 | 2.00 | 2.00 | realised 400/200 |
| I03 | 1.50 | 1.50 | 1.50 | 1.60 | realised 120/80; set price in 2027-03 |
| I04 | — | — | — | — | no decided price: priced from the list on `Price head` (below) |

**Customer prices (`Price head`) and revenue (`Net Revenue Plan`)**

| Customer, item | `Price head` 2027-01 / 2027-02 / 2027-03 | Revenue 2027-01 / 2027-02 / 2027-03 |
|---|---|---|
| C01, I01 | 1.00 / 1.05 / 1.05 | 120 / 126 / 126 |
| C02, I02 | 2.00 / 2.00 / 2.00 | 120 / 120 / 120 |
| C03, I03 | 1.35 / 1.35 / 1.44 | 135 / 135 / 144 |
| C04, I01 | 1.00 / 1.05 / 1.05 | 220 / 231 / 231 |
| C04, I04 | 3.00 / 3.00 / 3.00 | 150 / 150 / 150 |
| C05, I02 | 1.90 / 1.90 / 1.90 | 304 / 304 / 304 |
| **Total** | | **1 049 / 1 066 / 1 075** |

`Price head` has exactly 6 rows — one per planned (customer, item) pair.

**Period totals**

| | 2026-12 | 2027-01 | 2027-02 | 2027-03 |
|---|---|---|---|---|
| `Net Revenue OUT` | 820 | 1 049 | 1 066 | 1 075 |
| `COGS OUT` | 406 | 535 | 535 | 535 |
| `Cost to Serve OUT` | 300 | 400 | 400 | 400 |
| `Contribution OUT` | 114 | 114 | 131 | 140 |
| `Contribution Margin Pct` | 13.90 % | 10.87 % | 12.29 % | 13.02 % |
| `CHECK Allocation A` | 0 | 0 | 0 | 0 |
| `CHECK Price Missing FINAL` | empty | empty | empty | empty |
| `CHECK Price Fallback FINAL` | empty | 1 | 1 | 1 |

`CHECK Price Fallback FINAL` reads 1 in each plan month: the one planned pair
(C04, I04) priced from the list. That is the intended warning, not a failure.

**Cost to serve, `2027-01`**

| Customer | Key | Result | Items |
|---|---|---|---|
| C01 | 12/24 = 0.5 | 75.00 | I01 75.00 |
| C02 | 6/24 = 0.25 | 37.50 | I02 37.50 |
| C03 | 6/24 = 0.25 | 37.50 | I03 37.50 |
| C04 | 24/36 = 0.6667 | 166.67 | I01 99.10 (220/370), I04 67.57 (150/370) |
| C05 | 12/36 = 0.3333 | 83.33 | I02 83.33 |
| **Total** | | **400.00** | **400.00** |

The same targets, in machine-readable form, are in [`targets.json`](targets.json).

## 8. Verification

The workbook in this folder was produced from the FML documents, the member
files and [`sample-data.json`](sample-data.json) by a renderer that follows the
companion specification, and checked against [`targets.json`](targets.json).

| Level (companion FML §14) | Result |
|---|---|
| 14.1 Well-formed | opens in Microsoft Excel; 895 formula cells carry cached values; no error values |
| 14.2 Controls and targets | 54 checks — controls, populated positions, row counts and hand-computed values |
| 14.3 Two evaluations | Microsoft Excel: 54/54 pass · independent evaluator (Python `formulas`): 54/54 pass |
| 14.4 Engine | not performed — the model has not been evaluated by an engine with data |

A workbook that passes these levels is a faithful translation of the documents;
it does not prove the model.
