"""Member files (FML 1.0 §6.4, [DIM-3], [DIM-10], Annex A.5).

A member file is RFC 4180 CSV in UTF-8: a header row, then one row per member. There are
no comment lines and no blank lines, and cells are not trimmed. What a header cell means
(a parent or an attribute) depends on the declaration that names the file; the checks
resolve it (checks.py).
"""


class Cell:
    __slots__ = ("text", "line", "col", "quoted")

    def __init__(self, text, line, col, quoted):
        self.text, self.line, self.col, self.quoted = text, line, col, quoted


class Member:
    __slots__ = ("name", "line", "col", "cells", "desc")

    def __init__(self, name, line, col):
        self.name, self.line, self.col = name, line, col
        self.cells = {}                                  # header text -> Cell (the first column of that name)
        self.desc = None


class MemberTable:
    def __init__(self, path):
        self.path = path
        self.dim = None
        self.dline = self.dcol = 1
        self.columns = []                                # header cells after the first: Cell
        self.members = []
        self.ok = True

    def names(self):
        return [m.name for m in self.members]


def has_control(s):
    return any(ord(ch) < 0x20 for ch in s)


def null_name(dim):
    return f"NULL ({dim})"


def records(text, report):
    """RFC 4180 records [DIM-3]. Yields ([Cell], line). A blank line is reported and skipped."""
    if text.startswith("﻿"):
        text = text[1:]
    text = text.replace("\r\n", "\n")
    i, n, line = 0, len(text), 1
    while i < n:
        if text[i] == "\n":
            report(line, 1, "FML-E0105", "blank line in a member file; a member file has none [DIM-3]")
            i += 1; line += 1; continue
        # a record: cells separated by ',', quoted cells may contain ',', '""' and line breaks
        cells, start_line, ls = [], line, i
        while True:
            col = i - ls + 1
            if i < n and text[i] == '"':
                buf, i, closed = [], i + 1, False
                cl, cc = line, col
                while i < n:
                    ch = text[i]
                    if ch == '"':
                        if i + 1 < n and text[i + 1] == '"':
                            buf.append('"'); i += 2; continue
                        closed = True; i += 1; break
                    if ch == "\n":
                        line += 1; ls = i + 1
                    buf.append(ch); i += 1
                if not closed:
                    report(cl, cc, "FML-E0101", "unterminated quoted cell in the member file")
                    yield cells + [Cell("".join(buf), cl, cc, True)], start_line
                    return
                if i < n and text[i] not in ",\n":
                    report(line, i - ls + 1, "FML-E0105", "unexpected text after a quoted cell; expected `,` or the "
                           "end of the row [DIM-3]")
                    while i < n and text[i] not in ",\n":
                        i += 1
                cells.append(Cell("".join(buf), cl, cc, True))
            else:
                k = i
                while k < n and text[k] not in ",\n":
                    k += 1
                raw = text[i:k]
                if '"' in raw:
                    report(line, col + raw.index('"'), "FML-E0105", "a `\"` inside an unquoted cell; a cell holding "
                           "`\"` is enclosed in double quotes and the quote doubled [DIM-3]")
                cells.append(Cell(raw, line, col, False))
                i = k
            if i < n and text[i] == ",":
                i += 1; continue
            break
        yield cells, start_line
        i += 1; line += 1


def parse_member_file(text, path, report):
    """Parse one member file; report(line, col, code, msg). Returns a MemberTable."""
    t = MemberTable(path)
    header = None
    seen = {}
    for cells, line in records(text, report):
        if header is None:
            header = cells
            first = cells[0]
            if first.text == "":
                report(first.line, first.col, "FML-E0105", "expected the dimension name as the first header cell [DIM-3]")
                t.ok = False
                return t
            t.dim, t.dline, t.dcol = first.text, first.line, first.col
            if has_control(first.text):
                report(first.line, first.col, "FML-E0205", "the dimension name contains a control character [LEX-3]")
            for c in cells[1:]:
                if c.text == "":
                    report(c.line, c.col, "FML-E0105", "expected `@description`, a parent dimension or an attribute "
                           "as a header cell [DIM-3]")
                t.columns.append(c)
            continue
        if len(cells) != len(header):
            report(cells[0].line, cells[0].col, "FML-E0609",
                   f"member row has {len(cells)} cells, the header has {len(header)} [DIM-10]")
        name = cells[0]
        if name.text == "":
            report(name.line, name.col, "FML-E0105", "expected a member name as the first cell of the row")
            continue
        if has_control(name.text):
            report(name.line, name.col, "FML-E0205", f"member name {name.text!r} contains a control character [LEX-3]")
        if name.text == null_name(t.dim):
            report(name.line, name.col, "FML-E0615", f"the member file lists {name.text!r}; only `@null` on the "
                   f"declaration gives a dimension its NULL member [DIM-5], [DIM-10]")
            continue
        low = name.text.lower()
        if low in seen:
            prev = seen[low]
            how = "is listed twice" if prev.name == name.text else f"differs only by case from {prev.name!r} (line {prev.line})"
            report(name.line, name.col, "FML-E0603", f"member {name.text!r} {how}; member names are unique "
                   f"case-insensitively [DIM-1]")
            continue
        m = Member(name.text, name.line, name.col)
        seen[low] = m
        for hc, c in zip(header[1:], cells[1:]):
            if hc.text == "@description":
                if m.desc is None:
                    m.desc = c.text
            elif hc.text and hc.text not in m.cells:
                m.cells[hc.text] = c
        t.members.append(m)
    if header is None:
        report(1, 1, "FML-E0105", "member file has no header line [DIM-3]")
        t.ok = False
    return t
