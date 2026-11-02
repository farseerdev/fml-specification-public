#!/usr/bin/env python3
"""build_examples.py — renders every example's workbook, evaluates it and checks its targets.

usage:
  python3 build_examples.py            # render + independent evaluator (formulas) + targets
  python3 build_examples.py --excel    # also evaluate in Microsoft Excel (macOS) and write the
                                       # values Excel computed into the shipped workbooks as cached values
"""
import glob, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
PY = sys.executable


def run(*args):
    r = subprocess.run([PY, *args], capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip().splitlines()


def excel_open(path, name):
    """Close any open workbook of the same name without saving, then open the file."""
    script = f'''with timeout of 120 seconds
  tell application "Microsoft Excel"
    if (exists workbook "{name}") then close workbook "{name}" saving no
    open (POSIX file "{path}")
  end tell
end timeout'''
    subprocess.run(["osascript", "-e", script], capture_output=True, text=True)


def excel_close(name):
    script = f'''with timeout of 60 seconds
  tell application "Microsoft Excel"
    if (exists workbook "{name}") then close workbook "{name}" saving no
  end tell
end timeout'''
    subprocess.run(["osascript", "-e", script], capture_output=True, text=True)


def main():
    use_excel = "--excel" in sys.argv
    work = tempfile.mkdtemp(prefix="fml2xlsx-")
    if use_excel:                                   # Excel's sandbox can open files under the user's home
        work = tempfile.mkdtemp(prefix="fml2xlsx-", dir=os.path.expanduser("~"))
    failures = 0
    for model in sorted(glob.glob(os.path.join(REPO, "examples", "*", "excel", "sample-data.json"))):
        ex = os.path.dirname(os.path.dirname(model)); name = os.path.basename(ex)
        targets = os.path.join(ex, "excel", "targets.json")
        out = os.path.join(work, f"{name}.xlsx")
        code, log = run(os.path.join(HERE, "fml2xlsx.py"), ex, model, out)
        if code: print(name, "RENDER FAILED", *log, sep="\n  "); failures += 1; continue
        calc = os.path.join(work, "calc"); os.makedirs(calc, exist_ok=True)
        run(os.path.join(HERE, "calc_formulas.py"), out, calc)
        evaluated = os.path.join(calc, f"{name}.xlsx".upper())
        code, log = run(os.path.join(HERE, "verify.py"), evaluated, targets)
        print(f"{name:20s} independent evaluator: {log[-1]}"); failures += code
        if use_excel:
            excel_open(out, f"{name}.xlsx")
            vals = os.path.join(work, f"{name}-excel-values.xlsx")
            run(os.path.join(HERE, "excel_values.py"), f"{name}.xlsx", vals, out)
            code, log = run(os.path.join(HERE, "verify.py"), vals, targets)
            print(f"{name:20s} Microsoft Excel:       {log[-1]}"); failures += code
            excel_close(f"{name}.xlsx")
            if code == 0:
                shipped = os.path.join(ex, "excel", f"{name}.xlsx")
                run(os.path.join(HERE, "inject_cache.py"), out, vals, shipped)
                code, log = run(os.path.join(HERE, "verify.py"), shipped, targets)
                print(f"{name:20s} shipped (cached):      {log[-1]}"); failures += code
    shutil.rmtree(work, ignore_errors=True)
    print("\nOK" if failures == 0 else f"\n{failures} FAILED")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
