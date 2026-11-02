"""Static checks over a loaded model (FML 1.0 §15, Annex C).

Every check here is decidable from the documents, the member files and the
manifest alone; checks that need data or an engine are listed in README.md.
"""
import re
from collections import defaultdict

from .members import has_control, null_name
from .model import display
from .syntax import Bin, Call, MRef, Neg, Num, Ref, walk

TIME = ("YearMonth", "Years", "Months")
READING = ("Quarters", "Half years", "Year to date")
SYSTEM = set(TIME) | set(READING) | {"Versions"}
PREDEFINED = [("YearMonth", "Years"), ("YearMonth", "Months"), ("Months", "Quarters"),
              ("Quarters", "Half years"), ("Months", "Year to date")]

# Arity of the standard functions (§12, Annex B): name -> (min, max or None)
FUNCS = {
    "round": (1, 2), "floor": (1, 1), "ceil": (1, 1), "abs": (1, 1), "power": (2, 2),
    "max": (2, 2), "min": (2, 2),
    "sum": (1, None), "avg": (2, 3),
    "cumsum": (1, 3), "delay": (2, 2), "spread": (2, 3),
    "if": (2, 3), "eq": (2, 2), "gt": (2, 2), "gte": (2, 2), "lt": (2, 2), "lte": (2, 2),
    "and": (1, None), "or": (1, None), "not": (1, 1),
    "hasvalue": (1, 1), "hasdmember": (1, None),
    "currentdate": (0, 0), "currentmonth": (0, 0), "currentyear": (0, 0), "daysincurrentmonth": (0, 0),
    "date": (3, 3), "edate": (2, 2), "year": (1, 1), "month": (1, 1), "day": (1, 1),
}
TIME_SERIES = {"cumsum", "delay", "spread", "avg"}
COMPARISONS = {"eq", "gt", "gte", "lt", "lte"}
CONTEXT_FUNCS = {"currentdate", "currentmonth", "currentyear", "daysincurrentmonth"}
# The dimensions a date context function reads its period from (§12.5, [FUN-8]); a declared time dimension
# (`@semantic time`, §6.9) is not one of them.
CONTEXT_REQUIRES = {
    "currentdate": ("YearMonth",),
    "daysincurrentmonth": ("YearMonth",),
    "currentmonth": ("YearMonth", "Months"),
    "currentyear": ("YearMonth", "Years"),
}
SELECTORS = {"and", "or", "not"}

STANDARD_PROPS = ["type", "rollup", "format", "decimals", "numberFormat", "folder", "desc", "notes",
                  "readonly", "numberValidation"]
TYPES = {"number", "integer", "string", "date", "boolean"}
ROLLUPS = {"sum", "average", "avg", "min", "max", "closing_state", "last", "beginning_state", "first", "none"}
ROLLUP_ALIAS = {"avg": "average", "last": "closing_state", "first": "beginning_state"}
FORMATS = {"number", "percentage", "currency", "date"}
NF_TYPES = {"NUMBER", "PERCENTAGE", "CURRENCY", "DATE"}
FORMAT_TO_NF = {"number": "NUMBER", "percentage": "PERCENTAGE", "currency": "CURRENCY", "date": "DATE"}
_INT = re.compile(r"[0-9]+\Z")


def norm_rollup(v):
    return ROLLUP_ALIAS.get(v, v)


def is_in(n): return n.endswith(" IN") or n.endswith("_IN")
def is_out(n): return n.endswith(" OUT") or n.endswith("_OUT")
def is_import(n): return n.startswith("IMPORT ") or n.startswith("IMPORT_")


def is_const(n):
    if isinstance(n, Num):
        return True
    if isinstance(n, Neg):
        return is_const(n.x)
    if isinstance(n, Bin):
        return is_const(n.l) and is_const(n.r)
    return False


def refs(n):
    return [x for x in walk(n) if isinstance(x, Ref)]


class Graph:
    def __init__(self, edges):
        self.parents = defaultdict(set)
        for c, p in edges:
            if c != p:
                self.parents[c].add(p)

    def reach(self, a, b, avoid=None):
        """Is b reachable from a through one or more parents (not passing through `avoid`)?"""
        seen, stack = {a}, [a]
        while stack:
            x = stack.pop()
            for p in self.parents.get(x, ()):
                if p == b:
                    return True
                if p not in seen and p != avoid:
                    seen.add(p); stack.append(p)
        return False

    def connected(self, a, b):
        return a == b or self.reach(a, b) or self.reach(b, a)


def sccs(nodes, edges):
    """Tarjan's strongly connected components. edges: node -> iterable of nodes."""
    index, low, on, stack, out, counter = {}, {}, set(), [], [], [0]

    def strong(v):
        index[v] = low[v] = counter[0]; counter[0] += 1
        stack.append(v); on.add(v)
        for w in edges.get(v, ()):
            if w not in index:
                strong(w); low[v] = min(low[v], low[w])
            elif w in on:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp = []
            while True:
                w = stack.pop(); on.discard(w); comp.append(w)
                if w == v:
                    break
            out.append(comp)
    import sys
    old = sys.getrecursionlimit()
    sys.setrecursionlimit(max(old, 10000))
    for v in nodes:
        if v not in index:
            strong(v)
    sys.setrecursionlimit(old)
    return out


class Checker:
    def __init__(self, model, sink):
        self.m, self.sink = model, sink
        self.mf = model.manifest
        self.complete = bool(self.mf.valid and self.mf.members_complete)

    def r(self, path, line, col, code, msg):
        self.sink.add(path, line, col, code, msg)

    # ------------------------------------------------------------------ entry
    def run(self):
        m = self.m
        self.vars = {}
        for doc in m.docs:
            for v in doc.variables:
                if v.name in self.vars:
                    first = self.vars[v.name]
                    self.r(v.path, v.line, v.col, "FML-E0201",
                           f"variable {v.name!r} is already declared at {first.path}:{first.line} [DOC-1]")
                else:
                    self.vars[v.name] = v
        self.collect_dimensions()
        self.check_dimensions()
        self.check_graph()
        for doc in m.docs:
            for block in doc.defaults_blocks:
                self.check_prop_list(block, doc.path)
        for doc in m.docs:
            for v in doc.variables:
                self.check_variable(v)
        self.check_dependency_cycles()
        self.check_styles()

    # ------------------------------------------------------------------ dimension declarations
    def collect_dimensions(self):
        """Declarations (§6.1, [DOC-6]): FML-E0207 for a system dimension, FML-E0209 for a second one."""
        self.decls = {}
        for doc in self.m.docs:
            for d in doc.dimensions:
                if has_control(d.name):
                    self.r(d.path, d.nline, d.ncol, "FML-E0205",
                           f"dimension name {d.name!r} contains a control character [LEX-3]")
                if d.name in SYSTEM:
                    self.r(d.path, d.line, d.col, "FML-E0207",
                           f"{d.name} is a system dimension: the engine provides it, and a model does not declare it "
                           f"[DIM-12], [DIM-6]")
                    continue
                if d.name in self.decls:
                    p = self.decls[d.name]
                    self.r(d.path, d.line, d.col, "FML-E0209",
                           f"dimension {d.name} is already declared at {p.path}:{p.line} [DOC-6]")
                    continue
                self.decls[d.name] = d
        self.known_dims = set(SYSTEM) | set(self.decls)
        self.declared_time = {n for n, d in self.decls.items() if d.semantic_time()}
        self.time_dims = set(TIME) | self.declared_time
        self.rollup_none = {n for n, d in self.decls.items()
                            if any(p.key == "rollup" and p.kind == "ident" and p.value == "none" for p in d.props)}
        # the member file of each declaration that names one, and the members of each dimension
        self.tables, self.members = {}, {}
        for n, d in self.decls.items():
            t = self.m.table_of.get(id(d))
            if t is not None and t.ok:
                self.tables[n] = t
            names = None
            if d.source == "inline":
                names = [x for x, _, _ in d.members]
            elif t is not None and t.ok and t.dim == n:
                names = t.names()
            if names is not None:
                s = set(names)
                if d.has("null"):
                    s.add(null_name(n))
                self.members[n] = s
        # parents [PARENT-1]: retain the first edge for recovery; the parser reports duplicates [PARENT-4]
        self.edges = {}
        for n, d in self.decls.items():
            for p, parent, words in d.parents():
                self.edges.setdefault((n, parent), (p, words, d))
        self.graph = Graph(list(self.edges) + PREDEFINED)
        self.stmt_graph = Graph(list(self.edges))

    def is_null_parent(self, parent):
        d = self.decls.get(parent)
        return d is not None and d.has("null")

    def check_dimensions(self):
        named_parent = {}                                # parent -> a child edge that may leave members unmapped
        for n, d in self.decls.items():
            r = lambda line, col, code, msg, _d=d: self.r(_d.path, line, col, code, msg)
            self.check_dim_props(d)
            parents = d.parents()
            pnames = {x for _, x, _ in parents}
            attrs = d.attributes()
            for p, parent, words in parents:
                if parent not in self.known_dims:
                    r(p.vline, p.vcol, "FML-E0208", f"@parent names {parent!r}, which is neither declared nor a system "
                      f"dimension [DOC-6]")
                elif parent != n and "required" not in words and self.may_be_unmapped(d, parent):
                    named_parent.setdefault(parent, (d, p))
            if d.source == "inline" and (parents or attrs):
                r(d.line, d.col, "FML-E0613", f"{n} lists its members inline and has "
                  f"{'@parent' if parents else '@attribute'}: an inline list has no column for parents or attributes; "
                  f"use a member file or no source [DIM-12]")
            for p, an, _ in attrs:
                if an in pnames or an == "@description":
                    r(p.vline, p.vcol, "FML-E0614", f"attribute {an!r} " + ("has the name of a parent of " + n
                      if an in pnames else "is named like the description column") + " [DIM-3]")
            if d.source == "inline":
                seen = {}
                for mname, ln, cl in d.members:
                    if has_control(mname):
                        r(ln, cl, "FML-E0205", f"member name {mname!r} contains a control character [LEX-3]")
                    if mname == null_name(n):
                        r(ln, cl, "FML-E0615", f"the inline list names {mname!r}; only `@null` gives a dimension its "
                          f"NULL member [DIM-5]")
                        continue
                    low = mname.lower()
                    if low in seen:
                        how = "is listed twice" if seen[low] == mname else f"differs only by case from {seen[low]!r}"
                        r(ln, cl, "FML-E0603", f"member {mname!r} {how}; member names are unique case-insensitively "
                          f"[DIM-1]")
                        continue
                    seen[low] = mname
                if not seen:
                    r(d.line, d.col, "FML-E0607", f"dimension {n} lists no member [DIM-8]")
            elif d.source == "file":
                t = self.m.table_of.get(id(d))
                if t is None:
                    r(d.fline, d.fcol, "FML-E0612", f"member file {d.file!r} does not exist (paths are relative to the "
                      f"model directory) [DIM-12]")
                elif t.ok:
                    self.check_table(d, t)
        for parent, (child, p) in sorted(named_parent.items()):
            pd = self.decls.get(parent)
            if pd is None or pd.has("null") or parent in self.declared_time:
                continue
            self.r(pd.path, pd.line, pd.col, "FML-W0606",
                   f"{parent} is a parent of {child.name}, which may leave members unmapped, and does not declare "
                   f"@null: a member of {child.name} with an empty {parent} cell reaches no parent [DIM-5], [PARENT-3]")

    def may_be_unmapped(self, d, parent):
        """True when a member of d may have no parent in `parent` [DIM-5]: its members are data, or its member
        file has an empty cell in that parent's column. A fully mapped dimension MAY omit @null."""
        if d.source is None:
            return True
        if d.source != "file":
            return False
        t = self.m.table_of.get(id(d))
        if t is None or not t.ok:
            return False
        return any(m.cells.get(parent) is None or m.cells[parent].text == "" for m in t.members)

    def check_dim_props(self, d):
        """Dimension properties (DIM-13): domains, FML-E0903; repetition, FML-W0204 except parents (parser)."""
        bad = lambda p, msg: self.r(d.path, p.vline, p.vcol, "FML-E0903", msg)
        seen = {}
        for p in d.props:
            k, kind, v = p.key, p.kind, p.value
            if kind == "invalid":
                continue
            if k == "parent":
                if kind not in ("ident", "string", "words"):
                    bad(p, f"@parent takes a dimension name, then optionally many and required; found {p.raw} [DIM-13]")
                    continue
                words = v[1] if kind == "words" else []
                extra = [w for w in words if w not in ("many", "required")]
                if extra or len(set(words)) != len(words):
                    bad(p, f"@parent takes a dimension name and the words many and required, each at most once; "
                        f"found {p.raw} [DIM-13]")
                    continue
                key = ("parent", v[0] if kind == "words" else v)
            elif k == "attribute":
                if kind != "words" or len(v[1]) != 1 or v[1][0] not in TYPES:
                    bad(p, f"@attribute takes a name and a type ({', '.join(sorted(TYPES))}); found {p.raw} [DIM-13]")
                    continue
                key = ("attribute", v[0])
            elif k == "null":
                if kind != "none":
                    bad(p, f"@null takes no value; found {p.raw} [DIM-13]")
                key = ("null",)
            elif k == "semantic":
                if (kind, v) != ("ident", "time"):
                    bad(p, f"@semantic takes the value time; found {p.raw} [DIM-13]")
                key = ("semantic",)
            elif k == "rollup":
                if (kind, v) != ("ident", "none"):
                    bad(p, f"@rollup on a dimension takes the value none; found {p.raw} [DIM-13]")
                key = ("rollup",)
            elif k in ("folder", "desc"):
                if kind != "string":
                    bad(p, f"@{k} takes a string; found {p.raw} [DIM-13]")
                key = (k,)
            else:
                self.r(d.path, p.line, p.col, "FML-I0901", f"@{k} is not a dimension property (preserved) [DIM-13], "
                       f"[PROP-12]")
                continue
            if key in seen and k != "parent":             # duplicate parents are FML-E0707 at parse time
                what = f"@{k} {key[1]}" if len(key) > 1 else f"@{k}"
                self.r(d.path, p.line, p.col, "FML-W0204", f"{what} is given twice on {d.name} (also line "
                       f"{seen[key].line}); the last occurrence is used [DIM-13]")
            seen[key] = p

    def check_table(self, d, t):
        """A member file against its declaration [DIM-3], [DIM-10], [PARENT-2], [PARENT-3]."""
        n = d.name
        r = lambda line, col, code, msg: self.r(t.path, line, col, code, msg)
        if t.dim != n:
            code = "FML-E0705" if t.dim in self.known_dims else "FML-E0208"
            r(t.dline, t.dcol, code, f"the header names {t.dim!r}, but the file is the member file of {n}: its first "
              f"cell is the name of the declaration that names it [DIM-3]")
            return
        parents = {x: words for _, x, words in d.parents()}
        attrs = {an for _, an, _ in d.attributes()}
        seen = set()
        for i, c in enumerate(t.columns):
            if c.text == "":
                continue
            if c.text == "@description":
                if i != 0:
                    r(c.line, c.col, "FML-E0705", "`@description` is the second header cell, after the dimension name "
                      "[DIM-3]")
                elif "@description" in seen:
                    pass
                seen.add(c.text)
                continue
            if c.text in seen:
                r(c.line, c.col, "FML-E0705", f"column {c.text!r} appears twice in the header [DIM-3]")
                continue
            seen.add(c.text)
            if c.text not in parents and c.text not in attrs:
                r(c.line, c.col, "FML-E0705", f"column {c.text!r} is neither a parent nor an attribute of {n}; "
                  f"header cells match the declaration's @parent and @attribute names with exact case [DIM-3]")
        for p, x, _ in d.parents():
            if x not in seen:
                self.r(d.path, p.line, p.col, "FML-E0705", f"@parent {x}: the member file {t.path} has no {x} column "
                       f"[DIM-3], [PARENT-4]")
        for p, an, _ in d.attributes():
            if an not in seen and an not in parents:
                self.r(d.path, p.line, p.col, "FML-E0705", f"@attribute {an}: the member file {t.path} has no "
                       f"{an} column [DIM-3]")
        if not t.members:
            r(t.dline, t.dcol, "FML-E0607", f"dimension {n} has no member [DIM-8]")
        for parent, words in parents.items():
            if parent not in seen:
                continue
            filled = False
            for mem in t.members:
                c = mem.cells.get(parent)
                if c is None:
                    continue
                parts = [x for x in c.text.split("|") if x]
                if not parts:
                    if "required" in words:
                        r(c.line, c.col, "FML-E0617", f"member {mem.name!r} has no {parent}, and @parent {parent} is "
                          f"required; name the parent, or {null_name(parent)!r} where it is unknown [PARENT-3]")
                    continue
                filled = True
                if len(parts) > 1 and "many" not in words:
                    r(c.line, c.col, "FML-E0616", f"member {mem.name!r} has {len(parts)} parents in {parent}, which is "
                      f"declared without many [PARENT-2]")
                for pm in parts:
                    self.check_fk_cell(t, parent, pm, c.line, c.col)
            if not filled and t.members:
                p = next(p for p, x, _ in d.parents() if x == parent)
                self.r(d.path, p.line, p.col, "FML-W0703", f"the {parent} column of {t.path} is empty in every row: "
                       f"the parent routes nothing to a real member [§7.5]")

    def check_fk_cell(self, t, parent, member, line, col):
        if parent in SYSTEM:
            st, why = self.member_status(parent, member)
            if st == "malformed" or (st == "no" and self.complete):
                self.r(t.path, line, col, "FML-E0610", f"parent cell names {member!r}, not a member of {parent}: {why} "
                       f"[DIM-10]")
            return
        ms = self.members.get(parent)
        if ms is None:
            if self.complete and parent in self.decls and parent not in self.declared_time:
                self.r(t.path, line, col, "FML-E0610", f"parent cell names {member!r}, but {parent} lists no members "
                       f"(membersComplete) [DIM-10]")
            return
        if member not in ms:
            hint = (f"; {parent} does not declare @null" if member == null_name(parent) else "")
            self.r(t.path, line, col, "FML-E0610",
                   f"parent cell names {member!r}, which is not a member of {parent}{hint} [DIM-10]")

    # ------------------------------------------------------------------ members
    def member_status(self, dim, member):
        """'yes', 'no' (not a member), 'unknown' (cannot be decided) or 'malformed' (never a member)."""
        if dim == "YearMonth":
            mm = re.fullmatch(r"(\d{4})-(\d{2})", member)
            if not mm or not 1 <= int(mm.group(2)) <= 12:
                return "malformed", "YearMonth members are \"YYYY-MM\" with a month 01–12 [§6.7]"
            if self.mf.horizon:
                lo, hi = self.mf.horizon
                if not lo <= int(mm.group(1)) <= hi:
                    return "no", f"outside the horizon {lo}-01 … {hi}-12 [§5.7]"
            return ("yes", "") if self.mf.horizon else ("unknown", "")
        if dim == "Years":
            if not re.fullmatch(r"\d{4}", member):
                return "malformed", "Years members are \"YYYY\" [§6.7]"
            if self.mf.horizon:
                lo, hi = self.mf.horizon
                return ("yes", "") if lo <= int(member) <= hi else ("no", f"outside the horizon {lo} … {hi} [§5.7]")
            return "unknown", ""
        if dim in ("Months", "Year to date"):
            ok = re.fullmatch(r"\d{2}", member) and 1 <= int(member) <= 12
            return ("yes", "") if ok else ("malformed", f"{dim} members are \"01\" … \"12\" [§6.7]")
        if dim == "Quarters":
            return ("yes", "") if member in ("Q1", "Q2", "Q3", "Q4") else ("malformed", "Quarters members are Q1 … Q4 [§6.7]")
        if dim == "Half years":
            return ("yes", "") if member in ("H1", "H2") else ("malformed", "Half years members are H1 and H2 [§6.7]")
        if dim == "Versions":
            if self.mf.valid and self.mf.versions is not None:
                return ("yes", "") if member in self.mf.versions else (
                    "no", f"not in the manifest's versions ({', '.join(sorted(self.mf.versions))}) [§5.7]")
            return ("yes", "") if member in ("Actual", "Plan") else ("unknown", "")
        ms = self.members.get(dim)
        if ms is None:
            return "unknown", f"dimension {dim} does not list its members"
        if member in ms:
            return "yes", ""
        low = {n.lower(): n for n in ms}
        if member.lower() in low:
            return "no", f"the member is {low[member.lower()]!r}; names are referenced case-exactly [LEX-2]"
        if member == null_name(dim):
            return "no", f"{dim} does not declare @null [DIM-5]"
        return "no", f"not listed in {self.tables[dim].path if dim in self.tables else 'the declaration of ' + dim}"

    def check_member_ref(self, path, line, col, dim, member, what="member reference"):
        if has_control(member):
            self.r(path, line, col, "FML-E0205", f"member name {member!r} contains a control character [LEX-3]")
        if dim not in self.known_dims:
            return                                       # FML-E0208, reported where the dimension is named
        st, why = self.member_status(dim, member)
        if st == "malformed" or (st == "no" and self.complete):
            self.r(path, line, col, "FML-E0302", f"unknown member {member!r} of {dim}: {why}")
        # A dimension with no member source has its members as data: checked at the model stage only [§5.7].

    # ------------------------------------------------------------------ the dimension graph
    def check_graph(self):
        """Graph shape over the declared parents (§7.5, DIMD-11). Each diagnostic is placed on a @parent line."""
        at = {k: (d.path, p.line, p.col) for k, (p, _, d) in self.edges.items()}
        nodes = sorted({x for e in self.edges for x in e})
        edges = defaultdict(set)
        for (c, p) in self.edges:
            if c != p:
                edges[c].add(p)
        for comp in sccs(nodes, edges):
            if len(comp) > 1:
                cs = set(comp)
                inside = sorted(at[k] for k in self.edges if k[0] in cs and k[1] in cs and k[0] != k[1])
                self.r(*inside[0], "FML-W0701", f"cycle in the dimension graph through {', '.join(sorted(comp))} [§7.5]")
        g = self.stmt_graph
        for a in nodes:
            outs = sorted(edges.get(a, ()))
            for b in nodes:
                if a == b:
                    continue
                via = [x for x in outs if x == b or g.reach(x, b)]
                if len(via) < 2:
                    continue
                ins = [x for x in nodes if b in edges.get(x, ()) and (x == a or g.reach(a, x))]
                if len(ins) < 2:
                    continue
                self.r(*at[(a, via[0])], "FML-I0702",
                       f"diamond: {b} is reached from {a} along more than one path (via {', '.join(via)}) [§7.5]")
        for (a, b) in self.edges:
            if a == b or a in SYSTEM or b in SYSTEM:
                continue
            for c in nodes:
                if c in (a, b):
                    continue
                if a in edges.get(c, ()) and b in edges.get(c, ()):     # both parents of c
                    self.r(*at[(a, b)], "FML-W0704",
                           f"{a} and {b} are both parents of {c}; making {b} a parent of {a} makes aggregation "
                           f"ambiguous [DIMD-11]")
                    break

    # ------------------------------------------------------------------ properties
    def check_prop_list(self, props, path):
        seen = {}
        for p in props:
            if p.key in seen:
                self.r(path, p.line, p.col, "FML-W0204",
                       f"@{p.key} is given twice (also line {seen[p.key].line}); the last occurrence is used [PROP-2]")
            seen[p.key] = p
            self.check_prop(p, path)

    def check_prop(self, p, path):
        k, kind, v = p.key, p.kind, p.value
        bad = lambda msg: self.r(path, p.vline, p.vcol, "FML-E0903", msg)
        if kind == "invalid":
            return
        if k not in STANDARD_PROPS:
            self.r(path, p.line, p.col, "FML-I0901", f"unknown property @{k} (preserved) [PROP-12]")
            return
        if k == "type":
            if kind != "ident" or v not in TYPES:
                bad(f"@type takes one of {', '.join(sorted(TYPES))}; found {p.raw} [§9.4.1]")
        elif k == "rollup":
            if kind == "ident":
                if v not in ROLLUPS:
                    self.r(path, p.vline, p.vcol, "FML-I0905",
                           f"@rollup {v} is not a standard rollup (an extension; preserved) [EXT-2]")
            else:
                bad(f"@rollup takes an identifier such as sum or closing_state; found {p.raw} [§9.4.2]")
        elif k == "format":
            if kind == "call":
                self.r(path, p.vline, p.vcol, "FML-E0902", f"@format takes a bare keyword; `{p.raw}` is not FML — "
                       f"write @format {v} and give the code in @numberFormat [PROP-6]")
            elif kind != "ident" or v not in FORMATS:
                bad(f"@format takes one of {', '.join(sorted(FORMATS))}; found {p.raw} [§9.4.3]")
        elif k == "decimals":
            if kind != "number" or not _INT.match(v):
                bad(f"@decimals takes an integer ≥ 0; found {p.raw} [§9.3]")
        elif k == "numberFormat":
            if kind != "object":
                bad(f"@numberFormat takes an object; found {p.raw} [§14.1]")
                return
            for fk, fkind, fv, raw in v:
                if fk == "type" and not (fkind in ("ident", "string") and fv in NF_TYPES):
                    bad(f"numberFormat.type takes one of {', '.join(sorted(NF_TYPES))}; found {raw} [§14.1]")
                elif fk == "decimals" and not (fkind == "number" and _INT.match(fv)):
                    bad(f"numberFormat.decimals takes an integer ≥ 0; found {raw} [§14.1]")
                elif fk == "custom" and fkind != "bool":
                    bad(f"numberFormat.custom takes true or false; found {raw} [§14.1]")
                elif fk == "formatString" and fkind != "string":
                    bad(f"numberFormat.formatString takes a string; found {raw} [§14.1]")
                elif fk == "currency" and fkind not in ("string", "ident"):
                    bad(f"numberFormat.currency takes an ISO 4217 code; found {raw} [§14.1]")
        elif k in ("folder", "desc", "notes"):
            if kind != "string":
                bad(f"@{k} takes a string; found {p.raw} [§9.3]")
        elif k == "readonly":
            if kind != "bool":
                bad(f"@readonly takes true or false; found {p.raw} [§9.3]")
        elif k == "numberValidation":
            if kind != "object":
                bad(f"@numberValidation takes an object {{ min: n, max: n }}; found {p.raw} [§9.4.8]")
                return
            vals = {}
            for fk, fkind, fv, raw in v:
                if fk not in ("min", "max"):
                    bad(f"@numberValidation has the fields min and max only; found {fk} [§9.4.8]")
                elif fkind != "number":
                    bad(f"numberValidation.{fk} takes a number; found {raw} [§9.4.8]")
                else:
                    vals[fk] = float(fv)
            if "min" in vals and "max" in vals and vals["min"] > vals["max"]:
                bad("numberValidation.min is greater than max [§9.4.8]")

    # ------------------------------------------------------------------ variables
    def check_variable(self, v):
        path = v.path
        r = lambda line, col, code, msg: self.r(path, line, col, code, msg)
        if has_control(v.name):
            r(v.line, v.col, "FML-E0205", f"variable name {v.name!r} contains a control character [LEX-3]")
        # grain
        seen, times, reading = {}, [], []
        for g in v.grain:
            if has_control(g.dim):
                r(g.line, g.col, "FML-E0205", f"dimension name {g.dim!r} contains a control character [LEX-3]")
            elif g.dim not in self.known_dims:
                r(g.line, g.col, "FML-E0208", f"{g.dim!r} in the grain of {v.name!r} is neither declared nor a system "
                  f"dimension [DOC-6]")
            if g.dim in seen:
                r(g.line, g.col, "FML-E0202", f"dimension {g.dim} appears twice in the grain of {v.name!r} [VAR-3]")
            seen[g.dim] = g
            if g.dim in self.time_dims:
                times.append(g)
            if g.dim in READING:
                reading.append(g)
            if g.pin is not None:
                self.check_member_ref(path, g.pline, g.pcol, g.dim, g.pin, "pinned grain entry")
        if len({g.dim for g in times}) > 1:
            g = times[1]
            r(g.line, g.col, "FML-E0206", f"the grain holds more than one time dimension "
              f"({', '.join(x.dim for x in times)}); a grain holds at most one [VAR-9]")
        for g in reading:
            r(g.line, g.col, "FML-E0206", f"{g.dim} is a reading level: values are read there, never stored; "
              f"it cannot be in a grain [VAR-9]")
        pins = [g for g in v.grain if g.pin is not None]
        for i, a in enumerate(pins):
            for b in pins[i + 1:]:
                if a.dim != b.dim and (self.graph.reach(a.dim, b.dim) or self.graph.reach(b.dim, a.dim)):
                    r(b.line, b.col, "FML-W0203", f"members pinned on {a.dim} and {b.dim}, which are connected by a "
                      f"parent; pin only the child [VAR-7]")
        # properties
        self.check_prop_list(v.own, path)
        props = v.props()
        self.check_formats(v, props)
        # formula
        if v.formula is not None:
            self.check_formula(v, props)
        self.check_naming(v, props)

    def check_formats(self, v, props):
        nf = props.get("numberFormat")
        fmt = props.get("format")
        fields = {}
        if nf is not None and nf.kind == "object":
            fields = {k: (kind, val) for k, kind, val, _ in nf.value}
        etype = None
        if "type" in fields:
            etype = fields["type"][1]
        elif fmt is not None and fmt.kind == "ident":
            etype = FORMAT_TO_NF.get(fmt.value)
        etype = etype or "NUMBER"
        v.eff_nf_type = etype
        fs = fields.get("formatString")
        if fs is None or fs[0] != "string":
            return
        s = fs[1]
        bare = re.sub(r'"[^"]*"|\\.', "", s)
        has_pct = "%" in bare
        custom = fields.get("custom", ("bool", False))[1] is True
        where = (nf.vline, nf.vcol)
        if etype == "PERCENTAGE" and not has_pct:
            self.r(v.path, *where, "FML-W1401", f"numberFormat type PERCENTAGE with formatString {s!r}, which has no `%`: "
                   f"0.15 displays as 0.15, not 15 % [FMT-1]")
        elif etype in ("NUMBER", "CURRENCY") and has_pct:
            self.r(v.path, *where, "FML-W1401", f"numberFormat type {etype} with a percentage formatString {s!r} [FMT-1]")
        elif not custom and etype in NF_TYPES:
            dec = fields.get("decimals")
            if dec is None:
                d = props.get("decimals")
                dec = ("number", d.value) if d is not None and d.kind == "number" else ("number", "2")
            try:
                n = int(dec[1])
            except ValueError:
                return
            part = "." + "0" * n if n > 0 else ""
            derived = {"NUMBER": "#,##0" + part, "CURRENCY": "#,##0" + part, "PERCENTAGE": "#,##0" + part + "%",
                       "DATE": ""}[etype]
            if s != derived:
                self.r(v.path, *where, "FML-W1401", f"formatString {s!r} disagrees with type {etype} and {n} decimals "
                       f"(derived: {derived!r}) and custom is not true [FMT-1]")

    # -- formula
    def check_formula(self, v, props):
        path, f = v.path, v.formula
        r = lambda line, col, code, msg: self.r(path, line, col, code, msg)
        self.cur = v
        self.value_refs, self.other_refs, self.mrefs, self.vref_filters = [], [], [], []

        def strvar(n):
            if isinstance(n, Call) and n.f == "sum" and n.args:
                n = n.args[0]
            if isinstance(n, Ref) and n.name in self.vars:
                tp = self.vars[n.name].props().get("type")
                return tp is not None and tp.kind == "ident" and tp.value == "string"
            return False

        def e0410(n, how):
            if strvar(n):
                name = n.name if isinstance(n, Ref) else n.args[0].name
                r(n.line, n.col, "FML-E0410", f"{name!r} has @type string and cannot be an operand of {how} [EVAL-33]")

        def go(n, mode, filters):
            if isinstance(n, Num):
                return
            if isinstance(n, Ref):
                if n.name not in self.vars:
                    r(n.line, n.col, "FML-E0301", f"reference to an unknown variable {n.name!r} [EXPR-6]")
                if mode == "value":
                    self.value_refs.append(n); self.vref_filters.append((n, filters))
                else:
                    self.other_refs.append(n)
                return
            if isinstance(n, MRef):
                r(n.line, n.col, "FML-E0105", "a member reference may appear only as a filter of sum, an argument "
                  "of hasDMember or of a member selector [§10.3]")
                return
            if isinstance(n, Bin):
                e0410(n.l, "arithmetic"); e0410(n.r, "arithmetic")
                go(n.l, mode, filters); go(n.r, mode, filters); return
            if isinstance(n, Neg):
                e0410(n.x, "arithmetic"); go(n.x, mode, filters); return
            fn, args = n.f, n.args
            if fn in FUNCS:
                lo, hi = FUNCS[fn]
                if len(args) < lo or (hi is not None and len(args) > hi):
                    want = f"{lo}" if lo == hi else (f"at least {lo}" if hi is None else f"{lo} to {hi}")
                    r(n.line, n.col, "FML-E0406", f"{n.fname}() takes {want} argument{'s' if (hi or lo) != 1 else ''}, "
                      f"found {len(args)} [§12]")
            else:
                r(n.line, n.col, "FML-I0408", f"{n.fname}() is not a function of §12 (an extension; preserved) [EXT-2]")
            if fn in TIME_SERIES and not any(d in self.time_dims for d in v.free):
                r(n.line, n.col, "FML-E0407", f"{n.fname}() runs along a time dimension, and the grain of {v.name!r} "
                  f"has none [FUN-6]")
            if fn in CONTEXT_REQUIRES:
                need = CONTEXT_REQUIRES[fn]
                if not any(g.dim in need for g in v.grain):      # free or pinned: a pin fixes the context's period
                    r(n.line, n.col, "FML-E0407", f"{n.fname}() reads its period from {' or '.join(need)}, which the "
                      f"grain of {v.name!r} does not carry; a dimension declared @semantic time does not "
                      f"count [FUN-8]")
            if fn in COMPARISONS:
                for a in args:
                    e0410(a, "a comparison")
            if fn == "if":
                if args:
                    go(args[0], "cond", filters)
                for a in args[1:]:
                    go(a, mode, filters)
            elif fn == "hasdmember":
                for a in args:
                    self.member_arg(a, "hasDMember", path)
            elif fn == "sum":
                fdims = set()
                for a in args[1:]:
                    fdims |= self.member_arg(a, "sum", path)
                if args:
                    go(args[0], mode, filters | fdims)
            elif fn in SELECTORS:
                for a in args:
                    if isinstance(a, MRef):
                        self.check_mref(a, "selector", path)
                    else:
                        go(a, mode, filters)
            elif fn in ("delay", "spread", "avg"):
                if args:
                    go(args[0], mode, filters)
                for a in args[1:]:
                    go(a, "other", filters)
            elif fn in FUNCS:
                for a in args:
                    go(a, mode, filters)
            else:                                        # an extension: members pass through, the rest is value
                for a in args:
                    if isinstance(a, MRef):
                        self.check_mref(a, "extension", path)
                    else:
                        go(a, mode, filters)

        go(f, "value", frozenset())
        vnames = {x.name for x in self.value_refs}
        allnames = vnames | {x.name for x in self.other_refs}

        # sparsity (§11.3, Guide §5)
        ifs = [x for x in walk(f) if isinstance(x, Call) and x.f == "if" and 2 <= len(x.args) <= 3]
        if not vnames:
            w1008 = None
            for x in ifs:
                branch_refs = [y for b in x.args[1:] for y in refs(b)]
                cond_vars = {y.name for y in refs(x.args[0])}
                if not branch_refs and len(cond_vars) >= 2:
                    w1008 = x; break
            eval5 = (isinstance(f, Call) and f.f == "if" and 2 <= len(f.args) <= 3
                     and all(is_const(b) for b in f.args[1:]) and len({y.name for y in refs(f.args[0])}) == 1)
            if w1008 is not None:
                r(w1008.line, w1008.col, "FML-W1006", "literal output of an if whose condition names two or more "
                  "variables: the formula creates no cells; return a carrier instead [EVAL-5], [SPARSE-3]")
            elif not eval5:
                r(v.fline, v.fcol, "FML-W1001", "the formula has only literals and context functions in value "
                  "position, so it creates no cells [EVAL-4]")
        for x in ifs:
            cond_has_hv = any(isinstance(y, Call) and y.f == "hasvalue" for y in walk(x.args[0]))
            if cond_has_hv and len(x.args) == 3 and is_const(x.args[1]) != is_const(x.args[2]):
                r(x.line, x.col, "FML-W1005", "a default taken through hasValue never widens the cells: the literal "
                  "appears only where another operand anchors a cell [EVAL-4] consequence 2")
            elif len(x.args) == 3 and is_const(x.args[2]):
                r(x.args[2].line, x.args[2].col, "FML-W1002", "if with a constant else-branch writes that constant "
                  "into every cell where the condition is false; use the two-argument if [FUN-3]")
        for x in walk(f):
            if isinstance(x, Call) and x.f == "sum" and len(x.args) == 1 and isinstance(x.args[0], Ref):
                r(x.line, x.col, "FML-I1003", f"sum({x.args[0].name!r}) without a filter is redundant: the projection "
                  f"already aggregates; write the reference alone [FUN-1]")
        if getattr(v, "eff_nf_type", None) == "PERCENTAGE":
            for x in walk(f):
                if isinstance(x, Bin) and x.op == "*" and any(isinstance(s, Num) and s.value == 100 for s in (x.l, x.r)):
                    r(x.line, x.col, "FML-W1402", "a percentage variable holds the ratio; the formula must not "
                      "multiply by 100 [PROP-7]")
        # members named in the formula
        for (mr, role) in self.mrefs:
            if mr.dim == "Versions" and mr.member != "Actual":
                r(mr.line, mr.col, "FML-W1301", f"formula names the version {mr.member!r}; route versions with "
                  f"data (forecast flags), naming only Versions > Actual [TIME-3]")
            if role == "hasDMember" and mr.member == f"NULL ({mr.dim})" and mr.dim not in v.dims:
                r(mr.line, mr.col, "FML-W1303", f"test against the NULL member of {mr.dim} through a parent changes "
                  f"meaning as keys are populated; test positively for the rows that should compute [EVAL-17]")
        if any(n not in self.vars for n in allnames):
            return                                       # grain checks need every operand's grain
        g = self.graph
        # W1105: own-grain and through-parent filters in one formula [EVAL-23]
        own, across = set(), set()
        for (mr, role) in self.mrefs:
            if role != "sum":
                continue
            if mr.dim in v.free:
                own.add(mr.dim)
            elif mr.dim not in v.dims and any(g.reach(d, mr.dim) for d in v.dims):
                across.add(mr.dim)
        if own and across:
            r(v.fline, v.fcol, "FML-W1105", f"own-grain filter ({', '.join(sorted(own))}) and through-parent filter "
              f"({', '.join(sorted(across))}) in one formula: the own-grain term repeats once per member the "
              f"through-parent terms reach [EVAL-23]")
        # W1104: a pin writes, it does not read [EVAL-18]
        for d, _m in v.pins.items():
            for ref, fdims in self.vref_filters:
                src = self.vars[ref.name]
                carries = any(x == d or g.reach(x, d) for x in src.free)   # a pinned operand holds one member
                if carries and not any(g.connected(fd, d) for fd in fdims):
                    r(ref.line, ref.col, "FML-W1104", f"{v.name!r} is pinned on {d}, and {ref.name!r} carries {d}: "
                      f"it is read over all members of {d}; filter it explicitly [EVAL-18]")
                    break
        # W1107: a read that aggregates across a dimension declared @rollup none [DIM-13]
        for ref, fdims in self.vref_filters + [(x, frozenset()) for x in self.other_refs]:
            for d in self.vars[ref.name].free:
                if d in self.rollup_none and d not in v.dims and d not in fdims:
                    r(ref.line, ref.col, "FML-W1107", f"{ref.name!r} is read across {d}, which is declared @rollup none: "
                      f"the read aggregates its members and is null; keep {d} in the grain or filter one member "
                      f"[DIM-13]")
                    break
        full = lambda name: set(v.dims) <= set(self.vars[name].dims)
        # W1102: a coarse operand as the only source of a value beside a full-grain one [EVAL-4a]
        for x in walk(f):
            if isinstance(x, Call) and x.f == "if" and len(x.args) == 3:
                a1, a2 = x.args[1], x.args[2]
                if isinstance(a1, Ref) and isinstance(a2, Ref) and full(a1.name) != full(a2.name):
                    coarse = a2 if full(a1.name) else a1
                    r(coarse.line, coarse.col, "FML-W1102", f"{coarse.name!r} lacks a dimension of the output grain "
                      f"and is a whole branch beside a full-grain branch: it has values only where the full-grain "
                      f"operand anchors cells; project it to the output grain first [EVAL-4a], [EVAL-12]")
        # W1103: a product of misaligned operands inside sum [EVAL-8]
        for x in walk(f):
            if isinstance(x, Call) and x.f == "sum" and x.args and isinstance(x.args[0], Bin) and x.args[0].op in "*/":
                factors, stack = [], [x.args[0]]
                while stack:
                    y = stack.pop()
                    if isinstance(y, Bin) and y.op in "*/":
                        stack += [y.l, y.r]
                    elif isinstance(y, Ref):
                        factors.append(y)
                grains = {frozenset(self.vars[y.name].dims) for y in factors}
                if len(grains) > 1:
                    r(x.line, x.col, "FML-W1103", "a product of operands at different grains inside sum: each operand "
                      "is aggregated first and the aggregates are multiplied; compute the product at the finer "
                      "grain in its own variable [EVAL-8]")
        # W1007: `0 + X` lift through a parent
        for x in walk(f):
            if isinstance(x, Bin) and x.op == "+":
                for zero, other in ((x.l, x.r), (x.r, x.l)):
                    if isinstance(zero, Num) and zero.value == 0 and isinstance(other, Ref):
                        src = self.vars[other.name]
                        if any(p not in v.dims and any(g.reach(c, p) for c in v.dims) for p in src.dims):
                            r(x.line, x.col, "FML-W1007", f"`0 + {other.name}` lifts through a parent and writes 0 on every "
                              f"child without data; write if(hasValue(X), X) [Guide §5.2]")
        # W1101: orphan dimension in the output grain [GRAIN-1]
        if allnames:
            for d in v.free:
                if d == "Versions":
                    continue                             # a version-free operand read by every version is intended [TIME-2]
                ok = any(x == d or g.reach(x, d) or g.reach(d, x) for n in allnames for x in self.vars[n].dims)
                if not ok:
                    r(v.line, v.col, "FML-W1101", f"orphan dimension {d}: no operand carries or reaches it, so every "
                      f"operand is broadcast over it [GRAIN-1]")

    def member_arg(self, a, fn, path):
        """A filter of sum or an argument of hasDMember. Returns the dimensions it names."""
        if isinstance(a, MRef):
            self.check_mref(a, fn, path)
            return {a.dim}
        if isinstance(a, Call) and a.f in SELECTORS:
            out = set()
            for x in a.args:
                out |= self.member_arg(x, fn, path)
            lo, hi = FUNCS[a.f]
            if len(a.args) < lo or (hi is not None and len(a.args) > hi):
                self.r(path, a.line, a.col, "FML-E0406", f"{a.fname}() takes {lo if lo == hi else f'at least {lo}'} "
                       f"argument{'s' if lo != 1 else ''}, found {len(a.args)} [§12]")
            return out
        where = "a sum filter" if fn == "sum" else "an argument of hasDMember"
        if isinstance(a, Ref):
            if a.name in self.vars:
                self.r(path, a.line, a.col, "FML-E0404", f"variable {a.name!r} passed as {where}: a filter is a "
                       f"member reference, not a condition [EVAL-20]")
            elif a.name in self.known_dims:
                self.r(path, a.line, a.col, "FML-E0405", f"dimension {a.name!r} passed as {where}: name a member, "
                       f"{a.name} > Member [EVAL-20]")
            else:
                dims = [d for d, ms in self.members.items() if a.name in ms]
                hint = f" (a member of {', '.join(sorted(dims))})" if dims else ""
                self.r(path, a.line, a.col, "FML-W0403", f"unqualified member reference {a.name!r}{hint}; write "
                       f"Dimension > {a.name} [EXPR-8]")
                unlisted = any(d.source is None for n, d in self.decls.items() if n not in self.declared_time)
                if not dims and self.complete and not unlisted:
                    self.r(path, a.line, a.col, "FML-E0302", f"{a.name!r} is not a member of any dimension "
                           f"(membersComplete) [§5.7]")
            return set()
        self.r(path, a.line, a.col, "FML-E0404", f"{where} must be a member reference or a selector over member "
               f"references, not a condition or a value [EVAL-20]")
        return set()

    def check_mref(self, mr, role, path):
        self.mrefs.append((mr, role))
        if mr.pinform:
            return
        if has_control(mr.dim):
            self.r(path, mr.line, mr.col, "FML-E0205", f"dimension name {mr.dim!r} contains a control character [LEX-3]")
        if mr.dim in self.vars and mr.dim not in self.known_dims:
            self.r(path, mr.line, mr.col, "FML-E0303", f"{mr.dim!r} is a variable, not a dimension; `>` qualifies a "
                   f"member by its dimension [§10.4]")
            return
        if mr.dim not in self.known_dims:
            self.r(path, mr.line, mr.col, "FML-E0208", f"{mr.dim!r} in a member reference is neither declared nor a "
                   f"system dimension; a reference never creates a dimension [DOC-6]")
            return
        self.check_member_ref(path, mr.mline, mr.mcol, mr.dim, mr.member)

    # -- naming (Guide §2)
    def check_naming(self, v, props):
        r = lambda code, msg: self.r(v.path, v.line, v.col, code, msg)
        n = v.name
        ro = props.get("readonly")
        readonly = ro is not None and ro.kind == "bool" and ro.value is True
        folder = props.get("folder")
        top = folder.value.split("/")[0].strip() if folder is not None and folder.kind == "string" and folder.value else ""
        if is_import(n) and v.has_formula:
            r("FML-W1201", "IMPORT is reserved for direct landing targets; a variable with a formula is a calculation "
              "[NAME-1]")
        elif not is_import(n) and not v.has_formula and top == "Import" and not is_in(n):
            r("FML-W1201", "a formula-less variable in the Import folder is an import and carries the IMPORT prefix "
              "[NAME-1]")
        if re.search(r" IN |_IN_", n):
            r("FML-W1202", "the IN suffix is the last token of the name [NAME-2]")
        elif not v.has_formula and not readonly and not is_import(n) and not is_in(n) and not is_out(n):
            r("FML-W1202", "a planner input (no formula, not read-only) ends in the suffix ` IN` [NAME-2]")
        if is_out(n) and not v.has_formula:
            r("FML-W1203", "OUT marks a computed output; a variable without a formula is an input, never an output "
              "[NAME-3], [ARCH-3]")
        if not is_in(n) and not readonly:
            r("FML-W1204", "a variable whose name does not end in ` IN` is @readonly true [NAME-4], [PROP-8]")
        desc = props.get("desc")
        if desc is not None and desc.kind == "string" and desc.value != "":
            self.r(v.path, desc.line, desc.col, "FML-I1206", "@desc is a display label shown in place of the name; "
                   "prose belongs in @notes [NAME-6], [PROP-11]")
        if is_in(n) and v.has_formula:
            f = v.formula
            fenced = isinstance(f, Call) and f.f == "if" and len(f.args) == 2
            if not fenced:
                r("FML-W1207", "a formula on an input variable other than a fenced seed `if(condition, value)` [ARCH-3]")
        notes = props.get("notes")
        if (not v.has_formula or is_in(n) or is_out(n)) and not (notes is not None and notes.kind == "string" and notes.value.strip()):
            r("FML-I1208", "input or output variable without @notes (who writes it, who reads it) [NAME-6]")
        ru = props.get("rollup")
        rollup = norm_rollup(ru.value) if ru is not None and ru.kind == "ident" else "sum"
        if rollup == "sum" and self.balance_like(n, notes.value if notes is not None and notes.kind == "string" else ""):
            r("FML-W1004", "balance-like variable with @rollup sum: twelve monthly balances summed are not a balance; "
              "use @rollup closing_state [TIME-1]")
        if is_import(n) and "Versions" in v.dims:
            r("FML-W1302", "an import carries no Versions: an actual is a fact, broadcast to every version that "
              "reads it [TIME-2]")

    @staticmethod
    def balance_like(name, notes):
        low = name.lower().replace("_", " ")
        if re.search(r"\b(movement|movements|change|changes|delta|flow|flows|check)\b", low):
            return False
        if re.search(r"\bbalances?\b(?![ -]sheet)", low):
            return True
        return bool(re.search(r"\b(a|the|closing|opening|period-end|end-of-period) balance\b(?![ -]sheet)",
                              notes.lower()))

    # ------------------------------------------------------------------ model-wide
    def check_dependency_cycles(self):
        edges = {}
        for n, v in self.vars.items():
            if v.formula is not None:
                edges[n] = {x.name for x in walk(v.formula) if isinstance(x, Ref) and x.name in self.vars}
        for comp in sccs(list(self.vars), edges):
            if len(comp) > 1 or comp[0] in edges.get(comp[0], ()):
                names = sorted(comp)
                for n in names:
                    v = self.vars[n]
                    what = "references itself" if len(comp) == 1 else f"is in a dependency cycle with {', '.join(repr(x) for x in names if x != n)}"
                    self.r(v.path, v.line, v.col, "FML-E0501", f"{n!r} {what}; express a recurrence with cumsum [EVAL-29]")

    def check_styles(self):
        a, b = [], []
        for v in self.vars.values():
            n = v.name
            if " " in n and "_" in n:
                self.r(v.path, v.line, v.col, "FML-W1205", f"{n!r} mixes spaces and underscores [NAME-5]")
            elif " " in n:
                a.append(v)
            elif "_" in n.strip("_"):
                b.append(v)
        if a and b:
            minority, style = (b, "B (underscores)") if len(b) <= len(a) else (a, "A (spaces)")
            for v in minority:
                self.r(v.path, v.line, v.col, "FML-W1205", f"{v.name!r} uses word-separator style {style}, the rest "
                       f"of the model the other style [NAME-5]")


def check(model, sink):
    Checker(model, sink).run()
