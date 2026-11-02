# Financial Modeling Language (FML)

**Open Specification — Version 1.0 (draft)**

*An open specification developed by Farseer*

Financial Modeling Language (FML) is an open specification originally developed
and published by Farseer.

The specification may be freely used, copied, implemented, and adapted,
including for commercial purposes, provided that appropriate attribution is
given to Farseer and any modifications are clearly identified.

---

FML is a declarative, text-based language for multidimensional financial
planning and analysis models. A model is a set of plain-text documents that
declare the **dimensions** a business is analysed by, with their **parents**,
and the **variables** that hold imported actuals, planner inputs,
calculations and reported outputs. Each formula is written once and holds at
every coordinate of its variable's grain; quarters, years and every rollup
along the dimension graph follow without being written.

```fml
dimension Product from "dimensions/Product.csv"
  @parent Category
dimension Category from "dimensions/Category.csv"

"Sales Volume IN" { Product, Versions, YearMonth }
"Unit Price IN"   { Product, Versions, YearMonth }
  @rollup average

"Sales Revenue"   { Product, Versions, YearMonth } = "Sales Volume IN" * "Unit Price IN"
  @readonly true
```

## The name

FML stands for **Financial Modeling Language**. Two other readings are just as
true:

- **Free Modeling Language** — open, under CC BY 4.0;
- **Farseer Modeling Language** — where it was born.

There is a fourth reading, usually muttered at 2 a.m. over a model whose
balance sheet no longer balances. That one is the reason the other three exist.

## Read the specification

| | |
|---|---|
| **Specification** | [`spec/fml-1.0.md`](spec/fml-1.0.md) — the language: normative, self-contained |
| **Modelling Guide** | [`spec/fml-modelling-guide-1.0.md`](spec/fml-modelling-guide-1.0.md) — informative: how to build correct, fast, maintainable models |
| **Agent Protocol** | [`spec/fml-agent-protocol-1.0.md`](spec/fml-agent-protocol-1.0.md) — normative for AI agents that write FML |
| **Grammar** | [`grammar/fml.ebnf`](grammar/fml.ebnf) (identical to Annex A) |
| **Farseer profile** | [`spec/fml-farseer-profile-1.0.md`](spec/fml-farseer-profile-1.0.md) — informative: what Farseer, the reference implementation, accepts beyond the standard, and its interchange format |
| **Excel translation** | [`spec/fml-excel-1.0.md`](spec/fml-excel-1.0.md) — companion specification: how an FML model becomes a workbook of live formulas |
| **Example models** | [`examples/`](examples/) — three-statement, sales and allocation, workforce, multi-entity with FX; each with member files and a translated workbook |
| **Linter and formatter** | [`tools/fml-lint/`](tools/fml-lint/) — parses models, reports the diagnostics of Annex C, emits canonical form |
| **Conformance tests** | [`tests/`](tests/) — syntax, model and evaluation vectors |
| **Reference renderer** | [`tools/fml2xlsx/`](tools/fml2xlsx/) — renders an FML model as an Excel workbook and verifies it |
| **For AI agents** | [`AGENTS.md`](AGENTS.md) and [`llms.txt`](llms.txt) |

Three documents:

1. **The Specification** — lexical structure, syntax, dimensions and parents,
   variables, properties, formula expressions, **evaluation semantics**, the
   function library, time and versions, number formats, diagnostics, and the
   model manifest.
2. **The Modelling Guide** — model architecture, naming, **dimension design**,
   grain alignment, sparsity, forecasting, controls, performance, a catalogue of
   modeling patterns (P&L, balance sheet, cash flow, multi-entity,
   consolidation, workforce, allocation, pricing) and of anti-patterns.
3. **The Agent Authoring Protocol** — a step-by-step procedure, decision tables
   and a self-review checklist for automated agents that generate or modify FML
   models.

Where to start:

- **Writing models:** Specification §3 (concepts) and §10–§11 (formulas and
  evaluation), then the Modelling Guide.
- **Implementing a parser or linter:** Specification §4–§9, §15, Annexes A and C,
  and the tests.
- **Implementing an engine:** all of the Specification, and the evaluation tests.
- **Building an AI agent:** Specification §3 and §11, and the Agent Protocol in full.

## Repository layout

```text
spec/fml-1.0.md              the specification
spec/fml-modelling-guide-1.0.md  the Modelling Guide (informative)
spec/fml-agent-protocol-1.0.md   the Agent Authoring Protocol
spec/fml-farseer-profile-1.0.md  the Farseer implementation profile (informative)
spec/fml-excel-1.0.md        companion: FML to Excel translation
grammar/fml.ebnf             the grammar, machine-readable
examples/                    four complete example models, each with its translated workbook
tools/fml-lint/              reference linter and formatter (Apache 2.0)
tools/fml2xlsx/              reference renderer for the Excel translation, and its verification (Apache 2.0)
tests/                       conformance vectors and their runner
AGENTS.md                    instructions for AI agents
llms.txt                     index for language-model tooling
LICENSE                      CC BY 4.0 legal code
NOTICE                       required attribution
CONTRIBUTING.md              how the specification evolves
CHANGELOG.md                 revision history
```

## File extension

FML documents use the extension **`.fml`**. Farseer's tooling also reads and
writes **`.fsl`** (Farseer Implementation Profile §7.3).

## Reference implementation

FML originated as the text format of the [Farseer](https://farseer.com) planning
platform, which is the reference implementation. The specification defines the
language so that a second engine can implement it without reference to
Farseer. What Farseer accepts beyond the standard — calculation and activation
flags, top-down entry, compound members, measures, a `formula` rollup, growth
functions — is not part of FML; it is documented, together with Farseer's
implementation-defined choices, in the
[Farseer Implementation Profile](spec/fml-farseer-profile-1.0.md).

## License and attribution

© 2026 Farseer d.o.o., Zagreb, Croatia.

The specification, grammar and examples are licensed under the
[Creative Commons Attribution 4.0 International License](LICENSE) (CC BY 4.0).
You may use, copy, implement and adapt them, including commercially, provided
you give appropriate attribution to Farseer and clearly identify any
modifications. See [`NOTICE`](NOTICE) for the attribution text. The code in
`tools/` and `tests/` is licensed under the [Apache License 2.0](tools/LICENSE). How the
specification evolves: [`GOVERNANCE.md`](GOVERNANCE.md).

## Versioning

The specification uses `MAJOR.MINOR` versions. Rule identifiers (`[EVAL-23]`),
anti-pattern identifiers (`AP-01`) and diagnostic codes (`FML-W1105`) are stable
within a major version. See [`CONTRIBUTING.md`](CONTRIBUTING.md).
