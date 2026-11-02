"""Diagnostics: codes, profile severities (FML 1.0 §15.4, Annex C)."""

PROFILES = ("lenient", "standard", "strict")

# Rows of the §15.4 table: (lenient, standard, strict); None = not reported.
_NAMING = ("I", "W", "W")
_READONLY = ("I", "W", "E")
_DESC = (None, "I", "W")
_LINK_CYCLES = ("I", "W", "E")
_DIAMONDS = (None, "I", "W")
_GRAIN = ("I", "W", "E")
_SPARSITY = ("I", "W", "E")
_EXTENSIONS = (None, None, "I")
_NOTES = (None, "I", "W")

PROFILE_ROWS = {
    "FML-W1201": _NAMING, "FML-W1202": _NAMING, "FML-W1203": _NAMING, "FML-W1205": _NAMING,
    "FML-W1204": _READONLY,
    "FML-I1206": _DESC,
    "FML-W0701": _LINK_CYCLES,
    "FML-I0702": _DIAMONDS,
    "FML-W1101": _GRAIN, "FML-W1102": _GRAIN, "FML-W1103": _GRAIN, "FML-W1104": _GRAIN,
    "FML-W1105": _GRAIN,
    "FML-W1001": _SPARSITY, "FML-W1002": _SPARSITY, "FML-W1005": _SPARSITY,
    "FML-W1006": _SPARSITY, "FML-W1007": _SPARSITY, "FML-W1106": _SPARSITY,
    "FML-I0904": _EXTENSIONS,
    "FML-I1208": _NOTES,
}

SEVERITY_WORD = {"E": "error", "W": "warning", "I": "info"}


def severity(code, profile):
    """Effective severity letter of a code under a profile, or None when not reported.
    An E is never lowered (Annex C)."""
    letter = code[4]
    if letter == "E":
        return "E"
    row = PROFILE_ROWS.get(code)
    if row is None:
        return letter
    return row[PROFILES.index(profile)]


class Diag:
    __slots__ = ("path", "line", "col", "code", "message")

    def __init__(self, path, line, col, code, message):
        self.path, self.line, self.col, self.code, self.message = path, line, col, code, message

    def key(self):
        return (self.path, self.line, self.col, self.code, self.message)

    def as_dict(self, profile):
        return {"path": self.path, "line": self.line, "col": self.col, "code": self.code,
                "severity": SEVERITY_WORD.get(severity(self.code, profile) or "", "off"),
                "message": self.message}


class Sink:
    """Collects diagnostics for one model; `at(path)` gives a reporter bound to a file."""

    def __init__(self):
        self.items = []
        self._seen = set()

    def add(self, path, line, col, code, message):
        d = Diag(path, line, col, code, message)
        if d.key() in self._seen:
            return
        self._seen.add(d.key())
        self.items.append(d)

    def at(self, path):
        sink = self

        class Reporter:
            def __call__(self, line, col, code, message):
                sink.add(path, line, col, code, message)
        return Reporter()

    def sorted(self):
        return sorted(self.items, key=lambda d: (d.path, d.line, d.col, d.code))
