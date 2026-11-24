"""Minimal KiCad s-expression tooling for the rev 3 schematic generator.

Reads symbols out of the KiCad standard libraries, flattens `extends` inheritance the
way eeschema does when it copies a symbol into a schematic's lib_symbols, and reports
pin positions so the generator can attach wires and labels to them.
"""
import os
import re

KICAD_SYMBOLS = os.environ.get("KICAD_SYMBOLS", "/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols")


# --- s-expression parsing -----------------------------------------------------------

class Sym(str):
    """A bare (unquoted) token."""


def parse(text):
    """Parse one s-expression document into nested lists. Strings stay quoted-aware:
    quoted strings become plain str, bare tokens become Sym."""
    tokens = re.findall(r'"(?:[^"\\]|\\.)*"|\(|\)|[^\s()"]+', text)
    stack = [[]]
    for t in tokens:
        if t == "(":
            stack.append([])
        elif t == ")":
            node = stack.pop()
            stack[-1].append(node)
        elif t.startswith('"'):
            stack[-1].append(t[1:-1].replace('\\"', '"'))
        else:
            stack[-1].append(Sym(t))
    return stack[0][0]


def dump(node, indent=0):
    """Serialize nested lists back to KiCad-style text (one child per line)."""
    pad = "\t" * indent
    if isinstance(node, list):
        if not node:
            return pad + "()"
        head = node[0]
        parts = [pad + "(" + _atom(head)]
        inline = []
        children = []
        for c in node[1:]:
            if isinstance(c, list):
                children.append(c)
            else:
                inline.append(_atom(c))
        if inline:
            parts[0] += " " + " ".join(inline)
        if not children:
            return parts[0] + ")"
        out = [parts[0]]
        for c in children:
            out.append(dump(c, indent + 1))
        out.append(pad + ")")
        return "\n".join(out)
    return pad + _atom(node)


def _atom(a):
    if isinstance(a, Sym):
        return str(a)
    if isinstance(a, str):
        return '"' + a.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n') + '"'
    return str(a)


def find(node, key):
    """First direct child list whose head is `key`."""
    for c in node:
        if isinstance(c, list) and c and c[0] == key:
            return c
    return None


def find_all(node, key):
    return [c for c in node if isinstance(c, list) and c and c[0] == key]


# --- symbol libraries ----------------------------------------------------------------

_lib_cache = {}


def load_lib(libname):
    if libname not in _lib_cache:
        path = os.path.join(KICAD_SYMBOLS, libname + ".kicad_sym")
        with open(path, encoding="utf-8") as f:
            doc = parse(f.read())
        syms = {}
        for s in find_all(doc, "symbol"):
            syms[s[1]] = s
        _lib_cache[libname] = syms
    return _lib_cache[libname]


def get_symbol(lib_id):
    """Return a flattened copy of `Lib:Name` ready for a schematic's lib_symbols block:
    top-level name is `Lib:Name`, sub-unit names are `Name_u_s`, no `extends`."""
    libname, name = lib_id.split(":", 1)
    syms = load_lib(libname)
    if name not in syms:
        raise KeyError(f"{lib_id} not in {libname}.kicad_sym")
    child = syms[name]
    ext = find(child, "extends")
    if ext:
        parent = _copy(syms[ext[1]])
        pname = parent[1]
        # rename parent and its units
        parent[1] = name
        for u in find_all(parent, "symbol"):
            u[1] = name + u[1][len(pname):]
        # child properties override parent's
        child_props = {p[1]: p for p in find_all(child, "property")}
        new = []
        for c in parent[2:]:
            if isinstance(c, list) and c and c[0] == "property":
                if c[1] in child_props:
                    c = _copy(child_props.pop(c[1]))
            new.append(c)
        for p in child_props.values():
            new.insert(0, _copy(p))
        parent[2:] = new
        flat = parent
    else:
        flat = _copy(child)
    flat[1] = lib_id
    return flat


def _copy(node):
    if isinstance(node, list):
        return [_copy(c) for c in node]
    return node


def pins(sym):
    """List of dicts: number, name, x, y (library coords, y up), angle, type, unit,
    hidden. Collected over every sub-unit of a flattened symbol."""
    out = []
    for u in find_all(sym, "symbol"):
        m = re.match(r".*_(\d+)_(\d+)$", u[1])
        unit = int(m.group(1)) if m else 0
        for p in find_all(u, "pin"):
            at = find(p, "at")
            out.append(dict(
                number=find(p, "number")[1],
                name=find(p, "name")[1],
                x=float(at[1]), y=float(at[2]), angle=float(at[3]) if len(at) > 3 else 0.0,
                length=float(find(p, "length")[1]),
                type=str(p[1]), unit=unit,
                hidden=find(p, "hide") is not None,
            ))
    return out


if __name__ == "__main__":
    import sys
    for lib_id in sys.argv[1:]:
        s = get_symbol(lib_id)
        ps = pins(s)
        print(f"== {lib_id}: {len(ps)} pins, units {sorted(set(p['unit'] for p in ps))}")
        for p in ps:
            print(f"  {p['number']:>4} {p['name']:<18} at ({p['x']:7.2f},{p['y']:7.2f}) ang {p['angle']:5.0f} len {p['length']:4.2f} {p['type']}{' hidden' if p['hidden'] else ''} u{p['unit']}")
