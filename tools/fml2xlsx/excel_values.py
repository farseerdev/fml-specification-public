"""excel_values.py <workbook name open in Excel> <out.xlsx> — reads the values Microsoft
Excel computed (via JXA) and writes them into a values-only workbook for verify.py."""
import json, subprocess, sys, os
from openpyxl import Workbook
here = os.path.dirname(os.path.abspath(__file__))
from openpyxl import load_workbook
src = load_workbook(sys.argv[3])
dims = {ws.title: [ws.max_row, ws.max_column] for ws in src.worksheets}
raw = subprocess.run(["osascript", "-l", "JavaScript", os.path.join(here, "dump.js"), sys.argv[1], json.dumps(dims)],
                     capture_output=True, text=True, check=True).stdout
data = json.loads(raw); wb = Workbook(); wb.remove(wb.active); errors = 0
for name, sh in data.items():
    ws = wb.create_sheet(name)
    vals = sh["values"]
    if vals is None: continue
    if not isinstance(vals, list): vals = [[vals]]
    vals = [row if isinstance(row, list) else [row] for row in vals]
    for r, row in enumerate(vals, 1):
        for c, v in enumerate(row, 1):
            if v == "" or v is None: continue
            if isinstance(v, (int, float)) and v <= -2146826200 and v >= -2146826300: v = "#ERR"; errors += 1
            ws.cell(r, c, v)
wb.save(sys.argv[2]); print(f"read {len(data)} sheets from Excel, {errors} error values")
