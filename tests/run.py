#!/usr/bin/env python3
"""tests/run.py — runs the FML 1.0 conformance suite.

  syntax/valid/*.fml     must lint without errors; an optional `# expect:` line lists
                         warnings or information the file must produce; each must
                         also satisfy the round trip [DOC-4]
  syntax/invalid/*.fml   must report every code of its `# expect:` line, and no other
                         error than those of its `# expect:` and `# may:` lines
  models/<case>/         lint under the profile of expect.json; the reported
                         (code, file, line) multiset must equal its `diagnostics`
  eval/<case>/           lint without errors, then render with tools/fml2xlsx, evaluate
                         with its independent evaluator and check excel/targets.json
                         (minus the assertions eval/skip.json lists)
  examples/*/            lint without errors under `standard`; every .fml round-trips
  dimensions             fmt puts the declarations first, sorted, properties in order; they are
                         information content (§5.5, §5.6)

usage: python3 tests/run.py [--no-eval] [--verbose]
Evaluation needs a Python with openpyxl and formulas: FML_EVAL_PYTHON=<python>, or the
interpreter running this script.
"""
import copy
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
LINT_DIR = os.path.join(REPO, "tools", "fml-lint")
RENDER_DIR = os.path.join(REPO, "tools", "fml2xlsx")
sys.path.insert(0, LINT_DIR)

import fml_lint                                             # noqa: E402
from fmllint import canon                                  # noqa: E402
from fmllint.diagnostics import Sink                       # noqa: E402
from fmllint.syntax import parse_document                  # noqa: E402

VERBOSE = "--verbose" in sys.argv
results = {}                                                # section -> [passed, failed, skipped]
failures = []


def record(section, ok, label, detail=""):
    r = results.setdefault(section, [0, 0, 0])
    if ok is None:
        r[2] += 1
        if VERBOSE:
            print(f"  skip  {label} {detail}")
        return
    r[0 if ok else 1] += 1
    if not ok:
        failures.append(f"[{section}] {label}: {detail}")
        print(f"  FAIL  {label}: {detail}")
    elif VERBOSE:
        print(f"  ok    {label}")


def header_codes(path, tag):
    out = []
    for line in open(path, encoding="utf-8-sig", errors="replace").read().splitlines()[:5]:
        m = re.match(r"\s*#\s*%s:\s*(.*)$" % tag, line)
        if m:
            out += re.findall(r"FML-[EWI]\d{4}", m.group(1))
    return out


def round_trip(path):
    """[DOC-4] parse(emit(parse(d))) ≡ parse(d); also emit is idempotent."""
    text = open(path, encoding="utf-8").read()
    s1 = Sink()
    d1 = parse_document(text, s1.at(path), path)
    if any(d.code[4] == "E" for d in s1.items):
        return False, "the document has syntax errors"
    out = canon.emit(d1)
    s2 = Sink()
    d2 = parse_document(out, s2.at("<canonical>"), "<canonical>")
    errs = [f"{d.line}:{d.col} {d.code} {d.message}" for d in s2.items if d.code[4] == "E"]
    if errs:
        return False, "canonical form does not parse: " + "; ".join(errs[:3])
    if canon.info_content(d1) != canon.info_content(d2):
        a, b = canon.info_content(d1), canon.info_content(d2)
        diff = [n for n in set(a[1]) | set(b[1]) if a[1].get(n) != b[1].get(n)]
        ddiff = [n for n in set(a[0]) | set(b[0]) if a[0].get(n) != b[0].get(n)]
        return False, f"information content differs (dimensions: {ddiff[:3]}; variables: {diff[:3]})"
    if canon.emit(d2) != out:
        return False, "canonical form is not stable: fmt(fmt(d)) != fmt(d)"
    return True, ""


def codes_of(diags, letters="EWI"):
    return [d.code for d, sev in diags if sev in letters]


# ----------------------------------------------------------------------------- syntax
def run_syntax():
    print("syntax vectors")
    for f in sorted(glob.glob(os.path.join(HERE, "syntax", "valid", "*.fml"))):
        name = os.path.relpath(f, HERE)
        diags = fml_lint.lint(f, "standard")
        errs = [f"{d.line}:{d.col} {d.code} {d.message}" for d, s in diags if s == "E"]
        want = header_codes(f, "expect")
        got = set(codes_of(diags))
        missing = [c for c in want if c not in got]
        ok = not errs and not missing
        record("syntax/valid", ok, name, "; ".join(errs[:3]) + (f" missing {missing}" if missing else ""))
        ok, why = round_trip(f)
        record("round trip", ok, name, why)
    for f in sorted(glob.glob(os.path.join(HERE, "syntax", "invalid", "*.fml"))):
        name = os.path.relpath(f, HERE)
        want, may = header_codes(f, "expect"), header_codes(f, "may")
        if not want:
            record("syntax/invalid", False, name, "no `# expect:` line")
            continue
        diags = fml_lint.lint(f, "standard")
        got = set(codes_of(diags))
        missing = [c for c in want if c not in got]
        extra = sorted({d.code for d, s in diags if s == "E" and d.code not in want and d.code not in may})
        record("syntax/invalid", not missing and not extra, name,
               (f"missing {missing} " if missing else "") + (f"unexpected errors {extra}" if extra else ""))


# ----------------------------------------------------------------------------- models
def run_models():
    print("model vectors")
    for d in sorted(glob.glob(os.path.join(HERE, "models", "*", ""))):
        case = os.path.basename(os.path.dirname(d))
        exp = json.load(open(os.path.join(d, "expect.json")))
        profile = exp.get("profile", "standard")
        diags = fml_lint.lint(d.rstrip("/"), profile)
        root = d.rstrip("/")
        got = Counter((x.code, os.path.relpath(x.path, root), x.line) for x, _ in diags)
        want = Counter((e["code"], e["file"], e["line"]) for e in exp["diagnostics"])
        detail = ""
        if got != want:
            detail = f"missing {sorted((want - got).elements())} unexpected {sorted((got - want).elements())}"
        record("models", got == want, case, detail)
        for p, code in exp.get("exit", {}).items():
            r = subprocess.run([sys.executable, os.path.join(LINT_DIR, "fml_lint.py"), "lint", root, "--profile", p],
                               capture_output=True, text=True)
            record("models", r.returncode == code, f"{case} exit under {p}", f"expected {code}, got {r.returncode}")
        for p, n in exp.get("counts", {}).items():
            k = len(fml_lint.lint(root, p))
            record("models", k == n, f"{case} count under {p}", f"expected {n}, got {k}")


# ----------------------------------------------------------------------------- eval
def eval_python():
    py = os.environ.get("FML_EVAL_PYTHON") or sys.executable
    r = subprocess.run([py, "-c", "import openpyxl, formulas"], capture_output=True, text=True)
    return py if r.returncode == 0 else None


def matches(t, s):
    if s.get("var") != t.get("var"):
        return False
    if "period" in s and s["period"] != t.get("period"):
        return False
    return all(t.get("keys", {}).get(k) == v for k, v in s.get("keys", {}).items())


def run_eval(skip_eval):
    print("evaluation vectors")
    skips = json.load(open(os.path.join(HERE, "eval", "skip.json")))
    py = None if skip_eval else eval_python()
    if py is None and not skip_eval:
        print("  (no Python with openpyxl and formulas: set FML_EVAL_PYTHON; rendering skipped)")
    work = tempfile.mkdtemp(prefix="fml-eval-")
    try:
        for d in sorted(glob.glob(os.path.join(HERE, "eval", "*", ""))):
            root = d.rstrip("/")
            case = os.path.basename(root)
            diags = fml_lint.lint(root, "standard")
            errs = [f"{os.path.relpath(x.path, root)}:{x.line} {x.code} {x.message}" for x, s in diags if s == "E"]
            record("eval (lint)", not errs, case, "; ".join(errs[:3]))
            sk = skips.get(case, {})
            if py is None or sk.get("all"):
                record("eval", None, case, f"({sk.get('kind', 'no evaluator')}: {sk.get('reason', '')})")
                continue
            targets = json.load(open(os.path.join(root, "excel", "targets.json")))
            kept = copy.deepcopy(targets)
            drop = sk.get("targets", [])
            kept["values"] = [t for t in targets.get("values", []) if not any(matches(t, s) for s in drop if "period" in s)]
            kept["row_counts"] = [t for t in targets.get("row_counts", [])
                                  if not any(s.get("rows") and s["var"] == t["var"] for s in drop)]
            n_skipped = len(targets.get("values", [])) - len(kept["values"]) + \
                len(targets.get("row_counts", [])) - len(kept["row_counts"])
            tpath = os.path.join(work, f"{case}-targets.json")
            json.dump(kept, open(tpath, "w"))
            out = os.path.join(work, f"{case}.xlsx")
            r = subprocess.run([py, os.path.join(RENDER_DIR, "fml2xlsx.py"), root,
                                os.path.join(root, "excel", "sample-data.json"), out], capture_output=True, text=True)
            if r.returncode:
                record("eval", False, case, "render failed: " + (r.stderr or r.stdout).strip().splitlines()[-1])
                continue
            untranslated = [l for l in r.stdout.splitlines() if l.startswith("UNTRANSLATED")]
            calc = os.path.join(work, f"calc-{case}")
            os.makedirs(calc, exist_ok=True)
            subprocess.run([py, os.path.join(RENDER_DIR, "calc_formulas.py"), out, calc], capture_output=True, text=True)
            evaluated = glob.glob(os.path.join(calc, "*.XLSX")) + glob.glob(os.path.join(calc, "*.xlsx"))
            if not evaluated:
                record("eval", False, case, "the evaluator wrote no workbook")
                continue
            r = subprocess.run([py, os.path.join(RENDER_DIR, "verify.py"), evaluated[0], tpath], capture_output=True, text=True)
            lines = (r.stdout + r.stderr).strip().splitlines()
            bad = [l for l in lines if l.startswith(("FAIL", "MISSING", "AMBIGUOUS", "ERROR"))]
            note = f" ({n_skipped} assertion(s) skipped: {sk.get('kind')} {sk.get('rule')})" if n_skipped else ""
            record("eval", r.returncode == 0, case + note, "; ".join(bad[:4] + untranslated[:2]) or lines[-1])
            if n_skipped:
                record("eval", None, f"{case}: {n_skipped} skipped assertion(s)")
    finally:
        shutil.rmtree(work, ignore_errors=True)


# ----------------------------------------------------------------------------- examples
def run_examples():
    print("examples")
    for d in sorted(glob.glob(os.path.join(REPO, "examples", "*", ""))):
        root = d.rstrip("/")
        diags = fml_lint.lint(root, "standard")
        errs = [f"{os.path.relpath(x.path, REPO)}:{x.line} {x.code} {x.message}" for x, s in diags if s == "E"]
        record("examples (lint)", not errs, os.path.relpath(root, REPO), "; ".join(errs[:5]))
    for f in sorted(glob.glob(os.path.join(REPO, "examples", "**", "*.fml"), recursive=True)):
        ok, why = round_trip(f)
        record("examples (round trip)", ok, os.path.relpath(f, REPO), why)


def run_dimension_round_trip():
    """§5.5, §5.6 item 1: dimension declarations are information content, and fmt puts them first, sorted by
    name, each with its properties in the canonical order."""
    print("dimensions")
    text = ('"A IN" { Product, Day }\n'
            '  @notes "Writer: form."\n'
            'dimension Region {\n'
            '  North,\n'
            '  South }   # an inline list across lines\n'
            'dimension Day from "dimensions/Day.csv"\n'
            '  @parent YearMonth\n'
            '  @desc "Calendar days"\n'
            '  @semantic time\n'
            'dimension Product\n'
            '  @folder "Sales"\n'
            '  @null\n'
            '  @attribute Color string\n'
            '  @parent Group required many\n'
            '  @parent Category\n'
            '  @rollup none\n')
    s = Sink()
    d1 = parse_document(text, s.at("<dims>"), "<dims>")
    errs = [f"{x.line}:{x.col} {x.code}" for x in s.items if x.code[4] == "E"]
    record("dimensions", not errs and set(canon.info_content(d1)[0]) == {"Day", "Product", "Region"},
           "parse collects every dimension declaration", "; ".join(errs) or str(canon.info_content(d1)[0]))
    out = canon.emit(d1)
    want = ('# --- Dimensions ---\n'
            'dimension Day from "dimensions/Day.csv"\n  @semantic time\n  @parent YearMonth\n  @desc "Calendar days"\n'
            'dimension Product\n  @rollup none\n  @parent Category\n  @parent Group many required\n'
            '  @attribute Color string\n  @null\n  @folder "Sales"\n'
            'dimension Region { North, South }\n\n# --- Variables ---\n')
    record("dimensions", out.startswith(want), "fmt puts declarations first, sorted, properties in canonical order",
           repr(out[:400]))
    d2 = parse_document(out, Sink().at("<canonical>"), "<canonical>")
    record("dimensions", canon.info_content(d2) == canon.info_content(d1) and canon.emit(d2) == out,
           "round trip keeps the declarations [DOC-4]", repr(out[:200]))
    for label, edit in (("dropping a declaration", lambda x: x.replace("dimension Region {\n  North,\n  South }", "")),
                        ("reordering inline members", lambda x: x.replace("North,\n  South", "South,\n  North")),
                        ("dropping @null", lambda x: x.replace("  @null\n", "")),
                        ("dropping many", lambda x: x.replace(" required many", " required"))):
        d3 = parse_document(edit(text), Sink().at("<dims>"), "<dims>")
        record("dimensions", canon.info_content(d3) != canon.info_content(d1),
               f"{label} changes the information content (§5.5)", "")
    for retired in ("link Product -> Category\n", "time Day\n"):
        s = Sink()
        parse_document(retired, s.at("<retired>"), "<retired>")
        record("dimensions", [x.code for x in s.items] == ["FML-E0104"],
               f"the retired statement {retired.split()[0]} is FML-E0104", str([x.code for x in s.items]))


def run_cli():
    print("command line")
    lint = os.path.join(LINT_DIR, "fml_lint.py")
    valid = os.path.join(HERE, "syntax", "valid", "v01-minimal.fml")
    r = subprocess.run([sys.executable, lint, "lint", valid, "--json"], capture_output=True, text=True)
    try:
        ok = r.returncode == 0 and isinstance(json.loads(r.stdout), list)
    except ValueError:
        ok = False
    record("cli", ok, "lint --json on a valid document", r.stderr.strip())
    bad = os.path.join(HERE, "syntax", "invalid", "e0101-unterminated-string.fml")
    r = subprocess.run([sys.executable, lint, "lint", bad], capture_output=True, text=True)
    ok = r.returncode == 1 and re.search(r"^\S+:\d+:\d+ FML-E0101 ", r.stdout, re.M) is not None
    record("cli", ok, "lint prints path:line:col CODE message and exits 1 on an error", r.stdout[:200])
    r = subprocess.run([sys.executable, lint, "fmt", valid], capture_output=True, text=True)
    record("cli", r.returncode == 0 and r.stdout.startswith("# --- Dimensions ---"), "fmt prints the canonical form", r.stderr)
    r = subprocess.run([sys.executable, lint, "fmt", bad], capture_output=True, text=True)
    record("cli", r.returncode == 1, "fmt refuses a document with syntax errors", "")
    for name in ("e0707-duplicate-parent", "e0707-duplicate-parent-modifiers",
                 "e0707-duplicate-parent-reordered-modifiers"):
        duplicate = os.path.join(HERE, "syntax", "invalid", name + ".fml")
        for profile in ("lenient", "standard", "strict"):
            r = subprocess.run([sys.executable, lint, "lint", duplicate, "--profile", profile, "--json"],
                               capture_output=True, text=True)
            diags = json.loads(r.stdout)
            got = [(d["code"], d["line"], d["col"], d["severity"]) for d in diags]
            record("cli", r.returncode == 1 and got == [("FML-E0707", 7, 3, "error")],
                   f"{name} is rejected under {profile} at the second parent", repr(got))
        r = subprocess.run([sys.executable, lint, "fmt", duplicate], capture_output=True, text=True)
        record("cli", r.returncode == 1 and not r.stdout and "FML-E0707" in r.stderr,
               f"fmt refuses {name} without dropping a parent", r.stderr.strip())


def main():
    run_syntax()
    run_models()
    run_eval("--no-eval" in sys.argv)
    run_examples()
    run_dimension_round_trip()
    run_cli()
    print("\nsummary")
    tp = tf = ts = 0
    for sec, (p, f, s) in results.items():
        print(f"  {sec:24s} {p:4d} passed  {f:3d} failed  {s:3d} skipped")
        tp, tf, ts = tp + p, tf + f, ts + s
    print(f"  {'total':24s} {tp:4d} passed  {tf:3d} failed  {ts:3d} skipped")
    if failures:
        print("\nFAILED")
        sys.exit(1)
    print("\nOK")


if __name__ == "__main__":
    main()
