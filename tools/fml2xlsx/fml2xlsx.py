#!/usr/bin/env python3
"""fml2xlsx — renders an FML model as a workbook, following
spec/fml-excel-1.0.md (draft). Generic: knows nothing about any one model.

usage: fml2xlsx.py <model-dir> <sample-data.json> <out.xlsx>
"""
import csv, datetime, glob, json, math, os, re, sys
from collections import OrderedDict, defaultdict
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter as COL
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.datavalidation import DataValidation

SYSTEM = {"YearMonth", "Months", "Quarters", "Half years", "Year to date", "Years", "Versions"}
TIME = {"Versions", "YearMonth", "Years", "Months"}
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fmlparse import parse_document                              # noqa: E402
INPUT_FILL = PatternFill("solid", fgColor="FFF2CC")
LABEL_FONT = Font(bold=True)
NUMRX = re.compile(r"-?\d+(\.\d+)?$")


def put_text(ws, r, c, v):
    """Writes a value from the model (a name, a member, a note, a source line) as text: one that begins
    with =, +, - or @ would otherwise become a live formula (FML §2.6)."""
    cell = ws.cell(r, c, v)
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@"):
        cell.data_type = "s"
        cell.quotePrefix = True
    return cell


# ----------------------------------------------------------------------------- model

class Var:
    def __init__(self, d, order, file):
        self.name = d["name"]
        self.grain = [g["dimension"] for g in d["grain"]]
        self.pins = {g["dimension"]: g["pinnedMember"] for g in d["grain"] if "pinnedMember" in g}
        self.formula = d.get("formula")
        self.props = {p["key"]: p["value"]["value"] for p in d["properties"]}
        self.order, self.file = order, file
        self.keys = [g for g in self.grain if g not in TIME]          # key dims, pins included
        self.free = [g for g in self.keys if g not in self.pins]
        # One time dimension per grain (FML [VAR-9]): YearMonth carries both the year and the month of a column.
        self.has_months = "Months" in self.grain or "YearMonth" in self.grain
        self.has_years = "Years" in self.grain or "YearMonth" in self.grain
        self.is_measure = len(self.grain) == 0
        folder = self.props.get("folder")
        self.block = folder.split("/")[0].strip() if folder else os.path.splitext(os.path.basename(file))[0]
        self.ast = parse_formula(self.formula) if self.formula else None
        self.rollup = {"last": "closing_state", "first": "beginning_state", "avg": "average"}.get(
            self.props.get("rollup", "sum"), self.props.get("rollup", "sum"))
        self.rows = []          # list of dicts dim -> member (pins included)


class Dim:
    def __init__(self, decl):
        self.name, self.members, self.desc, self.fk = decl["name"], [], {}, OrderedDict()   # fk[parent][member] -> [parents]
        self.attrs = OrderedDict()                                  # attrs[name][member] -> text
        self.null = decl["null"]


def read_member_file(d, decl, path):
    """A member file (FML 1.0 §6.4, [DIM-3]): RFC 4180 CSV in UTF-8, cells not trimmed. The header names the
    dimension, then @description, then one column per @parent and @attribute of the declaration."""
    with open(path, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.reader(fh))
    header = rows[0]
    parents = [p["dimension"] for p in decl["parents"]]
    cols = sorted(header[1:], key=lambda h: (h != "@description", h not in parents))
    for h in cols:
        if h in parents: d.fk[h] = {}
        elif h != "@description": d.attrs[h] = {}
    for r in rows[1:]:
        r = r + [""] * (len(header) - len(r))
        m = r[0]; d.members.append(m)
        for h, cell in zip(header[1:], r[1:]):
            if h == "@description": d.desc[m] = cell
            elif h in d.fk: d.fk[h][m] = [p for p in cell.split("|") if p]
            else: d.attrs[h][m] = cell


def load_model(model_dir):
    """A model is every .fml document under the model directory (FML 1.0 §5.2) with the member files its
    dimension declarations name (§6.4)."""
    files = sorted(glob.glob(os.path.join(model_dir, "**", "*.fml"), recursive=True))
    asts = {f: parse_document(open(f, encoding="utf8").read()) for f in files}
    decls, variables, order = {}, OrderedDict(), 0
    for f in files:
        doc = asts[f]
        for d in doc["dimensions"]: decls[d["name"]] = d
        for v in doc["variables"]:
            variables[v["name"]] = Var(v, order, f); order += 1
    dims, edges = OrderedDict(), []
    for name in sorted(decls):
        decl = decls[name]; d = Dim(decl); dims[name] = d
        if decl["source"] == "file": read_member_file(d, decl, os.path.join(model_dir, decl["file"]))
        elif decl["source"] == "inline": d.members = list(decl["members"])
        for p in decl["parents"]:
            d.fk.setdefault(p["dimension"], {}); edges.append((name, p["dimension"]))
            for m in d.members: d.fk[p["dimension"]].setdefault(m, [])
        if d.null: d.members.append(f"NULL ({name})")                  # only @null gives a NULL member [DIM-5]
    for d in dims.values():
        for parent, fk in d.fk.items():
            pnull = parent != d.name and parent in dims and dims[parent].null
            for m, ps in fk.items():
                # FML 1.0 [EVAL-15], [PARENT-3]: an empty foreign key reaches the parent's NULL member (a tree
                # excepted: there an empty parent makes a root)
                if not ps and pnull: fk[m] = [f"NULL ({parent})"]
            if d.null:
                # §6.5: the NULL member's parents are the NULL members of the parents that declare @null; none in a tree
                fk[f"NULL ({d.name})"] = [f"NULL ({parent})"] if pnull else []
    times = {n for n, decl in decls.items() if decl["time"]}
    return variables, dims, edges, files, times - SYSTEM


def not_translated(V, times):
    """[X-NT-1]: a variable whose grain holds a declared time dimension (FML 1.0 §6.9) is not
    translated — the workbook's period columns are YearMonth — and neither is any variable that
    references one, directly or through others. Returns {name: (code, detail)}."""
    out = {}
    for n, v in V.items():
        held = [d for d in v.grain if d in times]
        if held:
            out[n] = ("CUSTOM-TIME", f"its time dimension {held[0]} is declared @semantic time; "
                      "the workbook's period columns are YearMonth")
    for n in topo(V):                                               # operands before their dependents
        bad = sorted(r for r in refs_in(V[n].ast) if r in out)
        if bad and n not in out:
            out[n] = ("DEPENDS-ON-UNTRANSLATED", f"references {bad[0]}, which is not translated")
    return out


# ----------------------------------------------------------------------------- formula parser

def tokenize(s):
    toks, i = [], 0
    while i < len(s):
        c = s[i]
        if c.isspace(): i += 1; continue
        if c == '"':
            j = i + 1; buf = ""
            while s[j] != '"':
                if s[j] == "\\": buf += s[j + 1]; j += 2; continue
                buf += s[j]; j += 1
            toks.append(("name", buf)); i = j + 1; continue
        if c.isdigit() or (c == "-" and i + 1 < len(s) and s[i + 1].isdigit() and (not toks or toks[-1][0] in ("op", "(", ","))):
            m = re.match(r"-?\d+(\.\d+)?", s[i:]); toks.append(("num", float(m.group(0)))); i += len(m.group(0)); continue
        if c.isalpha() or c == "_":
            m = re.match(r"[A-Za-z_]\w*", s[i:]); toks.append(("id", m.group(0))); i += len(m.group(0)); continue
        if c in "+-*/": toks.append(("op", c)); i += 1; continue
        if c in "(),>": toks.append((c, c)); i += 1; continue
        raise ValueError(f"bad char {c!r} in {s}")
    return toks


def parse_formula(s):
    toks = tokenize(s); pos = [0]
    def peek(k=0): return toks[pos[0] + k] if pos[0] + k < len(toks) else (None, None)
    def nxt(): t = toks[pos[0]]; pos[0] += 1; return t
    def expr():
        l = term()
        while peek()[0] == "op" and peek()[1] in "+-": op = nxt()[1]; l = ("bin", op, l, term())
        return l
    def term():
        l = factor()
        while peek()[0] == "op" and peek()[1] in "*/": op = nxt()[1]; l = ("bin", op, l, factor())
        return l
    def factor():
        t = nxt()
        if t[0] == "num": return ("num", t[1])
        if t[0] == "op" and t[1] == "-": return ("bin", "-", ("num", 0.0), factor())
        if t[0] == "(":
            e = expr(); assert nxt()[0] == ")"; return e
        if t[0] in ("name", "id"):
            if t[0] == "id" and peek()[0] == "(":
                nxt(); args = []
                if peek()[0] != ")":
                    args.append(arg())
                    while peek()[0] == ",": nxt(); args.append(arg())
                assert nxt()[0] == ")"; return ("call", t[1], args)
            if peek()[0] == ">":
                nxt(); m = nxt(); return ("mref", t[1], m[1] if m[0] != "num" else fmt(m[1]))
            return ("ref", t[1])
        raise ValueError(f"unexpected {t} in {s}")
    def arg(): return expr()
    e = expr(); assert pos[0] == len(toks), s; return e


def fmt(v):
    if isinstance(v, str): return v
    return str(int(v)) if float(v).is_integer() else repr(float(v))


def refs_in(node, acc=None):
    acc = set() if acc is None else acc
    if node is None: return acc
    if node[0] == "ref": acc.add(node[1])
    elif node[0] == "bin": refs_in(node[2], acc); refs_in(node[3], acc)
    elif node[0] == "call":
        for a in node[2]: refs_in(a, acc)
    return acc


# ----------------------------------------------------------------------------- dimension graph

class Graph:
    def __init__(self, edges, dims):
        self.parents = defaultdict(list)
        for c, p in edges:
            if c != p: self.parents[c].append(p)
        self.trees = {c for c, p in edges if c == p}
        self.dims = dims

    def chain(self, a, b):
        """Shortest parent chain a -> ... -> b (list of dims incl. both), or None."""
        if a == b: return [a]
        frontier, seen = [[a]], {a}
        while frontier:
            nf = []
            for path in frontier:
                for p in self.parents[path[-1]]:
                    if p in seen: continue
                    if p == b: return path + [p]
                    seen.add(p); nf.append(path + [p])
            frontier = nf
        return None

    def up(self, a, member, b):
        """Members of b that `member` of a reaches."""
        path = self.chain(a, b); cur = [member]
        for x, y in zip(path, path[1:]):
            nxt = []
            for m in cur: nxt += self.dims[x].fk.get(y, {}).get(m, []) if x in self.dims else []
            cur = nxt
        return cur

    def reach_target(self, d, targets):
        """First target dim reachable from d (aggregation), with its chain."""
        best = None
        for t in targets:
            c = self.chain(d, t)
            if c and len(c) > 1 and (best is None or len(c) < len(best[1])): best = (t, c)
        return best


# ----------------------------------------------------------------------------- data

def ym(p):
    """A YearMonth member "2027-03" (FML §6.7) as (year, month)."""
    return int(p[:4]), int(p[5:])


def period_list(data):
    return [(p, *ym(p)) for p in data["periods"]]


def to_serial(s):
    if isinstance(s, (int, float)): return s
    d = datetime.date.fromisoformat(s)
    return (d - datetime.date(1899, 12, 30)).days


def input_rows_and_values(var, data, periods):
    entries = data["inputs"].get(var.name, [])
    rows, vals = [], []
    for e in entries:
        keys = dict(e["keys"]); keys.update(var.pins)
        row_vals = []
        for i, (p, y, m) in enumerate(periods):
            v = None
            if "values" in e: v = e["values"].get(p)
            elif "from" in e:
                fy, fm = ym(e["from"])
                if (y, m) >= (fy, fm): v = e["value"]
            elif "years" in e: v = e["years"].get(f"{y}")
            elif "value" in e: v = e["value"]
            if v is not None and var.props.get("type") == "date": v = to_serial(v)
            row_vals.append(v)
        rows.append(keys); vals.append(row_vals)
    return rows, vals


# ----------------------------------------------------------------------------- domains (anchoring)

def domain(node, T, V, G):
    """Patterns (dict over T.free; missing key = wildcard) of the cells the node anchors. None = no coordinates."""
    k = node[0]
    if k in ("num", "mref"): return None
    if k == "ref":
        src = V[node[1]]; pats = []
        for r in src.rows:
            choices = [{}]
            for t in T.free:
                if t in r: opts = [r[t]]
                else:
                    agg = next(((c, G.chain(c, t)) for c in src.keys if c not in T.free and G.chain(c, t) and len(G.chain(c, t)) > 1), None)
                    opts = G.up(agg[0], r[agg[0]], t) if agg else None
                if opts is None: continue                     # broadcast or lookup: wildcard
                choices = [dict(c, **{t: o}) for c in choices for o in opts]
            pats += choices
        uniq = []
        for p in pats:
            if p not in uniq: uniq.append(p)
        return uniq
    if k == "bin":
        a, b = domain(node[2], T, V, G), domain(node[3], T, V, G)
        if node[1] in "+-": return union(a, b)
        a = None if has_literal_term(node[2]) else a
        b = None if has_literal_term(node[3]) else b
        return intersect(a, b)
    if k == "call":
        f, args = node[1], node[2]
        if f == "if":
            d = union(domain(args[1], T, V, G), domain(args[2], T, V, G) if len(args) > 2 else None)
            cond_vars = refs_in(args[0])
            if d is None and len(cond_vars) == 1:
                # EVAL-5: literal output, exactly one variable in the condition -> its cells
                return domain(("ref", next(iter(cond_vars))), T, V, G)
            return d
        if f in ("hasDMember", "hasTags", "currentDate", "currentMonth", "currentYear", "daysInCurrentMonth"): return None
        if f == "sum": return domain(args[0], T, V, G)
        if f == "cumsum":
            d = domain(args[0], T, V, G)
            return union(d, domain(args[2], T, V, G)) if len(args) > 2 else d
        if f in ("delay", "spread", "spread_days", "avg", "round"): return domain(args[0], T, V, G)
        out = None
        for a in args: out = union(out, domain(a, T, V, G))
        return out
    raise ValueError(node)


def carried(v):
    """The dimensions a reference to v carries [EVAL-4a]: its grain and pins; YearMonth also carries Years and Months
    (the calendar exception: each month belongs to exactly one year and one month of the year)."""
    dims = set(v.grain) | set(v.pins)
    return dims | {"Years", "Months"} if "YearMonth" in dims else dims


def full_grain_refs(n, T, V):
    """FML 1.0 [EVAL-4a]: value-position references whose grain carries every dimension of T's grain."""
    need = set(T.grain)
    return {r for r in value_refs(n) if r in V and need <= carried(V[r])}


def has_literal_term(n):
    """A +/- chain with a literal term is never null, so as a factor it does not restrict cells."""
    if n[0] == "num": return False
    if n[0] == "bin" and n[1] in "+-":
        terms = []
        def walk(x):
            if x[0] == "bin" and x[1] in "+-": walk(x[2]); walk(x[3])
            else: terms.append(x)
        walk(n)
        return any(t[0] == "num" for t in terms)
    return False


def value_refs(n, acc=None):
    """Variable references in value position (spec §11.3): not inside conditions."""
    acc = set() if acc is None else acc
    if n[0] == "ref": acc.add(n[1])
    elif n[0] == "bin": value_refs(n[2], acc); value_refs(n[3], acc)
    elif n[0] == "call":
        f, a = n[1], n[2]
        if f == "if":
            for x in a[1:]: value_refs(x, acc)
        elif f in ("hasValue", "hasDMember", "hasTags"): pass
        elif f == "cumsum":
            for x in a: value_refs(x, acc)
        else:
            for x in a: value_refs(x, acc)
    return acc


def union(a, b):
    if a is None: return b
    if b is None: return a
    out = list(a)
    for p in b:
        if p not in out: out.append(p)
    return out


def intersect(a, b):
    if a is None: return b
    if b is None: return a
    out = []
    for p in a:
        for q in b:
            if all(p[x] == q[x] for x in p if x in q):
                m = dict(p, **q)
                if m not in out: out.append(m)
    return out


def plan_rows(T, V, G):
    pats = domain(T.ast, T, V, G)
    fg = full_grain_refs(T.ast, T, V)
    if fg:                                  # [EVAL-4a] rule 1: only full-grain references place cells
        cand = None
        for r in sorted(fg): cand = union(cand, domain(("ref", r), T, V, G))
        pats = intersect(cand or [], pats) if pats is not None else cand
    rows = []
    for p in (pats or []):
        if all(t in p for t in T.free):
            r = {t: p[t] for t in T.free}; r.update(T.pins)
            if r not in rows: rows.append(r)
    if T.is_measure and pats: rows = [{}]
    def sortkey(r):
        out = []
        for d in T.keys:
            ms = G.dims[d].members if d in G.dims else []
            out.append(ms.index(r[d]) if r.get(d) in ms else 999)
        return out
    return sorted(rows, key=sortkey)


# ----------------------------------------------------------------------------- layout

class Layout:
    def __init__(self, V, periods, G):
        self.V, self.periods, self.G = V, periods, G
        self.years = sorted({y for _, y, _ in periods})
        self.sheets = OrderedDict()                       # block -> dict
        for v in sorted(V.values(), key=lambda v: v.order):
            sh = self.sheets.setdefault(v.block, {"vars": [], "keys": []})
            sh["vars"].append(v.name)
            for d in v.keys:
                if d not in sh["keys"]: sh["keys"].append(d)
        self.FIRST = 7                                     # first variable label row
        self.pos = {}                                      # var -> (sheet, first data row)
        for name, sh in self.sheets.items():
            r = self.FIRST
            for vn in sh["vars"]:
                v = V[vn]; r += 1                          # label row
                self.pos[vn] = (name, r); r += max(len(v.rows), 0)
                if not v.rows: r += 0
            sh["last"] = r
            nk = len(sh["keys"])
            sh["c_key"] = {d: 2 + i for i, d in enumerate(sh["keys"])}
            sh["c_p0"] = 2 + nk
            sh["c_y0"] = sh["c_p0"] + len(periods) + 1
            sh["c_h0"] = sh["c_y0"] + len(self.years) + 1
            sh["helpers"] = []                             # (var, spec) in column order

    def sheet_of(self, vn): return self.pos[vn][0]
    def q(self, sheet): return "'" + sheet.replace("'", "''") + "'"
    def row_index(self, vn, row):
        v = self.V[vn]
        for i, r in enumerate(v.rows):
            if all(r.get(d) == row.get(d) for d in v.keys): return self.pos[vn][1] + i
        return None
    def cell(self, vn, rownum, ci, here_sheet):
        s = self.sheet_of(vn); a = f"{COL(self.sheets[s]['c_p0'] + ci)}{rownum}"
        return a if s == here_sheet else f"{self.q(s)}!{a}"
    def vrange(self, vn, colnum, here_sheet):
        s = self.sheet_of(vn); r0 = self.pos[vn][1]; r1 = r0 + len(self.V[vn].rows) - 1
        c = COL(colnum); a = f"${c}${r0}:${c}${r1}"
        return a if s == here_sheet else f"{self.q(s)}!{a}"
    def val_range(self, vn, ci, here): return self.vrange(vn, self.sheets[self.sheet_of(vn)]["c_p0"] + ci, here)
    def key_range(self, vn, d, here): return self.vrange(vn, self.sheets[self.sheet_of(vn)]["c_key"][d], here)
    def helper(self, vn, spec):
        sh = self.sheets[self.sheet_of(vn)]
        if (vn, spec) not in sh["helpers"]: sh["helpers"].append((vn, spec))
        return sh["c_h0"] + sh["helpers"].index((vn, spec))
    def helper_range(self, vn, spec, here): return self.vrange(vn, self.helper(vn, spec), here)
    def helper_cell(self, vn, spec, rownum, here):
        s = self.sheet_of(vn); a = f"${COL(self.helper(vn, spec))}{rownum}"
        return a if s == here else f"{self.q(s)}!{a}"


# ----------------------------------------------------------------------------- translation

def xs(s): return '"' + s.replace('"', '""') + '"'
NULL = '""'


class Ex:
    """A translated sub-expression: text, whether it may be null, whether it is a bare cell reference."""
    def __init__(self, t, mn=True, raw=False): self.t, self.mn, self.raw = t, mn, raw


def val(e):
    return f'IF(ISNUMBER({e.t}),{e.t},"")' if e.raw else e.t


class Translator:
    def __init__(self, T, row, rownum, ci, L, V, G, version, notes):
        self.T, self.row, self.rownum, self.ci, self.L, self.V, self.G = T, row, rownum, ci, L, V, G
        self.version, self.notes = version, notes
        self.here = L.sheet_of(T.name)

    def fail(self, why): raise NotImplementedError(why)

    # -- references ----------------------------------------------------------------
    def criteria(self, vn, filters=()):
        """SUMIFS criteria pairs for operand vn read in T at self.row, plus filters."""
        T, V, G, L = self.T, self.V, self.G, self.L
        src = V[vn]; crit = OrderedDict(); exact = True
        for d in src.keys:
            if d in T.free:
                crit[("key", d)] = (L.key_range(vn, d, self.here), xs(self.row[d]))
            elif d in T.pins:
                exact = False                                           # the pin writes, it does not read
            else:
                agg = G.reach_target(d, T.free)
                if agg:
                    t, chain = agg
                    crit[("agg", d, t)] = (L.helper_range(vn, ("chain", tuple(chain)), self.here), xs(self.row[t]))
                    exact = False
                    continue
                lk = next(((t, G.chain(t, d)) for t in T.free if G.chain(t, d) and len(G.chain(t, d)) > 1), None)
                if lk:
                    t, chain = lk
                    hc = L.helper_cell(T.name, ("chain", tuple(chain)), self.rownum, self.here)
                    crit[("lookup", d)] = (L.key_range(vn, d, self.here), hc)
                    exact = False
                else:
                    exact = False                                       # aggregated over d
        for (fd, fm) in filters:
            exact = False
            if fd in T.free:                                            # own grain: broadcast
                for k in list(crit):
                    if (k[0] == "key" and k[1] == fd) or (k[0] == "agg" and k[2] == fd): del crit[k]
                if fd in src.keys: crit[("f", fd)] = (L.key_range(vn, fd, self.here), xs(fm))
                else:
                    c = next(d for d in src.keys if G.chain(d, fd))
                    crit[("f", fd)] = (L.helper_range(vn, ("chain", tuple(G.chain(c, fd))), self.here), xs(fm))
                continue
            if fd in src.keys:
                crit[("f", fd)] = (L.key_range(vn, fd, self.here), xs(fm)); continue
            # reached through a parent of one of the operand's dims; subtree for a tree
            base = fd; via = None
            for d in src.keys:
                ch = G.chain(d, fd)
                if ch and len(ch) > 1: via = ch; break
            if via is None: self.fail(f"filter {fd} not reachable from {vn}")
            if fd in G.trees:
                crit[("f", fd)] = (L.helper_range(vn, ("path", tuple(via)), self.here), xs(f"*|{fm}|*"))
            else:
                crit[("f", fd)] = (L.helper_range(vn, ("chain", tuple(via)), self.here), xs(fm))
        return crit, exact

    def aggregate(self, vn, filters=(), ci=None):
        ci = self.ci if ci is None else ci
        src = self.V[vn]
        if not src.rows: return Ex(NULL)
        crit, exact = self.criteria(vn, filters)
        L = self.L
        if exact:                                                       # aligned / broadcast: direct reference
            rn = L.row_index(vn, self.row)
            if rn is None: return Ex(NULL)
            return Ex(L.cell(vn, rn, ci, self.here), True, True)
        rng = L.val_range(vn, ci, self.here)
        pairs = ",".join(f"{a},{b}" for a, b in crit.values())
        fn = "AVERAGEIFS" if src.rollup == "average" else "SUMIFS"
        if not crit:
            body = f"AVERAGE({rng})" if fn == "AVERAGEIFS" else f"SUM({rng})"
            return Ex(f'IF(COUNT({rng})=0,"",{body})')
        count = f'COUNTIFS({pairs},{rng},">-9.99E+307")'
        return Ex(f'IF({count}=0,"",{fn}({rng},{pairs}))')

    def ref(self, vn, ci=None):
        if vn not in self.V: self.fail(f"unknown variable {vn}")
        return self.aggregate(vn, (), ci)

    # -- expressions -----------------------------------------------------------------
    def tr(self, n, ci=None):
        ci = self.ci if ci is None else ci
        k = n[0]
        if k == "num": return Ex(fmt(n[1]), False)
        if k == "ref": return self.ref(n[1], ci)
        if k == "bin" and n[1] in "+-":
            terms = []
            def walk(x, sign):
                if x[0] == "bin" and x[1] in "+-":
                    walk(x[2], sign); walk(x[3], sign if x[1] == "+" else -sign)
                else: terms.append((sign, x))
            walk(n, 1)
            ts = [(sg, self.tr(x, ci)) for sg, x in terms]
            ts = [(sg, e) for sg, e in ts if e.t != NULL]                 # a null term adds nothing
            if not ts: return Ex(NULL)
            mn = [e.t for _, e in ts if e.mn]
            if len(mn) < len(ts): mn_guard = []                          # a literal term is never null
            else: mn_guard = mn
            body = ""
            for i, (sg, e) in enumerate(ts):
                part = f"N({e.t})" if e.mn else f"({e.t})"
                body += ("" if i == 0 and sg > 0 else ("+" if sg > 0 else "-")) + part
            return Ex(f'IF(COUNT({",".join(mn_guard)})=0,"",{body})' if mn_guard else f"({body})", bool(mn_guard))
        if k == "bin" and n[1] == "/":
            num, den = self.tr(n[2], ci), self.tr(n[3], ci)
            if den.t == NULL: return Ex(NULL)
            numt = "0" if num.t == NULL else (f"N({num.t})" if num.mn else f"({num.t})")
            dent = den.t if not den.t.startswith("IF(") else f"({den.t})"
            if not den.mn: return Ex(f'IF({dent}=0,"",{numt}/{dent})')
            return Ex(f'IF(OR(COUNT({den.t})=0,N({den.t})=0),"",{numt}/{dent})')
        if k == "bin":
            factors = []
            def walkm(x, inv):
                if x[0] == "bin" and x[1] == "*":
                    walkm(x[2], inv); walkm(x[3], inv)
                else: factors.append((inv, x))
            walkm(n, False)
            fs = [(inv, self.tr(x, ci)) for inv, x in factors]
            if any(e.t == NULL for _, e in fs): return Ex(NULL)          # a null factor nulls the product
            mn = [e.t for _, e in fs if e.mn]
            body = ""
            for i, (inv, e) in enumerate(fs):
                body += ("" if i == 0 else ("/" if inv else "*")) + (e.t if not e.t.startswith("IF(") else f"({e.t})")
            divisors = [e.t for inv, e in fs if inv]
            conds = ([f'COUNT({",".join(mn)})<{len(mn)}'] if mn else []) + [f"N({d})=0" for d in divisors]
            if not conds: return Ex(f"({body})", False)
            cond = conds[0] if len(conds) == 1 else f"OR({','.join(conds)})"
            return Ex(f'IF({cond},"",{body})', True)
        if k == "call": return self.call(n, ci)
        self.fail(f"cannot translate {n}")

    def cond(self, n, ci):
        """(excel condition, [operands that may be null])"""
        k = n[0]
        if k == "call":
            f, a = n[1], n[2]
            ops = {"eq": "=", "gt": ">", "gte": ">=", "lt": "<", "lte": "<="}
            if f in ops:
                x, y = self.tr(a[0], ci), self.tr(a[1], ci)
                nx = f"N({x.t})" if x.mn else x.t; ny = f"N({y.t})" if y.mn else y.t
                c = f"{nx}{ops[f]}{ny}"
                if x.mn and y.mn and f in ("eq", "gte", "lte"):   # both operands null -> false (FML 1.0 [EVAL-26])
                    c = f"AND(COUNT({x.t},{y.t})>0,{c})"
                return c, [e.t for e in (x, y) if e.mn]
            if f in ("and", "or"):
                parts = [self.cond(x, ci) for x in a]
                return f"{f.upper()}({','.join(p[0] for p in parts)})", sum((p[1] for p in parts), [])
            if f == "not":
                c, g = self.cond(a[0], ci); return f"NOT({c})", g
            if f == "hasValue":
                x = self.tr(a[0], ci); return f"ISNUMBER({x.t})", []
            if f in ("hasDMember", "hasTags"):
                parts = [self.has_member(x, ci) for x in a]
                return (parts[0] if len(parts) == 1 else f"AND({','.join(parts)})"), []
        x = self.tr(n, ci)
        return f"N({x.t})<>0", []

    def has_member(self, mref, ci):
        assert mref[0] == "mref", mref
        d, m = mref[1], mref[2]
        sh = self.L.sheets[self.here]; c = COL(sh["c_p0"] + ci)
        if d == "Versions": return "TRUE" if self.version == m else "FALSE"
        if d == "Months": return f'{c}$3={xs(m)}'
        if d == "Years": return f'{c}$2={xs(m)}'
        if d == "YearMonth":                           # the intersection of the two header rows (FML §6.7)
            y, mm = ym(m); return f'AND({c}$2={xs(f"{y}")},{c}$3={xs(f"{mm:02d}")})'
        T, G = self.T, self.G
        if d in T.keys:
            return f'${COL(sh["c_key"][d])}{self.rownum}={xs(m)}'
        for t in T.keys:
            ch = G.chain(t, d)
            if ch and len(ch) > 1:
                hc = self.L.helper_cell(T.name, ("chain", tuple(ch)), self.rownum, self.here)
                return f"{hc}={xs(m)}"
        self.fail(f"hasDMember on unreachable dimension {d}")

    def call(self, n, ci):
        f, a = n[1], n[2]
        sh = self.L.sheets[self.here]; col = COL(sh["c_p0"] + ci)
        if f == "if":
            c, _ = self.cond(a[0], ci)              # a null condition reads false (FML 1.0 [EVAL-25])
            A = self.tr(a[1], ci); B = self.tr(a[2], ci) if len(a) > 2 else Ex(NULL)
            return Ex(f"IF({c},{val(A)},{val(B)})")
        if f == "hasValue":                         # 1 or null in value position (FML 1.0 [EVAL-6])
            c, _ = self.cond(n, ci); return Ex(f'IF({c},1,"")')
        if f in ("eq", "gt", "gte", "lt", "lte", "not"):
            c, _ = self.cond(n, ci)                # 1 or 0, never null: cells come from the anchoring guard [EVAL-6], [EVAL-26]
            return Ex(f"--({c})", False)
        if f in ("and", "or"):
            c, _ = self.cond(n, ci)                # null where every operand is null (FML 1.0 [EVAL-26])
            if all(x[0] == "ref" for x in a):
                ops = [self.tr(x, ci).t for x in a]
                return Ex(f'IF(COUNT({",".join(ops)})=0,"",--({c}))', True)
            return Ex(f"--({c})", False)
        if f in ("hasDMember", "hasTags"):
            c, _ = self.cond(n, ci); return Ex(f"--({c})", False)
        if f == "sum":
            if a[0][0] != "ref": self.fail("sum() over an expression")
            filters = []
            for x in a[1:]:
                if x[0] != "mref": self.fail("sum() filter that is not a member reference")
                filters.append((x[1], x[2]))
            return self.aggregate(a[0][1], tuple(filters), ci)
        if f == "delay":
            if a[0][0] != "ref" or a[1][0] != "num": self.fail("delay() form")
            nv = float(a[1][1]); k = int(math.floor(nv + 0.5))   # a half rounds up, towards +inf (FML 1.0 §12.3)
            if ci - k < 0 or ci - k >= len(self.L.periods): return Ex(NULL)
            return self.ref(a[0][1], ci - k)
        if f == "cumsum":
            x = self.tr(a[0], ci)
            fac = self.tr(a[1], ci) if len(a) > 1 else Ex("0", False)
            prev = Ex(self.L.cell(self.T.name, self.rownum, ci - 1, self.here), True, True) if ci > 0 else None
            if x.t == NULL: x = Ex("0", False)
            mn = ([prev.t] if prev else []) + ([x.t] if x.mn else [])
            prevN = f"N({prev.t})" if prev else "0"
            if fac.mn and fac.raw:                  # the factor carries forward (FML 1.0 §12.3)
                first = self.L.cell(a[1][1], self.L.row_index(a[1][1], self.row), 0, self.here) if a[1][0] == "ref" else None
                if first is None: self.fail("cumsum() factor that is not an aligned variable")
                last = fac.t.split("!")[-1]
                fac = Ex(f"IFERROR(LOOKUP(9.99E+307,{first}:{last}),0)", False)
            grow = prevN if (not fac.mn and fac.t == "0") else f"{prevN}*(1+N({fac.t}))"
            inner = f"{grow}+N({x.t})" if x.t != "0" else grow
            body = f'IF(COUNT({",".join(mn)})=0,"",{inner})' if mn else inner
            if len(a) > 2:
                s = self.tr(a[2], ci); body = f"IF(ISNUMBER({s.t}),{s.t},{body})"
            return Ex(body)
        if f == "spread":
            if a[0][0] != "ref" or a[1][0] != "num": self.fail("spread() form")
            nmon = int(a[1][1]); d = int(a[2][1]) if len(a) > 2 else 0
            lo, hi = max(0, ci - d - nmon + 1), ci - d
            if hi < 0: return Ex(NULL)
            cells = [self.ref(a[0][1], j) for j in range(lo, hi + 1)]
            cells = [c.t for c in cells if c.t != NULL]
            if not cells: return Ex(NULL)
            lst = ",".join(cells)
            return Ex(f'IF(COUNT({lst})=0,"",SUM({lst})/{nmon})')
        if f in ("max", "min"):
            x, y = self.tr(a[0], ci), self.tr(a[1], ci)
            mn = [e.t for e in (x, y) if e.mn]
            return Ex(f'IF(COUNT({",".join([x.t, y.t])})=0,"",{f.upper()}({x.t},{y.t}))', True)
        if f in ("round", "abs", "floor", "ceil"):
            x = self.tr(a[0], ci)
            fn = {"round": f"ROUND({x.t},{fmt(a[1][1]) if len(a) > 1 else 0})", "abs": f"ABS({x.t})",
                  "floor": f"INT({x.t})", "ceil": f"-INT(-{x.t})"}[f]
            return Ex(f'IF(COUNT({x.t})=0,"",{fn})' if x.mn else fn, x.mn)
        if f == "power":
            x, y = self.tr(a[0], ci), self.tr(a[1], ci); mn = [e.t for e in (x, y) if e.mn]
            body = f"POWER({x.t},{y.t})"
            return Ex(f'IF(COUNT({",".join(mn)})<{len(mn)},"",{body})' if mn else body, bool(mn))
        if f in ("date", "edate", "year", "month", "day"):
            xs_ = [self.tr(x, ci) for x in a]; mn = [e.t for e in xs_ if e.mn]
            ts = [e.t for e in xs_]
            if f == "date":                         # FML rounds each argument, Excel's DATE truncates (FML 1.0 §12.5)
                whole = lambda x: (x[0] == "num" and float(x[1]).is_integer()) or (
                    x[0] == "call" and x[1] in ("year", "month", "day", "currentYear", "currentMonth"))
                ts = [t if whole(x) else f"ROUND({t},0)" for x, t in zip(a, ts)]
            body = f"{'EDATE' if f == 'edate' else f.upper()}({','.join(ts)})"
            return Ex(f'IF(COUNT({",".join(mn)})<{len(mn)},"",{body})' if mn else body, bool(mn))
        if f == "currentMonth": return Ex(f"{col}$5", False)
        if f == "currentYear": return Ex(f"{col}$4", False)
        if f == "currentDate": return Ex(f"DATE({col}$4,{col}$5,1)", False)
        if f == "daysInCurrentMonth": return Ex(f"DAY(EOMONTH(DATE({col}$4,{col}$5,1),0))", False)
        self.fail(f"function {f}() is not translated")

    def formula(self):
        e = self.tr(self.T.ast)
        body = val(e)
        anchors = full_grain_refs(self.T.ast, self.T, self.V) or value_refs(self.T.ast)   # [X-NULL-5], FML 1.0 [EVAL-4a]
        if not anchors and self.T.ast[0] == "call" and self.T.ast[1] == "if" and len(refs_in(self.T.ast[2][0])) == 1:
            anchors = set()                     # EVAL-5: the condition's own test already decides the cell
        if anchors and not e.mn and not self.T.is_measure:
            # X-NULL-5: no value-position reference has a number here -> no cell
            cells = [self.tr(("ref", r)).t for r in sorted(anchors)]
            cells = [c for c in cells if c != NULL]
            body = f'IF(COUNT({",".join(cells)})=0,"",{body})' if cells else NULL
        return "=" + body


# ----------------------------------------------------------------------------- workbook

def xl(formula):
    return re.sub(r"\bXLOOKUP\(", "_xlfn.XLOOKUP(", formula)


def topo(V):
    order, seen = [], set()
    def visit(n, stack=()):
        if n in seen: return
        if n in stack: raise ValueError(f"cycle at {n}")
        for r in sorted(refs_in(V[n].ast)):
            if r in V: visit(r, stack + (n,))
        seen.add(n); order.append(n)
    for n in V: visit(n)
    return order


def render(model_dir, data_path, out_path):
    V, dims, edges, files, times = load_model(model_dir)
    data = json.load(open(data_path)); periods = period_list(data); version = data.get("version")
    G = Graph(edges, dims)
    notes = []
    skipped = not_translated(V, times)
    for n, (code, why) in skipped.items():
        V[n].keys = [d for d in V[n].keys if d not in times]       # no key column for the declared time dimension
        notes.append((n, "not translated", code, why))
    # rows
    for n in topo(V):
        v = V[n]
        if n in skipped:
            v.rows, v.data = [], []                                 # rendered without rows and without a formula
        elif v.ast is None:
            v.rows, v.data = input_rows_and_values(v, data, periods)
        else:
            v.rows = plan_rows(v, V, G)
            if not v.rows:
                if value_refs(v.ast) or (v.ast[0] == "call" and v.ast[1] == "if" and len(refs_in(v.ast[2][0])) == 1):
                    notes.append((n, "information", "NO-DATA", "no cells for the rendered data: its operands have no data in the excerpt"))
                else:
                    notes.append((n, "not translated", "NO-CELLS", "the formula has no variable reference in value position, so it can never create a cell"))
    L = Layout(V, periods, G)
    wb = Workbook(); wb.remove(wb.active)
    ws_notes = wb.create_sheet("Notes"); ws_dims = wb.create_sheet("Dimensions")
    for name in L.sheets: wb.create_sheet(name[:31])
    ws_src = wb.create_sheet("Source")

    # Dimensions sheet
    r = 1; dimcols = {}
    ws_dims.cell(1, 1, "Dimensions").font = LABEL_FONT
    r = 3
    for d in dims.values():
        ws_dims.cell(r, 1, d.name).font = LABEL_FONT; r += 1
        heads = ["Member", "Description"] + list(d.fk.keys()) + (["Path"] if d.name in G.trees else [])
        c_attr = 1 + len(heads)                                     # attribute columns follow the parents and the path
        for i, h in enumerate(heads + list(d.attrs)): ws_dims.cell(r, 1 + i, h).font = LABEL_FONT
        r += 1; r0 = r
        for m in d.members:
            put_text(ws_dims, r, 1, m); put_text(ws_dims, r, 2, d.desc.get(m, ""))
            for i, p in enumerate(d.fk):
                put_text(ws_dims, r, 3 + i, "|".join(d.fk[p].get(m, [])))
            for i, a in enumerate(d.attrs):
                put_text(ws_dims, r, c_attr + i, d.attrs[a].get(m, ""))
            r += 1
        r1 = r - 1
        if not d.members:                                           # members are data (FML 1.0 [DIM-12]): no ranges
            r += 1; continue
        safe = re.sub(r"\W", "_", d.name)
        wb.defined_names[f"dim_{safe}"] = DefinedName(f"dim_{safe}", attr_text=f"Dimensions!$A${r0}:$A${r1}")
        for i, p in enumerate(d.fk):
            c = COL(3 + i); ps = re.sub(r"\W", "_", p)
            wb.defined_names[f"fk_{safe}_{ps}"] = DefinedName(f"fk_{safe}_{ps}", attr_text=f"Dimensions!${c}${r0}:${c}${r1}")
            if p in dims and dims[p].members:
                dv = DataValidation(type="list", formula1=f"=dim_{ps}", allow_blank=True)
                ws_dims.add_data_validation(dv); dv.add(f"{c}{r0}:{c}{r1}")
        if d.name in G.trees:
            pc = COL(3 + len(d.fk)); fkc = COL(3 + list(d.fk).index(d.name))
            depth = tree_depth(d)
            for rr in range(r0, r1 + 1):
                # ancestors from the PARENT column only — reading the path column itself would be circular
                anc, cur = [], f"A{rr}"
                for _ in range(depth):
                    cur = f'XLOOKUP({cur},$A${r0}:$A${r1},${fkc}${r0}:${fkc}${r1},"")'; anc.append(cur)
                parts = "".join(f'{x}&"|"&' for x in reversed(anc))
                ws_dims[f"{pc}{rr}"] = xl(f'="|"&{parts}A{rr}&"|"')
            wb.defined_names[f"path_{safe}"] = DefinedName(f"path_{safe}", attr_text=f"Dimensions!${pc}${r0}:${pc}${r1}")
        dimcols[d.name] = safe
        r += 1

    untranslated = set()
    # block sheets
    for sname, sh in L.sheets.items():
        ws = wb[sname[:31]]
        ws.cell(1, 1, sname).font = Font(bold=True, size=13)
        ws.cell(2, 1, "Variable").font = LABEL_FONT
        for d, c in sh["c_key"].items(): ws.cell(2, c, d).font = LABEL_FONT
        for i, (p, y, m) in enumerate(periods):
            c = sh["c_p0"] + i
            ws.cell(2, c, f"{y}"); ws.cell(3, c, f"{m:02d}"); ws.cell(4, c, y); ws.cell(5, c, m)
        ws.row_dimensions[4].hidden = True; ws.row_dimensions[5].hidden = True
        for j, y in enumerate(L.years):
            n_in = sum(1 for _, yy, _ in periods if yy == y)
            ws.cell(2, sh["c_y0"] + j, f"{y}" + (" (partial)" if n_in < 12 else "")).font = LABEL_FONT
            ws.cell(3, sh["c_y0"] + j, "Total")
        for vn in sh["vars"]:
            v = V[vn]; first = L.pos[vn][1]
            lab = ws.cell(first - 1, 1, vn); lab.font = LABEL_FONT
            if v.props.get("notes"): lab.comment = Comment(v.props["notes"], "FML")
            numfmt = number_format(v)
            for i, row in enumerate(v.rows):
                rn = first + i
                put_text(ws, rn, 1, vn)
                for d in v.keys: put_text(ws, rn, sh["c_key"][d], row.get(d))
                for ci in range(len(periods)):
                    cell = ws.cell(rn, sh["c_p0"] + ci)
                    if v.ast is None:
                        val_ = v.data[i][ci]
                        anchor = first_col_of_value(v, periods, ci)
                        if anchor is not None and anchor != ci:
                            if v.data[i][anchor] is not None:
                                cell.value = f"={COL(sh['c_p0'] + anchor)}{rn}"
                        else:
                            if val_ is not None: cell.value = val_
                            cell.fill = INPUT_FILL
                    else:
                        try:
                            cell.value = xl(Translator(v, row, rn, ci, L, V, G, version, notes).formula())
                        except NotImplementedError as e:
                            untranslated.add((vn, str(e))); cell.value = None
                    cell.number_format = numfmt
                # year totals
                for j, y in enumerate(L.years):
                    cols = [sh["c_p0"] + ci for ci, (_, yy, _) in enumerate(periods) if yy == y]
                    a, b = f"{COL(cols[0])}{rn}", f"{COL(cols[-1])}{rn}"; rng = f"{a}:{b}"
                    ro = v.rollup
                    if v.is_measure or ro == "formula":
                        f_ = None
                    elif v.props.get("type") == "date" and ro in ("sum", "average"):
                        f_ = None                          # a sum or mean of dates is not a date
                    elif ro == "closing_state": f_ = f'=IF(ISNUMBER({b}),{b},"")'
                    elif ro == "beginning_state": f_ = f'=IF(ISNUMBER({a}),{a},"")'
                    elif ro == "average": f_ = f'=IFERROR(AVERAGE({rng}),"")'
                    elif ro in ("min", "max"): f_ = f'=IF(COUNT({rng})=0,"",{ro.upper()}({rng}))'
                    elif ro == "none": f_ = None
                    else: f_ = f'=IF(COUNT({rng})=0,"",SUM({rng}))'
                    if f_: ws.cell(rn, sh["c_y0"] + j, f_).number_format = numfmt
        # helper columns (filled after all formulas requested them)
    for sname, sh in L.sheets.items():
        ws = wb[sname[:31]]
        for k, (vn, spec) in enumerate(sh["helpers"]):
            c = sh["c_h0"] + k; kind, chain = spec
            ws.cell(2, c, f"{vn} · {'→'.join(chain)}" + (" path" if kind == "path" else "")).font = Font(italic=True, color="808080")
            v = V[vn]; first = L.pos[vn][1]
            for i in range(len(v.rows)):
                rn = first + i
                expr = f"${COL(sh['c_key'][chain[0]])}{rn}"
                for x, y in zip(chain, chain[1:]):
                    expr = f'XLOOKUP({expr},dim_{dimcols[x]},fk_{dimcols[x]}_{dimcols[y]},"")'
                if kind == "path":
                    expr = f'XLOOKUP({expr},dim_{dimcols[chain[-1]]},path_{dimcols[chain[-1]]},"")'
                ws.cell(rn, c, xl("=" + expr))
            ws.column_dimensions[COL(c)].hidden = True
    for vn, why in sorted(untranslated):
        notes.append((vn, "not translated", "UNSUPPORTED-FUNCTION", why))

    # Notes entries derived from the model
    multi_year = len(L.years) > 1
    for v in V.values():
        if v.ast is None or v.name in skipped: continue
        fns = calls_in(v.ast)
        if multi_year and ({"delay", "cumsum", "spread"} & fns): notes.append((v.name, "assumption", "DELAY-YEAR", "values carry across the year boundary"))
        if v.is_measure: notes.append((v.name, "assumption", "MEASURE-TOTAL", "a measure, evaluated at the total of the excerpt; no year total"))
        if v.props.get("calculateOnDemand"): notes.append((v.name, "assumption", "ON-DEMAND", "computed normally in the workbook"))
    notes.append(("(workbook)", "assumption", "MAPPING-ONE-WAY", "a mapping changed on Dimensions does not travel back to the member files"))
    head = [
        "Translated from FML",
        f"Source: {', '.join(os.path.relpath(f, model_dir) for f in files)} and the member files they name",
        f"Rendered version: {version or '(model has no Versions)'}; periods {periods[0][0]} to {periods[-1][0]}; data: sample data ({os.path.basename(data_path)})",
        "Null profile: null-faithful (empty or \"\" = null; 0 = zero)",
        "This workbook reconstructs the values the FML semantics define at the coordinates it renders. It does not reproduce the engine's behaviour: it always has somewhere to write, so it cannot show defects that come from cells not existing. Agreement with its own formulas proves the translation, not the model.",
        "Verification: see the verification report next to this file.",
    ]
    for i, h in enumerate(head, 1): ws_notes.cell(i, 1, h)
    ws_notes.cell(1, 1).font = Font(bold=True, size=13)
    r = len(head) + 2
    for i, h in enumerate(["Variable", "Kind", "Code", "Detail"]): ws_notes.cell(r, 1 + i, h).font = LABEL_FONT
    for n in notes:
        r += 1
        for i, x in enumerate(n): put_text(ws_notes, r, 1 + i, x)
    ws_notes.column_dimensions["A"].width = 34; ws_notes.column_dimensions["D"].width = 90

    # Source
    r = 1
    for f in files:
        ws_src.cell(r, 1, os.path.relpath(f, model_dir)).font = LABEL_FONT; r += 1
        for line in open(f, encoding="utf8").read().splitlines():
            put_text(ws_src, r, 1, line); r += 1
        r += 1
    ws_src.column_dimensions["A"].width = 120
    for sname in L.sheets:
        ws = wb[sname[:31]]; ws.column_dimensions["A"].width = 34; ws.freeze_panes = ws.cell(6, L.sheets[sname]["c_p0"])
    wb.calculation.fullCalcOnLoad = True
    wb.save(out_path)
    untranslated |= {(n, why) for n, (_, why) in skipped.items()}
    return {"untranslated": sorted(untranslated), "notes": notes, "layout": L, "V": V}


def tree_depth(d):
    parent = {m: (d.fk[d.name].get(m) or [None])[0] for m in d.members}
    best = 0
    for m in d.members:
        k, cur = 0, parent.get(m)
        while cur and k < 50: k += 1; cur = parent.get(cur)
        best = max(best, k)
    return max(best, 1)


def first_col_of_value(v, periods, ci):
    """§5.3: a variable without months holds its value in the first month of each
    year (Years only), in the first column of each month of the year (Months only, a
    seasonal profile) or of the excerpt (no time dimension); other columns refer to it."""
    if v.has_months and v.has_years: return None
    if v.has_months:
        m = periods[ci][2]
        return next(i for i, (_, _, mm) in enumerate(periods) if mm == m)
    if v.has_years:
        y = periods[ci][1]
        return next(i for i, (_, yy, _) in enumerate(periods) if yy == y)
    return 0


def calls_in(n, acc=None):
    acc = set() if acc is None else acc
    if n is None: return acc
    if n[0] == "call":
        acc.add(n[1])
        for a in n[2]: calls_in(a, acc)
    elif n[0] == "bin": calls_in(n[2], acc); calls_in(n[3], acc)
    return acc


def number_format(v):
    fmt_ = v.props.get("format"); dec = v.props.get("decimals")
    nf = v.props.get("numberFormat")
    if isinstance(nf, dict) and nf.get("formatString"): return nf["formatString"]
    if fmt_ == "percentage": return "0.00%" if dec is None else ("0%" if dec == 0 else "0." + "0" * int(dec) + "%")
    if fmt_ == "date" or v.props.get("type") == "date": return "yyyy-mm-dd"
    d = 2 if dec is None else int(dec)
    return "#,##0" + ("." + "0" * d if d else "")


if __name__ == "__main__":
    res = render(*sys.argv[1:4])
    for u in res["untranslated"]: print("UNTRANSLATED", u)
    print("wrote", sys.argv[3])
