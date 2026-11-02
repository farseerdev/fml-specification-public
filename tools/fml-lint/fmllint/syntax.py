"""Lexer and recursive-descent parsers for FML 1.0 documents and formulas
(FML 1.0 §4, §5.1, §6.1, §8.1, §9.1–§9.2, §10.1, Annex A.2–A.4).

parse_document(text, report) -> Document
    report(line, col, code, message) receives every syntax diagnostic.
"""
import re

IDENT, STRING, NUMBER, PUNCT, OP, NL, EOF, BAD = "ident", "string", "number", "punct", "op", "nl", "eof", "bad"
RESERVED = {"dimension", "true", "false"}               # §4.5, §4.8
RETIRED = ("link", "time")                               # statements of earlier drafts (§7.1, §6.9)
IDENT_RX = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_IDENT_AT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_NUMBER_AT = re.compile(r"-?[0-9]+(?:\.[0-9]+)?")
_ESCAPES = {'"': '"', "\\": "\\", "n": "\n", "t": "\t", "r": "\r"}


class Token:
    __slots__ = ("kind", "value", "raw", "line", "col", "error")

    def __init__(self, kind, value, raw, line, col, error=False):
        self.kind, self.value, self.raw, self.line, self.col, self.error = kind, value, raw, line, col, error

    def is_p(self, v):
        return self.kind == PUNCT and self.value == v

    def is_op(self, v=None):
        return self.kind == OP and (v is None or self.value == v)

    def is_name(self):
        return self.kind in (IDENT, STRING)

    def __repr__(self):
        return f"Token({self.kind},{self.value!r},{self.line}:{self.col})"


def describe(t):
    if t.kind == NL:
        return "the end of the line"
    if t.kind == EOF:
        return "the end of the document"
    return f"`{t.raw}`"


# ----------------------------------------------------------------------------- lexer

def lex(text, report):
    """Tokens of a document, with NL tokens for line terminators and comments dropped (§4.1–§4.7)."""
    if text.startswith("﻿"):
        text = text[1:]
    toks = []
    i, n, line, ls = 0, len(text), 1, 0               # ls = index of the line's first character
    while i < n:
        c = text[i]
        col = i - ls + 1
        if c == "\n":
            toks.append(Token(NL, None, "\n", line, col)); i += 1; line += 1; ls = i; continue
        if c == "\r":
            if i + 1 < n and text[i + 1] == "\n":
                i += 1; continue                          # CR LF is one line terminator
            report(line, col, "FML-E0107", "invalid character U+000D (a carriage return not followed by a line feed)")
            toks.append(Token(BAD, c, c, line, col)); i += 1; continue
        if c in " \t":
            i += 1; continue
        if c == "#" or (c == "/" and text.startswith("//", i)):
            while i < n and text[i] != "\n":
                i += 1
            continue
        if c == '"':
            j, buf, closed = i + 1, [], False
            while j < n:
                ch = text[j]
                if ch == '"':
                    closed = True; j += 1; break
                if ch == "\n" or (ch == "\r" and j + 1 < n and text[j + 1] == "\n"):
                    break
                if ch == "\\":
                    if j + 1 >= n or text[j + 1] in "\r\n":
                        j += 1; break
                    e = text[j + 1]
                    buf.append(_ESCAPES.get(e, "\\" + e)); j += 2; continue   # LEX-4: unknown escapes keep both
                buf.append(ch); j += 1
            if not closed:
                report(line, col, "FML-E0101", "unterminated string: a string must end on the line where it begins [§4.6]")
                while j < n and text[j] != "\n" and not (text[j] == "\r" and j + 1 < n and text[j + 1] == "\n"):
                    j += 1
            toks.append(Token(STRING, "".join(buf), text[i:j], line, col, error=not closed))
            i = j; continue
        if ("0" <= c <= "9") or (c == "-" and i + 1 < n and "0" <= text[i + 1] <= "9"):
            m = _NUMBER_AT.match(text, i)                 # LEX-5: '-' followed by a digit is part of the literal
            toks.append(Token(NUMBER, m.group(0), m.group(0), line, col)); i = m.end(); continue
        if c == "_" or ("A" <= c <= "Z") or ("a" <= c <= "z"):
            m = _IDENT_AT.match(text, i)
            toks.append(Token(IDENT, m.group(0), m.group(0), line, col)); i = m.end(); continue
        if c == "-" and text.startswith("->", i):
            toks.append(Token(PUNCT, "->", "->", line, col)); i += 2; continue
        if c in "{}(),=:@>":
            toks.append(Token(PUNCT, c, c, line, col)); i += 1; continue
        if c in "+-*/":
            toks.append(Token(OP, c, c, line, col)); i += 1; continue
        hint = ""
        if c == "." and toks and toks[-1].kind == NUMBER:
            hint = " — a number has no trailing decimal point; write `5`, not `5.` [§4.7]"
        elif c == "." and i + 1 < n and text[i + 1].isdigit():
            hint = " — a number has no leading decimal point; write `0.5` [§4.7]"
        elif c in "<!&|=;[]%^'":
            hint = " — FML has no infix comparison or logical operators; use eq, gt, and, … [EXPR-3]" if c in "<!&|" else ""
        report(line, col, "FML-E0107", f"invalid character {c!r} (U+{ord(c):04X}) outside a string or comment{hint}")
        toks.append(Token(BAD, c, c, line, col)); i += 1
    toks.append(Token(EOF, None, "", line, i - ls + 1))
    return toks


# ----------------------------------------------------------------------------- formula AST

class Num:
    __slots__ = ("lexeme", "line", "col")

    def __init__(self, lexeme, line, col): self.lexeme, self.line, self.col = lexeme, line, col

    @property
    def value(self): return float(self.lexeme)


class Ref:
    __slots__ = ("name", "line", "col")

    def __init__(self, name, line, col): self.name, self.line, self.col = name, line, col


class MRef:
    __slots__ = ("dim", "member", "line", "col", "mline", "mcol", "pinform")

    def __init__(self, dim, member, line, col, mline, mcol, pinform=False):
        self.dim, self.member, self.line, self.col, self.mline, self.mcol = dim, member, line, col, mline, mcol
        self.pinform = pinform                           # written `Dim = Member` (already reported, E0401)


class Call:
    __slots__ = ("fname", "args", "line", "col")

    def __init__(self, fname, args, line, col): self.fname, self.args, self.line, self.col = fname, args, line, col

    @property
    def f(self): return self.fname.lower()              # function names are case-insensitive (§12)


class Bin:
    __slots__ = ("op", "l", "r", "line", "col")

    def __init__(self, op, l, r, line, col): self.op, self.l, self.r, self.line, self.col = op, l, r, line, col


class Neg:
    __slots__ = ("x", "line", "col")

    def __init__(self, x, line, col): self.x, self.line, self.col = x, line, col


def walk(node):
    """Every node of a formula AST, pre-order."""
    yield node
    if isinstance(node, Bin):
        yield from walk(node.l); yield from walk(node.r)
    elif isinstance(node, Neg):
        yield from walk(node.x)
    elif isinstance(node, Call):
        for a in node.args:
            yield from walk(a)


class _Stop(Exception):
    pass


class ExprParser:
    """Recursive descent over the tokens of one formula (§10.1, Annex A.4), NL tokens removed."""

    def __init__(self, toks, report):
        self.t, self.i, self.report = toks, 0, report

    def peek(self, k=0):
        j = self.i + k
        return self.t[j] if j < len(self.t) else None

    def next(self):
        tok = self.t[self.i]; self.i += 1; return tok

    def fail(self, tok, code, msg):
        if tok is None:
            last = self.t[-1]
            self.report(last.line, last.col + len(last.raw), code, msg)
        else:
            self.report(tok.line, tok.col, code, msg)
        raise _Stop()

    def unexpected(self, tok, where="in the formula"):
        if tok is None:
            self.fail(None, "FML-E0105", "expected an operand at the end of the formula")
        if tok.kind == NUMBER and tok.raw.startswith("-"):
            self.fail(tok, "FML-E0105", f"`{tok.raw}` is a negative literal [LEX-5]; write `- {tok.raw[1:]}` to subtract")
        if tok.is_p(">"):
            self.fail(tok, "FML-E0105", "`>` between two values is not FML (use gt(a, b)) [EXPR-3]; "
                      "a member reference `Dim > Member` is allowed only as a function argument [§10.3]")
        if tok.is_p("="):
            self.fail(tok, "FML-E0105", "`=` in a formula: FML has no infix comparison (use eq(a, b)) [EXPR-3]")
        if tok.is_p(")"):
            self.fail(tok, "FML-E0103", "unmatched `)` in the formula [EXPR-5]")
        self.fail(tok, "FML-E0105", f"unexpected {describe(tok)} {where}")

    def parse(self):
        try:
            node = self.expression()
            if self.peek() is not None:
                self.unexpected(self.peek())
            return node
        except _Stop:
            return None

    def expression(self):
        left = self.term()
        while self.peek() is not None and self.peek().is_op() and self.peek().value in "+-":
            op = self.next()
            left = Bin(op.value, left, self.term(), op.line, op.col)
        return left

    def term(self):
        left = self.factor()
        while self.peek() is not None and self.peek().is_op() and self.peek().value in "*/":
            op = self.next()
            left = Bin(op.value, left, self.factor(), op.line, op.col)
        return left

    def factor(self):
        t = self.peek()
        if t is None:
            self.fail(None, "FML-E0105", "expected an operand at the end of the formula")
        if t.is_op("-"):                                  # unary minus [EXPR-2]
            self.next()
            x = self.factor()
            if isinstance(x, Num) and not x.lexeme.startswith("-"):
                return Num("-" + x.lexeme, t.line, t.col)  # `- 3` and `-3` are the same constant
            return Neg(x, t.line, t.col)
        if t.kind == NUMBER:
            self.next(); return Num(t.raw, t.line, t.col)
        if t.is_p("("):
            self.next()
            e = self.expression()
            c = self.peek()
            if c is None or not c.is_p(")"):
                if c is None:
                    self.fail(t, "FML-E0103", "`(` is not closed [EXPR-5]")
                self.unexpected(c, "inside parentheses; expected `)`")
            self.next()
            return e
        if t.kind == IDENT and self.peek(1) is not None and self.peek(1).is_p("("):
            return self.call()
        if t.is_name():
            self.next()
            self.check_reserved(t)
            nt = self.peek()
            if nt is not None and nt.is_p("=") and self.peek(1) is not None and self.peek(1).kind in (IDENT, STRING, NUMBER):
                self.fail(nt, "FML-E0401", "`Dim = Member` is grain syntax and must not appear in a formula; "
                          "read one member with sum(X, Dim > Member) [VAR-6]")
            if nt is not None and nt.is_p("{"):
                self.fail(nt, "FML-E0401", "`Var { Dim = Member }` is not a formula operand [EXPR-9]; use sum(Var, Dim > Member)")
            return Ref(t.value, t.line, t.col)
        self.unexpected(t, "where an operand is expected")

    def check_reserved(self, t):
        if t.kind == IDENT and t.value in RESERVED:
            self.fail(t, "FML-E0105", f"`{t.value}` is a reserved word; a variable with this name is written in string form [§4.5]")

    def call(self):
        name = self.next(); self.next()
        args = []
        if self.peek() is not None and self.peek().is_p(")"):
            self.next(); return Call(name.value, args, name.line, name.col)
        while True:
            args.append(self.argument())
            c = self.peek()
            if c is not None and c.is_p(","):
                self.next(); continue
            if c is not None and c.is_p(")"):
                self.next(); break
            if c is None:
                self.fail(name, "FML-E0103", f"`(` of {name.value}( is not closed [EXPR-5]")
            self.unexpected(c, f"in the arguments of {name.value}(); expected `,` or `)`")
        return Call(name.value, args, name.line, name.col)

    def argument(self):
        t, t1, t2 = self.peek(), self.peek(1), self.peek(2)
        if t is not None and t.is_name() and t1 is not None and t1.is_p(">"):
            self.next(); self.next()
            m = self.peek()
            if m is None or not m.is_name():
                if m is not None and m.kind == NUMBER:
                    self.fail(m, "FML-E0105", f"a member name that is not an identifier is written in string form: "
                              f"{t.raw} > \"{m.raw}\" [LEX-1]")
                self.fail(m, "FML-E0105", "expected a member name after `>`")
            self.next()
            nt = self.peek()
            if nt is not None and not (nt.is_p(",") or nt.is_p(")")):
                self.fail(nt, "FML-E0105", "a member reference is a whole argument, not an operand of arithmetic [§10.3]")
            return MRef(t.value, m.value, t.line, t.col, m.line, m.col)
        if (t is not None and t.is_name() and t1 is not None and t1.is_p("=")
                and t2 is not None and t2.kind in (IDENT, STRING, NUMBER)):
            self.report(t1.line, t1.col, "FML-E0401", "`Dim = Member` is grain syntax and must not appear in a formula; "
                        f"write {t.raw} > {t2.raw if t2.kind != NUMBER else chr(34) + t2.raw + chr(34)} [VAR-6]")
            self.next(); self.next(); self.next()
            return MRef(t.value, t2.value, t.line, t.col, t2.line, t2.col, pinform=True)
        e = self.expression()
        nt = self.peek()
        if nt is not None and nt.is_p(">"):
            self.unexpected(nt)
        return e


def parse_formula_tokens(toks, report):
    """Check parentheses [EXPR-5], then parse. Returns the AST or None (diagnostics reported)."""
    if not toks:
        return None
    if any(t.kind == BAD or t.error for t in toks):
        return None                                      # E0107 / E0101 already reported
    depth, opens = 0, []
    for t in toks:
        if t.is_p("("):
            depth += 1; opens.append(t)
        elif t.is_p(")"):
            if depth == 0:
                report(t.line, t.col, "FML-E0103", "unmatched `)` in the formula [EXPR-5]")
                return None
            depth -= 1; opens.pop()
    if depth:
        o = opens[-1]
        report(o.line, o.col, "FML-E0103", "`(` is not closed before the end of the formula [EXPR-5]")
        return None
    return ExprParser(toks, report).parse()


def parse_formula(text, report):
    """Parse a formula given as text (one or more lines; continuation is free inside a formula string)."""
    toks = [t for t in lex(text, report) if t.kind not in (NL, EOF)]
    return parse_formula_tokens(toks, report)


# ----------------------------------------------------------------------------- document model

class Prop:
    """A property line. kind: string | number | bool | ident | call | object | words | none | invalid.
    `words` is `name identifier { identifier }` (@parent, @attribute): value = (name, [identifier, …]).
    `none` is a property without a value (@null)."""
    __slots__ = ("key", "kind", "value", "raw", "line", "col", "vline", "vcol", "origin")

    def __init__(self, key, kind, value, raw, line, col, vline, vcol, origin="own"):
        self.key, self.kind, self.value, self.raw = key, kind, value, raw
        self.line, self.col, self.vline, self.vcol, self.origin = line, col, vline, vcol, origin


class GrainEntry:
    __slots__ = ("dim", "line", "col", "pin", "pline", "pcol")

    def __init__(self, dim, line, col, pin=None, pline=None, pcol=None):
        self.dim, self.line, self.col, self.pin, self.pline, self.pcol = dim, line, col, pin, pline, pcol


class Variable:
    def __init__(self, name, line, col, path):
        self.name, self.line, self.col, self.path = name, line, col, path
        self.grain = []
        self.has_formula = False
        self.formula = None                              # AST, or None when absent or unparsable
        self.formula_ok = True
        self.fline = self.fcol = None
        self.own = []                                    # Prop, in source order
        self.inherited = []                              # Prop from the active defaults block
        self.broken = False                              # a syntax error in the declaration

    # -- grain helpers
    @property
    def dims(self): return [g.dim for g in self.grain]

    @property
    def free(self): return [g.dim for g in self.grain if g.pin is None]

    @property
    def pins(self): return {g.dim: g.pin for g in self.grain if g.pin is not None}

    def props(self):
        """Effective properties: own (last occurrence wins, PROP-2) over inherited (PROP-3)."""
        out = {}
        for p in self.inherited:
            out[p.key] = p
        own = {}
        for p in self.own:
            own[p.key] = p
        out.update(own)
        return out


class DimDecl:
    """A dimension declaration (§6.1). source: None (members are data), "inline" or "file"."""

    def __init__(self, name, line, col, nline, ncol, path):
        self.name, self.line, self.col, self.nline, self.ncol, self.path = name, line, col, nline, ncol, path
        self.source = None
        self.members = []                                # inline: (name, line, col), in order
        self.file = None                                 # `from` path, as written
        self.fline = self.fcol = None
        self.props = []                                  # Prop, in source order
        self.broken = False

    def parents(self):
        """[(Prop, parent name, set of words)] for each well-formed @parent, in source order."""
        out = []
        for p in self.props:
            if p.key != "parent":
                continue
            if p.kind in ("ident", "string"):
                out.append((p, p.value, set()))
            elif p.kind == "words":
                out.append((p, p.value[0], set(p.value[1])))
        return out

    def attributes(self):
        """[(Prop, name, type)] for each @attribute with a name and a type, in source order."""
        return [(p, p.value[0], p.value[1][0]) for p in self.props
                if p.key == "attribute" and p.kind == "words" and len(p.value[1]) == 1]

    def has(self, key):
        return any(p.key == key for p in self.props)

    def semantic_time(self):
        return any(p.key == "semantic" and p.kind == "ident" and p.value == "time" for p in self.props)


class Document:
    def __init__(self, path):
        self.path = path
        self.dimensions = []                             # DimDecl, in source order
        self.variables = []
        self.defaults_blocks = []                        # lists of Prop
        self.errors = 0


# ----------------------------------------------------------------------------- document parser

class DocParser:
    def __init__(self, text, report, path=""):
        self.errors = 0

        def rep(line, col, code, msg):
            if code[4] == "E":
                self.errors += 1
            report(line, col, code, msg)
        self.report = rep
        self.t = lex(text, rep)
        self.i = 0
        self.doc = Document(path)
        self.defaults = []

    # -- cursor
    def peek(self, k=0):
        return self.t[min(self.i + k, len(self.t) - 1)]

    def next(self):
        tok = self.t[self.i]
        if tok.kind != EOF:
            self.i += 1
        return tok

    def past_nl(self, j=None):
        j = self.i if j is None else j
        while self.t[j].kind == NL:
            j += 1
        return j

    def skip_nl(self):
        self.i = self.past_nl()

    def at_line_end(self):
        return self.peek().kind in (NL, EOF)

    def skip_line(self):
        while self.peek().kind not in (NL, EOF):
            self.i += 1

    def starts_statement(self, j):
        """Does the (logical) line whose first token is t[j] begin a statement? (LEX-6)"""
        t = self.t[j]
        if t.kind == EOF:
            return True
        if t.is_p("@") or (t.kind == IDENT and t.value == "dimension"):
            return True
        if t.kind == IDENT and t.value in RETIRED and self.t[j + 1].is_name():
            return True
        if t.is_name():
            return self.t[self.past_nl(j + 1)].is_p("{")
        return False

    def recover(self):
        """After an error: skip to the next line that begins a statement."""
        self.skip_line()
        while True:
            self.skip_nl()
            if self.starts_statement(self.i):
                return
            self.skip_line()

    def err(self, tok, code, msg):
        self.report(tok.line, tok.col, code, msg)

    def expect_line_end(self, what):
        t = self.peek()
        if t.kind in (NL, EOF):
            return True
        if t.kind != BAD:
            self.err(t, "FML-E0105", f"unexpected {describe(t)} after {what}; expected the end of the line")
        self.skip_line()
        return False

    def name(self, what):
        t = self.peek()
        if t.is_name():
            self.next()
            if t.kind == IDENT and t.value in RESERVED:
                self.err(t, "FML-E0105", f"`{t.value}` is a reserved word; write the name in string form: \"{t.value}\" [§4.5]")
            return t
        if t.kind == NUMBER:
            self.err(t, "FML-E0105", f"expected {what}; a name that begins with a digit is written in string form: \"{t.raw}\" [LEX-1]")
        elif t.kind != BAD:
            self.err(t, "FML-E0105", f"expected {what}, found {describe(t)}")
        return None

    # -- document
    def parse(self):
        while True:
            self.skip_nl()
            t = self.peek()
            if t.kind == EOF:
                break
            if t.kind == BAD:
                self.recover(); continue
            if t.kind == IDENT and t.value == "dimension" and not self.t[self.past_nl(self.i + 1)].is_p("{"):
                self.dimension(); continue               # `dimension {` is a variable named dimension: reported there
            if t.kind == IDENT and t.value in RETIRED and self.peek(1).is_name():
                self.retired(t); continue
            if t.is_p("@"):
                t1 = self.peek(1)
                if t1.kind == IDENT and t1.value == "defaults":
                    self.defaults_block(); continue
                self.err(t, "FML-E0102", "property line outside a declaration or defaults block [PROP-1]")
                self.skip_line(); continue
            if t.is_name():
                j = self.past_nl(self.i + 1)
                if self.t[j].is_p("{"):
                    self.variable(); continue
                if self.t[j].kind != BAD:
                    self.err(self.t[j] if self.t[j].kind not in (NL, EOF) else t, "FML-E0105",
                             f"expected `{{` after the variable name {t.raw}")
                self.recover(); continue
            self.err(t, "FML-E0104", f"unexpected {describe(t)} at top level; expected a dimension declaration, "
                     "a defaults block or a variable declaration")
            self.recover()
        self.doc.errors = self.errors
        return self.doc

    def retired(self, kw):
        if kw.value == "link":
            msg = ("the link statement is retired: declare the parent with `@parent <Parent>` on the child's "
                   "dimension declaration [§7.1]")
        else:
            msg = "the time statement is retired: declare the dimension with `@semantic time` [§6.9]"
        self.err(kw, "FML-E0104", msg)
        self.recover()

    def dimension(self):
        kw = self.next()
        n = self.name("a dimension name after `dimension`")
        if n is None:
            self.recover(); return
        d = DimDecl(n.value, kw.line, kw.col, n.line, n.col, self.doc.path)
        self.doc.dimensions.append(d)
        t = self.peek()
        if t.is_p("{"):
            d.source = "inline"
            if not self.member_list(d):
                d.broken = True
                self.recover(); return
        elif t.kind == IDENT and t.value == "from":
            self.next()
            s = self.peek()
            if s.kind != STRING:
                if s.kind != BAD:
                    self.err(s, "FML-E0105", f"expected the path of a member file as a string after `from`, found {describe(s)}")
                d.broken = True
                self.recover(); return
            self.next()
            if s.error:
                d.broken = True
                self.recover(); return
            d.source, d.file, d.fline, d.fcol = "file", s.value, s.line, s.col
        if not self.expect_line_end(f"the declaration of {n.raw}"):
            d.broken = True
        d.props = self.property_lines()
        parents = {}
        for p, parent, _ in d.parents():
            if parent in parents:
                self.report(p.line, p.col, "FML-E0707",
                            f"@parent {parent} is given twice on {d.name} (also line {parents[parent].line}); "
                            "each parent dimension may be declared only once, regardless of modifiers [PARENT-4]")
            else:
                parents[parent] = p

    def member_list(self, d):
        """`{ name, … }` of an inline member source (§6.1, §4.9 item 7)."""
        self.next()
        while True:
            self.skip_nl()
            t = self.peek()
            if t.is_p("}"):
                self.next(); return True
            if t.kind == EOF:
                self.err(t, "FML-E0105", f"expected `}}` to close the members of {d.name}")
                return False
            m = self.name("a member name")
            if m is None:
                return False
            d.members.append((m.value, m.line, m.col))
            self.skip_nl()
            s = self.peek()
            if s.is_p(","):
                self.next()
            elif not s.is_p("}"):
                if s.kind != BAD:
                    self.err(s, "FML-E0105", f"expected `,` or `}}` in the members of {d.name}, found {describe(s)}")
                return False

    def defaults_block(self):
        at = self.next(); self.next()
        self.expect_line_end("`@defaults`")
        props = self.property_lines(origin="defaults")
        self.defaults = props
        self.doc.defaults_blocks.append(props)

    # -- properties
    def property_lines(self, origin="own"):
        props = []
        while True:
            j = self.past_nl()
            t = self.t[j]
            if not t.is_p("@") or (self.t[j + 1].kind == IDENT and self.t[j + 1].value == "defaults"):
                return props
            self.i = j
            p = self.property(origin)
            if p is not None:
                props.append(p)

    def property(self, origin="own"):
        at = self.next()
        nt = self.peek()
        if nt.kind != IDENT:
            if nt.kind != BAD:
                self.err(nt, "FML-E0105", f"expected a property name after `@`, found {describe(nt)}")
            self.skip_line(); return None
        self.next()
        v = self.peek()
        if v.kind in (NL, EOF):
            if nt.value == "null":                       # the one property without a value (DIM-13)
                return Prop("null", "none", None, "", at.line, at.col, nt.line, nt.col, origin)
            self.err(v if v.kind == NL else nt, "FML-E0106", f"expected a value for @{nt.value}")
            return None
        prop = self.property_value(nt.value, at, v, origin)
        if prop is None:
            self.skip_line(); return None
        t = self.peek()
        if t.kind not in (NL, EOF):
            if prop.kind == "ident" and t.is_op("-") and self.peek(1).kind == IDENT:
                self.err(prop_tok_start(prop), "FML-E0903",
                         f"`{prop.raw}-{self.peek(1).raw}` is not an identifier; write `{prop.raw}_{self.peek(1).raw}` [PROP-5]")
                prop.kind = "invalid"
            elif t.kind != BAD:
                self.err(t, "FML-E0105", f"unexpected {describe(t)} after the value of @{prop.key}; "
                         "a property line holds one property [§9.1]")
            self.skip_line()
        return prop

    def property_value(self, key, at, v, origin):
        mk = lambda kind, value, raw: Prop(key, kind, value, raw, at.line, at.col, v.line, v.col, origin)
        if v.kind == STRING:
            self.next()
            if self.peek().kind == IDENT:
                return self.words(mk, v)
            return mk("string", v.value, v.raw)
        if v.kind == NUMBER:
            self.next(); return mk("number", v.raw, v.raw)
        if v.kind == IDENT:
            self.next()
            if v.value in ("true", "false"):
                return mk("bool", v.value == "true", v.raw)
            if self.peek().is_p("("):
                depth, parts = 0, [v.raw]
                while True:
                    t = self.peek()
                    if t.kind in (NL, EOF):
                        self.err(t, "FML-E0105", f"unbalanced parentheses in the value of @{key}")
                        return None
                    self.next(); parts.append(t.raw)
                    depth += t.is_p("("); depth -= t.is_p(")")
                    if depth == 0:
                        break
                return mk("call", v.value, "".join(parts))
            if self.peek().kind == IDENT:
                return self.words(mk, v)
            return mk("ident", v.value, v.raw)
        if v.is_p("{"):
            return self.object_value(key, at, v, origin)
        if v.kind != BAD:
            self.err(v, "FML-E0106", f"expected a property value for @{key}, found {describe(v)}")
        return None

    def words(self, mk, first):
        """`name identifier { identifier }`: @attribute <name> <type>, @parent <dim> [many] [required]."""
        rest = []
        while self.peek().kind == IDENT:
            rest.append(self.next().value)
        raw = " ".join([first.raw] + rest)
        return mk("words", (first.value, rest), raw)

    def object_value(self, key, at, v, origin):
        self.next()
        pairs = []
        while True:
            self.skip_nl()
            t = self.peek()
            if t.is_p("}"):
                self.next(); break
            if t.kind == EOF:
                self.err(v, "FML-E0105", f"expected `}}` to close the object value of @{key}")
                return None
            if not t.is_name():
                if t.kind != BAD:
                    self.err(t, "FML-E0105", f"expected a field name in the object value of @{key}, found {describe(t)}")
                return self._abandon_object()
            self.next()
            c = self.peek()
            if not c.is_p(":"):
                if c.kind != BAD:
                    self.err(c, "FML-E0105", f"expected `:` after the field name {t.raw}")
                return self._abandon_object()
            self.next()
            x = self.peek()
            if x.kind == STRING:
                kind, val = "string", x.value
            elif x.kind == NUMBER:
                kind, val = "number", x.raw
            elif x.kind == IDENT:
                kind, val = ("bool", x.value == "true") if x.value in ("true", "false") else ("ident", x.value)
            else:
                if x.kind != BAD:
                    self.err(x, "FML-E0106", f"expected a value for the field {t.raw}, found {describe(x)}")
                return self._abandon_object()
            self.next()
            pairs.append((t.value, kind, val, x.raw))
            s = self.peek()
            if s.is_p(","):
                self.next()
            elif s.kind == NL or s.is_p("}"):
                pass
            else:
                if s.kind != BAD:
                    self.err(s, "FML-E0105", f"expected `,`, a line break or `}}` after the field {t.raw}, found {describe(s)}")
                return self._abandon_object()
        raw = "{ " + ", ".join(f"{k}: {r}" for k, _, _, r in pairs) + " }"
        return Prop(key, "object", pairs, raw, at.line, at.col, v.line, v.col, origin)

    def _abandon_object(self):
        while self.peek().kind != EOF and not self.peek().is_p("}") and not (
                self.peek().kind == NL and self.starts_statement(self.past_nl())):
            self.i += 1
        if self.peek().is_p("}"):
            self.next()
        return None

    # -- variables
    def variable(self):
        nt = self.next()
        var = Variable(nt.value, nt.line, nt.col, self.doc.path)
        if nt.kind == IDENT and nt.value in RESERVED:
            self.err(nt, "FML-E0105", f"`{nt.value}` is a reserved word; write the variable name in string form [§4.5]")
            var.broken = True
        self.skip_nl()
        self.next()                                      # '{' (checked by the caller)
        if not self.grain(var):
            var.broken = True
            var.inherited = list(self.defaults)
            self.doc.variables.append(var)
            self.recover()
            return
        t = self.peek()
        if t.is_p("="):
            self.formula(var)
        elif t.is_p("@"):
            first = self.property()                      # VAR-1: inline properties, formula-less variables only
            var.own = ([first] if first else []) + self.property_lines()
        elif t.kind in (NL, EOF):
            j = self.past_nl()
            if self.t[j].is_p("="):
                self.i = j; self.formula(var)
            else:
                var.own = self.property_lines()
        else:
            if t.kind != BAD:
                self.err(t, "FML-E0105", f"expected `=`, a property or the end of the line after the grain, found {describe(t)}")
            var.broken = True
            self.recover()
        var.inherited = list(self.defaults)
        self.doc.variables.append(var)

    def grain(self, var):
        while True:
            self.skip_nl()
            t = self.peek()
            if t.is_p("}"):
                self.next(); return True
            if t.kind == EOF:
                self.err(t, "FML-E0105", f"expected `}}` to close the grain of {var.name}")
                return False
            d = self.name("a dimension name in the grain")
            if d is None:
                return False
            ge = GrainEntry(d.value, d.line, d.col)
            if self.peek().is_p("="):
                self.next()
                m = self.name("the pinned member after `=`")
                if m is None:
                    return False
                ge.pin, ge.pline, ge.pcol = m.value, m.line, m.col
            var.grain.append(ge)
            s = self.peek()
            if s.is_p(","):
                self.next()
            elif s.kind == NL or s.is_p("}"):
                pass                                     # §4.9 item 2: a line break MAY separate entries
            else:
                if s.kind != BAD:
                    self.err(s, "FML-E0105", f"expected `,` or `}}` in the grain of {var.name}, found {describe(s)}")
                return False

    def formula(self, var):
        eq = self.next()
        var.has_formula = True
        new_line = self.peek().kind == NL
        self.skip_nl()                                   # §4.9 item 4
        t = self.peek()
        if t.kind == EOF or t.is_p("@") or (new_line and self.starts_statement(self.i)):
            self.err(eq, "FML-E0105", f"expected a formula after `=`, found {describe(t)}")
            var.formula_ok = False
            var.broken = True
            var.own = self.property_lines()
            return
        toks, depth, opens, reported = [], 0, [], False
        while True:
            t = self.peek()
            if t.kind == EOF:
                break
            if t.kind == NL:
                j = self.past_nl()
                if depth > 0:                            # §4.9 item 3: free inside parentheses …
                    if self.t[j].kind != EOF and self.starts_statement(j):
                        o = opens[-1]                    # … but a property or header there means a missing ')'
                        self.err(o, "FML-E0103", f"`(` is not closed: line {self.t[j].line} begins a "
                                 f"{'property' if self.t[j].is_p('@') else 'new statement'} [EXPR-5]")
                        reported = True
                        break
                    if self.t[j].kind == EOF:
                        break
                    self.i = j; continue
                if self.starts_statement(j):             # LEX-6
                    break
                if (toks and toks[-1].kind == OP) or self.t[j].kind == OP:   # §4.9 item 5
                    self.i = j; continue
                break
            if t.is_p("("):
                depth += 1; opens.append(t)
            elif t.is_p(")") and depth > 0:
                depth -= 1; opens.pop()
            if t.is_p("@") and depth == 0:
                self.err(t, "FML-E0105", "a property after a formula must begin on its own line [VAR-1]")
                reported = True
                self.skip_line()
                break
            toks.append(t); self.next()
        var.fline, var.fcol = (toks[0].line, toks[0].col) if toks else (eq.line, eq.col)
        if reported:
            var.formula_ok = False
        else:
            before = self.errors
            var.formula = parse_formula_tokens(toks, self.report)
            var.formula_ok = var.formula is not None and self.errors == before
        if not var.formula_ok:
            var.broken = True
        var.own = self.property_lines()


def prop_tok_start(p):
    class P:
        line, col = p.vline, p.vcol
    return P


def parse_document(text, report, path=""):
    return DocParser(text, report, path).parse()


# ----------------------------------------------------------------------------- names

def name_repr(name):
    """Identifier form where valid, otherwise string form (§5.6 item 6)."""
    if IDENT_RX.match(name) and name not in RESERVED:
        return name
    return quote(name)


def quote(s):
    out = ['"']
    for ch in s:
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\t":
            out.append("\\t")
        elif ch == "\r":
            out.append("\\r")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)
