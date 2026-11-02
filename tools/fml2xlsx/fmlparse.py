"""fmlparse.py — a small parser for FML documents (spec/fml-1.0.md §4–§9, Annex A).

parse_document(text) -> {"dimensions": [...], "variables": [...]}.

Each dimension declaration (§6.1) is {"name", "source": None | "inline" | "file", "members": [...] (inline),
"file"? (the `from` path), "parents": [{"dimension", "many", "required"}], "attributes": [{"name", "type"}],
"null", "time" (@semantic time, §6.9), "properties": {key: value}} for the other properties.
Each variable is {"name", "grain": [{"dimension", "pinnedMember"?}], "formula"?,
"properties": [{"key", "value": {"value"}}]}. A defaults block applies to the variables below it
in its own document, until the next block replaces it (PROP-3, DOC-3).
"""
import re

TOKEN = re.compile(r'''
    (?P<ws>[ \t]+)
  | (?P<comment>\#.*|//.*)
  | (?P<string>"(?:\\.|[^"\\])*")
  | (?P<number>-?\d+(?:\.\d+)?)
  | (?P<ident>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<punct>[{}(),=:@>])
  | (?P<op>[+\-*/])
  | (?P<other>.)
''', re.X)


class ParseError(Exception):
    pass


def tokenize(text):
    """Tokens per line: list of (kind, value, raw) plus a ('nl', None, '\\n') at each line end."""
    out = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for m in TOKEN.finditer(line):
            k = m.lastgroup; v = m.group(0)
            if k in ("ws", "comment"): continue
            if k == "string": v = unescape(v[1:-1])
            if k == "other": raise ParseError(f"line {lineno}: unexpected character {v!r}")
            out.append((k, v, m.group(0), lineno))
        out.append(("nl", None, "\n", lineno))
    out.append(("eof", None, "", len(text.splitlines()) + 1))
    return out


def unescape(s):
    res, i = "", 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            c = s[i + 1]
            res += {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"'}.get(c, "\\" + c); i += 2
        else:
            res += s[i]; i += 1
    return res


class Cursor:
    def __init__(self, toks): self.t, self.i = toks, 0
    def peek(self, k=0): return self.t[min(self.i + k, len(self.t) - 1)]
    def next(self): tok = self.peek(); self.i += 1; return tok
    def skip_nl(self):
        while self.peek()[0] == "nl": self.i += 1
    def peek_past_nl(self, k=0):
        j = self.i
        while self.t[j][0] == "nl": j += 1
        return self.t[min(j + k, len(self.t) - 1)]


def parse_document(text):
    c = Cursor(tokenize(text))
    doc = {"dimensions": [], "variables": []}
    defaults = []
    c.skip_nl()
    while c.peek()[0] != "eof":
        k, v, _, ln = c.peek()
        if k == "nl": c.next(); continue
        if k == "ident" and v == "dimension" and c.peek_past_nl(1)[1] != "{":
            doc["dimensions"].append(dimension(c))                  # dimension declaration (§6.1)
            continue
        if k == "punct" and v == "@":
            if c.peek(1)[1] == "defaults":
                c.next(); c.next(); defaults = properties(c)
                continue
            raise ParseError(f"line {ln}: property outside a variable declaration")
        if k in ("ident", "string"):
            var = variable(c)
            have = {p["key"] for p in var["properties"]}
            var["properties"] = var["properties"] + [p for p in defaults if p["key"] not in have]
            doc["variables"].append(var)
            continue
        raise ParseError(f"line {ln}: unexpected {v!r} at top level")
    return doc


def name(c):
    k, v, _, ln = c.next()
    if k not in ("ident", "string"): raise ParseError(f"line {ln}: expected a name, found {v!r}")
    return v


def expect(c, kind, value=None):
    k, v, _, ln = c.next()
    if k != kind or (value is not None and v != value): raise ParseError(f"line {ln}: expected {value or kind}, found {v!r}")


def dimension(c):
    c.next(); ln = c.peek()[3]
    d = {"name": name(c), "source": None, "members": [], "parents": [], "attributes": [], "null": False,
         "time": False, "properties": {}}
    if c.peek()[1] == "{":                                     # inline members, across lines (§4.9)
        c.next(); d["source"] = "inline"
        c.skip_nl()
        while c.peek()[1] != "}":
            d["members"].append(name(c)); c.skip_nl()
            if c.peek()[1] == ",": c.next(); c.skip_nl()
        c.next()
    elif c.peek()[:2] == ("ident", "from"):
        c.next(); k, v, _, _ = c.next()
        if k != "string": raise ParseError(f"line {ln}: expected the path of a member file after `from`")
        d["source"], d["file"] = "file", v
    if c.peek()[0] not in ("nl", "eof"): raise ParseError(f"line {ln}: expected the end of the declaration of {d['name']}")
    for key, vals in dimension_properties(c):
        if key == "parent":
            d["parents"] = [p for p in d["parents"] if p["dimension"] != vals[0]]     # the last one applies (PARENT-4)
            d["parents"].append({"dimension": vals[0], "many": "many" in vals[1:], "required": "required" in vals[1:]})
        elif key == "attribute": d["attributes"].append({"name": vals[0], "type": vals[1] if len(vals) > 1 else None})
        elif key == "null": d["null"] = True
        elif key == "semantic": d["time"] = vals[0] == "time"
        else: d["properties"][key] = vals[0] if vals else None
    return d


def dimension_properties(c):
    """Property lines of a dimension declaration (DIM-13): (key, [values]). @null has no value; @parent and
    @attribute take a name followed by words (`many`, `required`, a type)."""
    out = []
    while True:
        j = c.i
        while c.t[j][0] == "nl": j += 1
        if not (c.t[j][0] == "punct" and c.t[j][1] == "@"): return out
        c.i = j; c.next()
        key = c.next()[1]; vals = []
        while c.peek()[0] not in ("nl", "eof"):
            k, v, _, ln = c.next()
            if k not in ("ident", "string", "number"): raise ParseError(f"line {ln}: unexpected {v!r} in @{key}")
            vals.append(v)
        out.append((key, vals))


def variable(c):
    nm = name(c)
    if c.peek_past_nl()[1] == "{": c.skip_nl()
    expect(c, "punct", "{")
    grain = []
    c.skip_nl()
    while c.peek()[1] != "}":
        d = name(c); entry = {"dimension": d}
        if c.peek()[1] == "=":
            c.next(); entry["pinnedMember"] = c.next()[1]
        grain.append(entry)
        if c.peek()[1] == ",": c.next()
        c.skip_nl()
    c.next()                                                   # }
    var = {"name": nm, "grain": grain, "properties": []}
    if c.peek_past_nl()[1] == "=" and c.peek()[1] != "@": c.skip_nl()
    if c.peek()[1] == "=":
        c.next(); var["formula"] = formula(c)
    var["properties"] = properties(c)
    return var


def starts_construct(c, j):
    """Does the logical line starting at token j begin a property, a dimension declaration or a
    variable header (LEX-6)?"""
    k, v = c.t[j][0], c.t[j][1]
    if k == "eof" or (k == "punct" and v == "@") or (k == "ident" and v == "dimension"): return True
    if k in ("ident", "string"):
        m = j + 1
        while c.t[m][0] == "nl": m += 1
        return c.t[m][1] == "{"
    return False


def formula(c):
    parts, depth, last = [], 0, None
    while c.peek()[0] == "nl": c.next()
    while True:
        k, v, raw, ln = c.peek()
        if k == "eof": break
        if k == "nl":
            if depth > 0: c.next(); continue
            j = c.i
            while c.t[j][0] == "nl": j += 1
            if starts_construct(c, j): break
            if last == "op" or c.t[j][0] == "op":
                c.i = j; continue
            break
        if v == "(": depth += 1
        if v == ")": depth -= 1
        if depth < 0: raise ParseError(f"line {ln}: unmatched ')'")
        parts.append(raw); last = k; c.next()
    if depth != 0: raise ParseError("unbalanced parentheses in formula")
    return " ".join(parts)


def properties(c):
    props = []
    while True:
        j = c.i
        while c.t[j][0] == "nl": j += 1
        if not (c.t[j][0] == "punct" and c.t[j][1] == "@") or c.t[j + 1][1] == "defaults": return props
        c.i = j; c.next()
        key = c.next()[1]
        props.append({"key": key, "value": {"value": value(c)}})


def value(c):
    k, v, raw, ln = c.next()
    if k == "string": return v
    if k == "number": return float(v) if "." in v else int(v)
    if k == "ident":
        if v in ("true", "false"): return v == "true"
        if c.peek()[1] == "(":
            depth, parts = 0, [v]
            while True:
                t = c.next(); parts.append(t[2])
                depth += t[1] == "("; depth -= t[1] == ")"
                if depth == 0: break
            return "".join(parts)
        return v
    if v == "{":
        obj = {}
        while True:
            c.skip_nl()
            if c.peek()[1] == "}": c.next(); return obj
            key = c.next()[1]; expect(c, "punct", ":")
            obj[key] = value(c)
            if c.peek()[1] == ",": c.next()
    raise ParseError(f"line {ln}: expected a property value, found {v!r}")
