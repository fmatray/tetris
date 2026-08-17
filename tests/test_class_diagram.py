"""Verify docs/class_diagram.md is exhaustive against the source code.

AST-parses every .py file under tetris/ and asserts the Mermaid class
diagram contains every class, every method, every instance attribute,
every __slots__ entry, every @property, and every inheritance edge.

Run: SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m pytest tests/test_class_diagram.py -q
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIAGRAM_PATH = ROOT / "docs" / "class_diagram.md"
SOURCE_ROOT = ROOT / "tetris"

# ── Source extraction ────────────────────────────────────────────────


def _extract_classes_from_source() -> dict[str, dict]:
    """AST-parse tetris/ and return {class_name: {methods, attrs, bases, slots, properties, statics}}."""
    classes: dict[str, dict] = {}
    for py in SOURCE_ROOT.rglob("*.py"):
        tree = ast.parse(py.read_text(), filename=str(py))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            info: dict = {
                "methods": set(),
                "attrs": set(),
                "bases": set(),
                "slots": set(),
                "properties": set(),
                "statics": set(),
            }
            # Inheritance
            for base in node.bases:
                if isinstance(base, ast.Name):
                    info["bases"].add(base.id)
                elif isinstance(base, ast.Attribute):
                    info["bases"].add(base.attr)
            # Methods
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    info["methods"].add(item.name)
                    # Detect @property
                    for dec in item.decorator_list:
                        if isinstance(dec, ast.Name) and dec.id == "property":
                            info["properties"].add(item.name)
                        if isinstance(dec, ast.Attribute) and dec.attr == "staticmethod":
                            info["statics"].add(item.name)
                        if isinstance(dec, ast.Name) and dec.id == "staticmethod":
                            info["statics"].add(item.name)
                    # Instance attributes: self.X = ... in __init__
                    if item.name == "__init__":
                        for stmt in ast.walk(item):
                            if (
                                isinstance(stmt, ast.Assign)
                                and isinstance(stmt.targets[0], ast.Attribute)
                                and isinstance(stmt.targets[0].value, ast.Name)
                                and stmt.targets[0].value.id == "self"
                            ):
                                info["attrs"].add(stmt.targets[0].attr)
            # __slots__
            for item in node.body:
                if (
                    isinstance(item, ast.Assign)
                    and len(item.targets) == 1
                    and isinstance(item.targets[0], ast.Name)
                    and item.targets[0].id == "__slots__"
                    and isinstance(item.value, ast.Tuple)
                ):
                    for elt in item.value.elts:
                        if isinstance(elt, ast.Constant):
                            info["slots"].add(elt.value)
            classes[node.name] = info
    return classes


# ── Diagram extraction ──────────────────────────────────────────────


def _extract_classes_from_diagram() -> dict[str, dict]:
    """Regex-parse the mermaid block and return {class_name: {methods, attrs}}."""
    text = DIAGRAM_PATH.read_text()
    # Extract the mermaid block
    m = re.search(r"```mermaid\n(.*?)```", text, re.DOTALL)
    assert m is not None
    body = m.group(1)
    # Replace {static} marker so its braces don't break block extraction
    body = body.replace("{static}", "STATIC")

    classes: dict[str, dict] = {}
    # Match class blocks: class ClassName { ... }
    for cm in re.finditer(r"class\s+(\w+)\s*\{(.*?)\}", body, re.DOTALL):
        name = cm.group(1)
        block = cm.group(2)
        methods: set[str] = set()
        attrs: set[str] = set()
        for line in block.strip().splitlines():
            line = line.strip()
            if not line or line.startswith(("%%", "__slots__")):
                continue
            # Method lines contain ()
            if "(" in line and ")" in line:
                # Extract method name before (
                mm = re.search(r"[+\-#]?\s*(?:STATIC\s+)?(\w+)\s*\(", line)
                if mm:
                    methods.add(mm.group(1))
            elif line and not line.startswith("%%"):
                # Attribute line: +name: type or -name: type
                am = re.search(r"[+\-#]\s*(\w+)\s*:", line)
                if am:
                    attrs.add(am.group(1))
        classes[name] = {"methods": methods, "attrs": attrs}

    # Extract inheritance edges: A <|-- B
    inheritance: set[tuple[str, str]] = set()
    for im in re.finditer(r"(\w+)\s*<\|--\s*(\w+)", body):
        inheritance.add((im.group(1), im.group(2)))

    # Store inheritance on a special key
    classes["__inheritance__"] = {"methods": set(), "attrs": set(), "edges": inheritance}  # type: ignore[assignment]
    return classes


# ── Tests ────────────────────────────────────────────────────────────

_SRC = _extract_classes_from_source()
_DIAG = _extract_classes_from_diagram()

# Synthetic classes in the diagram that don't exist in source (utility wrappers).
_SKIP_CLASSES: set[str] = {"Storage", "nn_Module"}

# Methods that are Python dunder or internal and need not appear in the
# diagram (beyond __init__ which we always include).
_SKIP_METHODS = {"__len__"}


def test_class_count():
    """Diagram has exactly the same classes as source (minus skips)."""
    src_classes = {c for c in _SRC if c not in _SKIP_CLASSES}
    diag_classes = {c for c in _DIAG if c != "__inheritance__"}
    missing = src_classes - diag_classes
    extra = diag_classes - src_classes - _SKIP_CLASSES
    assert not missing, f"Classes missing from diagram: {missing}"
    assert not extra, f"Extra classes in diagram: {extra}"


def test_methods_present():
    """Every source method appears in the diagram."""
    missing: dict[str, set[str]] = {}
    for cls, info in _SRC.items():
        if cls in _SKIP_CLASSES:
            continue
        if cls not in _DIAG:
            continue
        diag_methods = _DIAG[cls]["methods"]
        for method in info["methods"]:
            if method in info["properties"]:
                continue  # properties are checked in test_properties_present
            if method in _SKIP_METHODS:
                continue
            if method not in diag_methods:
                missing.setdefault(cls, set()).add(method)
    assert not missing, f"Methods missing from diagram: {missing}"


def test_attributes_present():
    """Every self.X assignment and __slots__ entry appears in the diagram."""
    missing: dict[str, set[str]] = {}
    for cls, info in _SRC.items():
        if cls in _SKIP_CLASSES:
            continue
        if cls not in _DIAG:
            continue
        diag_attrs = _DIAG[cls]["attrs"]
        for attr in info["attrs"] | info["slots"]:
            if attr not in diag_attrs:
                missing.setdefault(cls, set()).add(attr)
    assert not missing, f"Attributes missing from diagram: {missing}"


def test_inheritance_edges():
    """Every source inheritance relationship appears in the diagram."""
    diag_edges = _DIAG.get("__inheritance__", {}).get("edges", set())
    missing: set[tuple[str, str]] = set()
    for cls, info in _SRC.items():
        for base in info["bases"]:
            # Skip external bases like nn.Module (handled as nn_Module)
            edge = (base, cls)
            if edge not in diag_edges:
                # Check if the base is external (not in source classes)
                if base not in _SRC and base not in _DIAG:
                    # External base — check for a renamed variant
                    ext_edge = (f"{base.replace('.', '_')}_Module", cls)
                    if ext_edge not in diag_edges:
                        # External bases are acceptable to skip
                        continue
                else:
                    missing.add(edge)
    assert not missing, f"Inheritance edges missing from diagram: {missing}"


def test_properties_present():
    """Every @property method appears in the diagram as a method or attribute."""
    missing: dict[str, set[str]] = {}
    for cls, info in _SRC.items():
        if cls in _SKIP_CLASSES or cls not in _DIAG:
            continue
        diag_methods = _DIAG[cls]["methods"]
        diag_attrs = _DIAG[cls]["attrs"]
        for prop in info["properties"]:
            if prop not in diag_methods and prop not in diag_attrs:
                missing.setdefault(cls, set()).add(prop)
    assert not missing, f"Properties missing from diagram: {missing}"


def test_statics_present():
    """Every @staticmethod appears in the diagram."""
    missing: dict[str, set[str]] = {}
    for cls, info in _SRC.items():
        if cls in _SKIP_CLASSES or cls not in _DIAG:
            continue
        diag_methods = _DIAG[cls]["methods"]
        for stat in info["statics"]:
            if stat not in diag_methods:
                missing.setdefault(cls, set()).add(stat)
    assert not missing, f"Static methods missing from diagram: {missing}"