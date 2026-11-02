#!/usr/bin/env python3
"""fml_lint — reference linter and formatter for FML 1.0 (spec/fml-1.0.md).

usage:
  python3 fml_lint.py lint <model-dir-or-file> [--profile lenient|standard|strict] [--json]
  python3 fml_lint.py fmt <file.fml>

`lint` prints `path:line:col CODE message` per diagnostic and exits 1 when any
diagnostic is an error under the chosen profile (§15.4). `fmt` prints the
canonical form of a document (§5.6); it refuses a document with syntax errors.

Licensed under the Apache License 2.0 — see tools/LICENSE.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fmllint import canon                                  # noqa: E402
from fmllint.checks import check                           # noqa: E402
from fmllint.diagnostics import PROFILES, SEVERITY_WORD, Sink, severity  # noqa: E402
from fmllint.model import load                             # noqa: E402
from fmllint.syntax import parse_document                  # noqa: E402


def lint(target, profile="standard"):
    """Lint a model directory or one file. Returns [(Diag, severity letter)], filtered by profile."""
    sink = Sink()
    model = load(target, sink)
    check(model, sink)
    out = []
    for d in sink.sorted():
        sev = severity(d.code, profile)
        if sev is not None:
            out.append((d, sev))
    return out


def format_text(text, path="<document>"):
    """(canonical text or None, [syntax diagnostics as strings])."""
    sink = Sink()
    doc = parse_document(text, sink.at(path), path)
    errs = [d for d in sink.sorted() if d.code[4] == "E"]
    if errs:
        return None, [f"{d.path}:{d.line}:{d.col} {d.code} {d.message}" for d in errs]
    return canon.emit(doc), []


def main(argv=None):
    ap = argparse.ArgumentParser(prog="fml_lint.py", description="Reference linter and formatter for FML 1.0")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("lint", help="report diagnostics (Annex C)")
    pl.add_argument("target", help="a model directory, an .fml document or a member file (.csv)")
    pl.add_argument("--profile", choices=PROFILES, default="standard")
    pl.add_argument("--json", action="store_true", help="print the diagnostics as a JSON array")
    pf = sub.add_parser("fmt", help="print the canonical form of a document (§5.6)")
    pf.add_argument("file")
    a = ap.parse_args(argv)

    if a.cmd == "lint":
        if not os.path.exists(a.target):
            print(f"fml_lint: no such file or directory: {a.target}", file=sys.stderr)
            return 2
        diags = lint(a.target, a.profile)
        if a.json:
            print(json.dumps([d.as_dict(a.profile) for d, _ in diags], indent=2, ensure_ascii=False))
        else:
            for d, sev in diags:
                note = "" if sev == d.code[4] else f"[{SEVERITY_WORD[sev]} under {a.profile}] "
                print(f"{d.path}:{d.line}:{d.col} {d.code} {note}{d.message}")
            n = {k: sum(1 for _, s in diags if s == k) for k in "EWI"}
            print(f"{n['E']} error(s), {n['W']} warning(s), {n['I']} info — profile {a.profile}", file=sys.stderr)
        return 1 if any(s == "E" for _, s in diags) else 0

    text = open(a.file, encoding="utf-8").read()
    out, errs = format_text(text, a.file)
    if out is None:
        for e in errs:
            print(e, file=sys.stderr)
        return 1
    sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
