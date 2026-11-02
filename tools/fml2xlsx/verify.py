#!/usr/bin/env python3
"""verify.py <calculated.xlsx> <targets.json> — reads a translated workbook by
variable name, keys and period (spec/fml-excel-1.0.md §4.4) and checks targets."""
import json, re, sys
from openpyxl import load_workbook

def read(path):
    wb = load_workbook(path, data_only=True)
    errors, table = [], {}
    for ws in wb.worksheets:
        if ws.title.upper() in ("NOTES", "DIMENSIONS", "SOURCE"):
            for row in ws.iter_rows():
                for c in row:
                    if isinstance(c.value, str) and c.value.startswith("#") and c.value[1:2].isupper(): errors.append((ws.title, c.coordinate, c.value))
            continue
        hdr2 = [c.value for c in ws[2]]; hdr3 = [c.value for c in ws[3]]
        pcols = [i for i, v in enumerate(hdr2) if isinstance(v, str) and re.match(r"\d{4}$", v) and isinstance(hdr3[i], str) and re.match(r"\d{2}$", hdr3[i])]
        ycols = [i for i, v in enumerate(hdr2) if isinstance(v, str) and re.match(r"\d{4}( \(partial\))?$", v) and hdr3[i] == "Total"]
        kcols = {hdr2[i]: i for i in range(1, pcols[0])} if pcols else {}
        allrows = list(ws.iter_rows(min_row=7, values_only=True))
        for ri, row in enumerate(allrows):
            name = row[0]
            if not name: continue
            nxt = allrows[ri + 1][0] if ri + 1 < len(allrows) else None
            prev = allrows[ri - 1][0] if ri > 0 else None
            if prev != name and all(row[i] is None for i in range(1, len(row))): continue   # label row
            for i, v in enumerate(row):
                if isinstance(v, str) and v.startswith("#") and v[1:2].isupper(): errors.append((ws.title, name, v))
            keys = tuple(sorted((k, str(row[i])) for k, i in kcols.items() if row[i] is not None))
            if all(row[i] is None for i in kcols.values()) and keys == () and not any(row[i] not in (None, "") for i in pcols):
                pass
            vals = {f"{hdr2[i]}-{hdr3[i]}": row[i] for i in pcols}     # a YearMonth member, "2027-03"
            vals.update({f"{hdr2[i].split()[0]} Total": row[i] for i in ycols})
            table.setdefault(name, []).append((dict(keys), vals))
    return table, errors

def num(v):
    return None if v in (None, "") else float(v)

def main(path, tpath):
    table, errors = read(path)
    T = json.load(open(tpath)); fails = 0; checked = 0
    for e in errors[:20]: print("ERROR CELL", e)
    fails += len(errors)
    for t in T["values"]:
        rows = table.get(t["var"], [])
        sel = [vals for keys, vals in rows if all(keys.get(k) == str(v) for k, v in t.get("keys", {}).items())]
        if not sel: print("MISSING ROW", t); fails += 1; continue
        if t.get("sum_rows"): got = sum(num(v.get(t["period"])) or 0 for v in sel)
        else:
            if len(sel) > 1 and not t.get("keys") and len(rows) > 1: print("AMBIGUOUS", t); fails += 1; continue
            got = num(sel[0].get(t["period"]))
        exp = t["expect"]; checked += 1
        ok = (got is None and exp is None) or (got is not None and exp is not None and abs(got - exp) <= t.get("tol", 0.005))
        if not ok: fails += 1
        print(("ok  " if ok else "FAIL"), t["var"], t.get("keys", ""), t["period"], "expected", exp, "got", got)
    for c in T.get("all", []):
        rows = table.get(c["var"], [])
        for keys, vals in rows:
            for p, v in vals.items():
                if c.get("periods") and p not in c["periods"]: continue
                if "Total" in p: continue
                checked += 1; v = num(v)
                if c["rule"] == "zero" and (v is None or abs(v) > 0.005): print("FAIL zero", c["var"], keys, p, v); fails += 1
                if c["rule"] == "empty" and v is not None: print("FAIL empty", c["var"], keys, p, v); fails += 1
                if c["rule"] == "populated" and v is None: print("FAIL populated", c["var"], keys, p, v); fails += 1
    for c in T.get("row_counts", []):
        n = len(table.get(c["var"], [])); checked += 1
        ok = n == c["rows"]; fails += 0 if ok else 1
        print(("ok  " if ok else "FAIL"), "rows", c["var"], "expected", c["rows"], "got", n)
    print(f"\n{checked} checks, {fails} failures, {len(errors)} error cells")
    return fails

if __name__ == "__main__":
    sys.exit(1 if main(*sys.argv[1:3]) else 0)
