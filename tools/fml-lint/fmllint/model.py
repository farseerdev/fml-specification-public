"""Loading a model: documents, the member files their declarations name, and the manifest
(FML 1.0 §5.2, §5.7, §6.1, §6.4)."""
import json
import os
import re

from .members import parse_member_file
from .syntax import parse_document

SUPPORTED_FML = ("1.0",)
_YM = re.compile(r"(\d{4})-(\d{2})\Z")


class Manifest:
    def __init__(self):
        self.present = False
        self.valid = False
        self.fml = None
        self.horizon = None                              # (from_year, to_year) when valid
        self.versions = None                             # set, Actual and Plan always included
        self.members_complete = False
        self.data = None


def _line_of(text, key):
    m = re.search(r'"%s"\s*:' % re.escape(key), text)
    return text.count("\n", 0, m.start()) + 1 if m else 1


def load_manifest(path, report):
    """Validate model.json [DOC-5]; every violation is FML-E0608."""
    mf = Manifest()
    if not os.path.exists(path):
        return mf
    mf.present = True
    text = open(path, encoding="utf-8").read()
    try:
        data = json.loads(text)
    except ValueError as e:
        line = getattr(e, "lineno", 1); col = getattr(e, "colno", 1)
        report(line, col, "FML-E0608", f"model manifest is not valid JSON: {getattr(e, 'msg', e)} [DOC-5]")
        return mf
    if not isinstance(data, dict):
        report(1, 1, "FML-E0608", "model manifest must be a JSON object [DOC-5]")
        return mf
    mf.data = data
    ok = True

    def bad(key, msg):
        nonlocal ok
        ok = False
        report(_line_of(text, key) if key else 1, 1, "FML-E0608", msg + " [DOC-5]")

    fml = data.get("fml")
    if "fml" not in data:
        bad(None, "model manifest has no `fml` field (required)")
    elif not isinstance(fml, str) or not re.fullmatch(r"\d+\.\d+", fml):
        bad("fml", f"`fml` must be a version string \"MAJOR.MINOR\", found {json.dumps(fml)}")
    elif fml not in SUPPORTED_FML:
        bad("fml", f"FML version {fml} is not implemented by this linter (supported: {', '.join(SUPPORTED_FML)})")
    else:
        mf.fml = fml

    hz = data.get("horizon")
    if "horizon" not in data:
        bad(None, "model manifest has no `horizon` field (required)")
    elif not isinstance(hz, dict) or not isinstance(hz.get("from"), str) or not isinstance(hz.get("to"), str):
        bad("horizon", "`horizon` must be an object {\"from\": \"YYYY-01\", \"to\": \"YYYY-12\"}")
    else:
        f, t = _YM.match(hz["from"]), _YM.match(hz["to"])
        if not f or not t or not (1 <= int(f.group(2)) <= 12) or not (1 <= int(t.group(2)) <= 12):
            bad("horizon", f"horizon members must be YearMonth members \"YYYY-MM\", found {hz['from']!r} to {hz['to']!r}")
        elif f.group(2) != "01" or t.group(2) != "12":
            bad("horizon", f"horizon must cover whole years: `from` ends in -01 and `to` in -12, "
                f"found {hz['from']!r} to {hz['to']!r} [DIM-9]")
        elif hz["from"] > hz["to"]:
            bad("horizon", f"horizon `from` {hz['from']!r} is after `to` {hz['to']!r}")
        else:
            mf.horizon = (int(f.group(1)), int(t.group(1)))

    if "versions" in data:
        vs = data["versions"]
        if not isinstance(vs, list) or not all(isinstance(v, str) and v for v in vs):
            bad("versions", "`versions` must be a list of member names")
        else:
            if len({v.lower() for v in vs}) != len(vs):
                bad("versions", "`versions` lists a member twice (member names are unique case-insensitively)")
            mf.versions = set(vs) | {"Actual", "Plan"}
    else:
        mf.versions = {"Actual", "Plan"}

    if "membersComplete" in data:
        if not isinstance(data["membersComplete"], bool):
            bad("membersComplete", "`membersComplete` must be true or false")
        else:
            mf.members_complete = data["membersComplete"]
    mf.valid = ok
    return mf


class Model:
    def __init__(self, root, display_root):
        self.root = root
        self.display_root = display_root
        self.docs = []
        self.tables = []                                 # MemberTable, every member file read
        self.table_of = {}                               # id(DimDecl) -> MemberTable, for `from` sources
        self.manifest = Manifest()
        self.single_file = False


def display(model, rel):
    return os.path.join(model.display_root, rel) if model.display_root else rel


def load(target, sink):
    """Load a model directory, a single .fml document or a single member file."""
    if os.path.isdir(target):
        root = target
        m = Model(root, target)
        fmls = []
        for dp, dns, fns in os.walk(root):
            dns[:] = sorted(d for d in dns if not d.startswith("."))
            for fn in sorted(fns):
                if fn.endswith(".fml"):
                    fmls.append(os.path.relpath(os.path.join(dp, fn), root))
        for rel in sorted(fmls):
            _load_doc(m, rel, sink)
        _load_sources(m, sink)
        mp = os.path.join(root, "model.json")
        m.manifest = load_manifest(mp, sink.at(display(m, "model.json")))
        return m
    root, fn = os.path.split(target)
    m = Model(root or ".", root)
    m.single_file = True
    if fn.endswith(".csv"):
        _load_table(m, fn, sink)
    else:
        _load_doc(m, fn, sink)                           # a model of one document: `from` is relative to its folder
        _load_sources(m, sink)
    return m


def read_text(path, report):
    """UTF-8 text (§4.1, [DIM-10]); undecodable bytes are reported and replaced."""
    raw = open(path, "rb").read()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as e:
        line = raw[:e.start].count(b"\n") + 1
        col = e.start - (raw.rfind(b"\n", 0, e.start) + 1) + 1
        report(line, col, "FML-E0107", f"the file is not valid UTF-8 (byte 0x{raw[e.start]:02X}) [§4.1]")
        return raw.decode("utf-8", errors="replace")


def _load_doc(m, rel, sink):
    path = os.path.join(m.root, rel)
    text = read_text(path, sink.at(display(m, rel)))
    doc = parse_document(text, sink.at(display(m, rel)), display(m, rel))
    doc.rel = rel
    m.docs.append(doc)


def _load_table(m, rel, sink):
    path = os.path.join(m.root, rel)
    text = read_text(path, sink.at(display(m, rel)))
    t = parse_member_file(text, display(m, rel), sink.at(display(m, rel)))
    t.rel = rel
    m.tables.append(t)
    return t


def _load_sources(m, sink):
    """The member file each `from "<path>"` names, relative to the model directory [DIM-12]. A file named by
    several declarations is read once. A missing file is left for the checks (FML-E0612)."""
    read = {}
    for doc in m.docs:
        for d in doc.dimensions:
            if d.source != "file" or not d.file:
                continue
            rel = os.path.normpath(d.file)
            if not os.path.isfile(os.path.join(m.root, rel)):
                continue
            if rel not in read:
                read[rel] = _load_table(m, rel, sink)
            m.table_of[id(d)] = read[rel]
