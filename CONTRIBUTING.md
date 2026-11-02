# Contributing to the FML specification

FML is an open specification. Proposals, corrections and questions are welcome
as GitHub issues and pull requests.

## What makes a good change

- **Corrections** of a rule that does not match engine behaviour: include a
  minimal model (FML plus member data) that reproduces the behaviour, the
  observed result and the expected result.
- **New rules or patterns**: state the problem the rule prevents, show the
  failing and the correct form in FML, and say whether it is normative (a
  language rule) or guidance (the Modelling Guide).
- **Clarifications**: point to the sentence that can be read two ways.

Examples in the specification must use generic names. Do not include names,
data or identifiers of any real organisation's model.

## Versioning

- **MINOR** (1.0 → 1.1): clarifications, new guidance, new diagnostics, new
  functions or properties that do not change the meaning of any conforming
  document.
- **MAJOR** (1.x → 2.0): any change that alters the meaning of a conforming
  document or removes a construct.

Rule identifiers (`[EVAL-23]`), anti-pattern identifiers (`AP-01`) and
diagnostic codes (`FML-W1105`) are never reused for a different meaning within
a major version. A withdrawn rule keeps its identifier, marked *withdrawn*.

Every published change is recorded in `CHANGELOG.md` and in Annex G of the
specification.

## Editorial conventions

- Normative statements use the key words of BCP 14 (RFC 2119, RFC 8174) in
  capitals.
- FML examples use Style A naming (Guide §2.2) and qualified member references.
- Every FML document in `examples/` must pass `tools/fml-lint` under the
  `standard` profile, and `python3 tests/run.py` must pass.

## License of contributions

By contributing you agree that your contribution is licensed under the
Creative Commons Attribution 4.0 International License, as is the rest of the
specification, and — for code under `tools/` and `tests/` — under the Apache
License 2.0. Sign off each commit (`git commit -s`, Developer Certificate of Origin
1.1). How changes are decided is described in [GOVERNANCE.md](GOVERNANCE.md).
