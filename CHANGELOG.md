# Changelog

All notable changes to the FML specification are recorded here. Versions
follow `MAJOR.MINOR` (see CONTRIBUTING.md).

## 1.0 — draft

### Changes during the draft

- **2026-10-28** — A second `@parent` naming the same parent dimension on
  one declaration is an error (`FML-E0707`), even when its modifiers are
  identical. Linting and formatting reject it [PARENT-4].
- **2026-10-28** — Dimension declarations (proposal). Every dimension other
  than a system dimension is declared with a `dimension` statement: members
  listed inline (`{ … }`), in a member file (`from "…"`), or not listed at all
  when they are data. Its properties are `@parent` (with `many` for several
  parents and `required` for no empty parent cell), `@attribute`, `@null`, `@semantic time`, `@rollup none`, `@folder`
  and `@desc` (§6.1, [DOC-6], [DIM-12], [DIM-13]). A name never creates a
  dimension or a member, and no processor adds a NULL member: only `@null`
  declares one (§6.5). The link statement, the time statement and the member
  file directives are retired; a relation between dimensions is a **parent**,
  and the [LINK-n] rules become [PARENT-n] (§7). Member files are plain
  RFC 4180 CSV in UTF-8, with no comments, no blank lines and no trimming, and
  their header cells match parent and attribute names exactly (§6.4).
- **2026-10-27** — [EVAL-4a] the calendar exception: a reference held by
  `YearMonth` carries `Years` and `Months`, so a yearly formula over monthly data
  has its cells where that data is; [EVAL-28a] and §11.10 say so, with an
  example, and eval vector `e16-monthly-in-yearly` pins it. The reference
  renderer counts a monthly reference as carrying them. Implementation profile,
  [FP-7]: a `@rollup formula` read directly evaluates a quotient with a null
  numerator as null.

### The first version

It consists of:

- **FML Specification 1.0** (`spec/fml-1.0.md`) — the language: lexical
  structure, documents and the model manifest, dimensions and member files,
  time dimensions (system ones and those a model declares with `time`),
  links, variables, properties, formulas, evaluation semantics, function
  library, time and versions, number formats, static validation; and the
  annexes (grammar, function reference, diagnostics, implementation profiles,
  guide for spreadsheet modelers, complete example model).
- **FML Modelling Guide 1.0** (`spec/fml-modelling-guide-1.0.md`, informative)
  — architecture, naming, dimension design, grain, sparsity, versions and
  forecasts, controls, performance, patterns and anti-patterns.
- **FML Agent Authoring Protocol 1.0** (`spec/fml-agent-protocol-1.0.md`) —
  the procedure automated agents follow when they write or change a model.
- **FML to Excel Translation 1.0** (`spec/fml-excel-1.0.md`) and the reference
  renderer `tools/fml2xlsx/`.
- **Farseer Implementation Profile 1.0** (`spec/fml-farseer-profile-1.0.md`,
  informative).
- **Reference linter and formatter** (`tools/fml-lint/`) and **conformance
  tests** (`tests/`).
- **Examples** — three-statement, sales and allocation, workforce, multi-entity
  with currency translation — each with member files, a manifest, a translated
  workbook, sample data and verification targets.
