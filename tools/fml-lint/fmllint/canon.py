"""Canonical form (FML 1.0 §5.6) and information content (§5.5, [DOC-4])."""
from .checks import STANDARD_PROPS
from .syntax import Bin, Call, MRef, Neg, Num, Ref, name_repr, quote

# §9.3 defaults; a property equal to its default is omitted (§5.6 item 5). @folder has no
# default to omit: its absence is not the root [PROP-10].
DEFAULTS = {"type": ("ident", "number"), "rollup": ("ident", "sum"), "format": ("ident", "number"),
            "decimals": ("number", "2"), "readonly": ("bool", False), "desc": ("string", ""),
            "notes": ("string", "")}

_PREC = {"+": 1, "-": 1, "*": 2, "/": 2}


def expr(n):
    """A formula on one line, spaced per §5.6 item 7."""
    if isinstance(n, Num):
        return n.lexeme
    if isinstance(n, Ref):
        return name_repr(n.name)
    if isinstance(n, MRef):
        return f"{name_repr(n.dim)} > {name_repr(n.member)}"
    if isinstance(n, Call):
        return f"{n.fname}({', '.join(expr(a) for a in n.args)})"
    if isinstance(n, Neg):
        inner = expr(n.x)
        return "-" + (f"({inner})" if isinstance(n.x, Bin) else inner)
    if isinstance(n, Bin):
        p = _PREC[n.op]
        left, right = expr(n.l), expr(n.r)
        if isinstance(n.l, Bin) and _PREC[n.l.op] < p:
            left = f"({left})"
        if isinstance(n.r, Bin) and _PREC[n.r.op] <= p:
            right = f"({right})"                         # keep the tree: A - (B - C), A / (B * C)
        return f"{left} {n.op} {right}"
    raise TypeError(n)


def value_text(p):
    if p.kind == "string":
        return quote(p.value)
    if p.kind == "number":
        return p.value
    if p.kind == "bool":
        return "true" if p.value else "false"
    if p.kind == "ident":
        return p.value
    if p.kind == "call":
        return p.raw
    if p.kind == "words":
        return " ".join([name_repr(p.value[0])] + p.value[1])
    if p.kind == "object":
        parts = []
        for k, kind, val, raw in p.value:
            key = k if name_repr(k) == k else quote(k)
            if kind == "string":
                vt = quote(val)
            elif kind == "bool":
                vt = "true" if val else "false"
            else:
                vt = val
            parts.append(f"{key}: {vt}")
        return "{ " + ", ".join(parts) + " }"
    return p.raw


def is_default(p):
    d = DEFAULTS.get(p.key)
    return d is not None and (p.kind, p.value) == d


def prop_order(key):
    if key in STANDARD_PROPS:
        return (0, STANDARD_PROPS.index(key), "")
    return (1, 0, key)


def grain_text(v):
    if not v.grain:
        return "{ }"
    parts = []
    for g in v.grain:
        parts.append(name_repr(g.dim) + (f" = {name_repr(g.pin)}" if g.pin is not None else ""))
    return "{ " + ", ".join(parts) + " }"


# §5.6 item 1. @null is not in the order the item gives; it is placed after @attribute.
DIM_PROP_ORDER = ["semantic", "rollup", "parent", "attribute", "null", "folder", "desc"]


def dim_props(d):
    """The properties of a dimension declaration as information content (§5.5): one @parent per parent
    dimension (duplicates are rejected by the parser, PARENT-4), one @attribute per name in source order,
    the last occurrence of any other property (PROP-2)."""
    parents, attrs, other = {}, {}, {}
    for p in d.props:
        if p.kind == "invalid":
            continue
        if p.key == "parent" and p.kind in ("ident", "string", "words"):
            name, words = (p.value, []) if p.kind != "words" else p.value
            parents[name] = tuple(sorted(set(words), key=lambda w: (w != "many", w)))
        elif p.key == "attribute" and p.kind == "words":
            attrs[p.value[0]] = tuple(p.value[1])
        else:
            other[p.key] = p
    return parents, attrs, other


def dim_text(d):
    head = f"dimension {name_repr(d.name)}"
    if d.source == "inline":
        head += " { " + ", ".join(name_repr(m) for m, _, _ in d.members) + " }" if d.members else " { }"
    elif d.source == "file":
        head += f" from {quote(d.file)}"
    lines = [head]
    parents, attrs, other = dim_props(d)

    def order(key):
        return (0, DIM_PROP_ORDER.index(key), "") if key in DIM_PROP_ORDER else (1, 0, key)
    keys = set(other) | ({"parent"} if parents else set()) | ({"attribute"} if attrs else set())
    for key in sorted(keys, key=order):
        if key == "parent":
            for name in sorted(parents):
                lines.append("  @parent " + " ".join([name_repr(name)] + list(parents[name])))
        elif key == "attribute":
            for name, rest in attrs.items():
                lines.append("  @attribute " + " ".join([name_repr(name)] + list(rest)))
        elif other[key].kind == "none":
            lines.append(f"  @{key}")
        else:
            lines.append(f"  @{key} {value_text(other[key])}")
    return lines


def emit(doc):
    """The canonical form of a parsed document (§5.6)."""
    out = []
    dims = {}
    for d in doc.dimensions:
        dims.setdefault(d.name, d)                       # a second declaration is FML-E0209
    if dims:
        out.append("# --- Dimensions ---")
        for name in sorted(dims):
            out += dim_text(dims[name])
    if doc.variables:
        if out:
            out.append("")
        out.append("# --- Variables ---")
        for i, v in enumerate(sorted(doc.variables, key=lambda v: v.name)):
            if i:
                out.append("")
            head = f"{name_repr(v.name)} {grain_text(v)}"
            if v.formula is not None:
                head += " = " + expr(v.formula)
            out.append(head)
            props = v.props()
            for key in sorted(props, key=prop_order):
                p = props[key]
                if is_default(p):
                    continue
                out.append(f"  @{key} {value_text(p)}")
    return "\n".join(out) + "\n"


def ast_key(n):
    if isinstance(n, Num):
        return ("num", float(n.lexeme))
    if isinstance(n, Ref):
        return ("ref", n.name)
    if isinstance(n, MRef):
        return ("mref", n.dim, n.member)
    if isinstance(n, Call):
        return ("call", n.f, tuple(ast_key(a) for a in n.args))
    if isinstance(n, Neg):
        return ("neg", ast_key(n.x))
    if isinstance(n, Bin):
        return ("bin", n.op, ast_key(n.l), ast_key(n.r))
    return None


def prop_key(p):
    if p.kind == "number":
        return ("number", float(p.value))
    if p.kind == "words":
        return ("words", p.value[0], tuple(p.value[1]))
    if p.kind == "object":
        return ("object", tuple(sorted((k, kind, float(val) if kind == "number" else val) for k, kind, val, _ in p.value)))
    return (p.kind, p.value if p.kind != "call" else p.raw.replace(" ", ""))


def info_content(doc):
    """§5.5: the set of dimension declarations and the set of variable declarations, defaults applied."""
    dims = {}
    for d in doc.dimensions:
        if d.name in dims:
            continue
        parents, attrs, other = dim_props(d)
        dims[d.name] = (d.source, tuple(m for m, _, _ in d.members), d.file,
                        tuple(sorted(parents.items())), tuple(attrs.items()),
                        tuple(sorted((k, prop_key(p)) for k, p in other.items())))
    variables = {}
    for v in doc.variables:
        props = {k: prop_key(p) for k, p in v.props().items() if not is_default(p)}
        variables[v.name] = (tuple((g.dim, g.pin) for g in v.grain),
                             ast_key(v.formula) if v.formula is not None else None,
                             tuple(sorted(props.items())))
    return dims, variables
