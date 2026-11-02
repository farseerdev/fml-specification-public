"""inject_cache.py <formulas.xlsx> <excel-values.xlsx> <out.xlsx> — writes the values Excel
computed into each formula cell as its cached value (<v>), keeping the formulas
(spec/fml-excel-1.0.md §14.1 item 2)."""
import re, sys, zipfile, datetime
from openpyxl import load_workbook
src, valpath, out = sys.argv[1:4]
vals = load_workbook(valpath)
wbf = load_workbook(src)
sheetfile = {}                               # sheet name -> xml path, via workbook.xml + rels
z = zipfile.ZipFile(src)
wbxml = z.read("xl/workbook.xml").decode(); rels = z.read("xl/_rels/workbook.xml.rels").decode()
rid = dict(re.findall(r'<Relationship[^>]*Id="(rId\d+)"[^>]*Target="([^"]+)"', rels)) | {a: b for b, a in re.findall(r'<Relationship[^>]*Target="([^"]+)"[^>]*Id="(rId\d+)"', rels)}
for name, r in re.findall(r'<sheet[^>]*name="([^"]+)"[^>]*r:id="(rId\d+)"', wbxml):
    t = rid[r]; sheetfile[name.replace("&amp;", "&")] = "xl/" + t.lstrip("/").replace("xl/", "")
def esc(s): return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
EPOCH = datetime.datetime(1899, 12, 30)
done = 0
zout = zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED)
for item in z.infolist():
    data = z.read(item.filename)
    name = next((n for n, f in sheetfile.items() if f == item.filename), None)
    if name and name in vals.sheetnames:
        ws = vals[name]; xml = data.decode()
        def fill(m):
            global done
            ref, attrs, f = m.group(1), m.group(2), m.group(3)
            v = ws[ref].value
            attrs = re.sub(r'\s+t="[^"]*"', "", attrs)
            if v is None or v == "":
                return f'<c r="{ref}"{attrs} t="str"><f>{f}</f><v></v></c>'
            if isinstance(v, datetime.datetime): v = (v - EPOCH).total_seconds() / 86400
            done += 1
            if isinstance(v, (int, float)): return f'<c r="{ref}"{attrs}><f>{f}</f><v>{repr(float(v))}</v></c>'
            if isinstance(v, str) and re.match(r"\d{4}-\d\d-\d\dT", v):
                d = datetime.datetime.fromisoformat(v.replace("Z", "+00:00")).replace(tzinfo=None)
                return f'<c r="{ref}"{attrs}><f>{f}</f><v>{round((d - EPOCH).total_seconds() / 86400)}</v></c>'
            if isinstance(v, bool): return f'<c r="{ref}"{attrs} t="b"><f>{f}</f><v>{int(v)}</v></c>'
            return f'<c r="{ref}"{attrs} t="str"><f>{f}</f><v>{esc(str(v))}</v></c>'
        xml = re.sub(r'<c r="([A-Z]+\d+)"([^>]*)><f>(.*?)</f>(?:<v>.*?</v>|<v\s*/>)?</c>', fill, xml)
        data = xml.encode()
    zout.writestr(item, data)
zout.close(); print(f"cached {done} formula values into {out}")
