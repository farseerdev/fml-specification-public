# Examples

| Example | Shows |
|---|---|
| [`sales-allocation/`](sales-allocation/) | Driver-based sales: a price carried from realised prices with planner changes, set price and list-price fallback, a customer price anchored on planned quantity, cost to serve allocated by orders and revenue mix, and missing-price and list-price controls. |
| [`multi-entity-fx/`](multi-entity-fx/) | Two entities with their own local charts and currencies on one group chart: entity-pinned imports, a rate looked up through two parents (currency and rate type), a translation reserve placed by a pinned transfer, and balance identity before and after translation. |
| [`three-statement/`](three-statement/) | A complete planning model: chart of accounts whose parents are P&L and balance-sheet lines, version-free actuals merged with the plan by a forecast flag, driver-based revenue, personnel, depreciation and financing, pinned transfer variables collected onto accounts, P&L subtotals filtered through a parent, a balance sheet that balances by construction, and an identity control. |
| [`workforce/`](workforce/) | Positions with contract dates, headcount derived from dates, salary elements pinned to their members, employer contributions on liable elements by a classifier parent, a raise from a month number, ledger-grain output over two parents, and a payroll variance on closed periods. |

Every `.fml` document parses and round-trips with the reference parser.
`multi-entity-fx` and `three-statement` are standard FML only. The other two
use one Farseer extension each: their margin or cost-per-FTE ratio carries
`@rollup formula`, so that the quarter and the year are recomputed from the
totals (Farseer Implementation Profile §4.2). The three-statement model is the
specification's Annex F and has been evaluated with data; the other three have
not. Run the checks of §22 of the specification
before relying on their numbers.

Each example has an `excel/` folder with the workbook that the
[FML to Excel Translation](../spec/fml-excel-1.0.md) companion specification
produces from it:

| File | Content |
|---|---|
| `<example>.xlsx` | the translated workbook — live formulas with cached values |
| `README.md` | the workbook's structure, the translations worth reading, expected `Notes` entries, verification targets and results |
| `sample-data.json` | the data the workbook was rendered with |
| `targets.json` | machine-readable verification targets, computed independently of the renderer |

Every workbook was checked in Microsoft Excel and in an independent formula
evaluator against its `targets.json`.

Layout of an example:

```text
dimensions.fml          every dimension declaration, with its parents (FML §6.1, §7)
variables/*.fml         variable documents, one per block
dimensions/*.csv        the member files the declarations name (FML §6.4)
```
