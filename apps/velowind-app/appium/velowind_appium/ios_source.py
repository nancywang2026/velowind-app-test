"""Read iOS state independently of XML attribute order."""
from __future__ import annotations

from xml.etree import ElementTree


def visible_ios_name(source: str, names: set[str]) -> bool | None:
    """Return None for non-iOS or incomplete XML, for legacy text fallbacks."""
    if "<XCUIElementType" not in source:
        return None
    try:
        root = ElementTree.fromstring(source)
    except ElementTree.ParseError:
        return None

    def walk(node):
        if node.get("visible") == "false" or node.get("enabled") == "false":
            return False
        if node.get("visible") == "true" and any(node.get(attr) in names for attr in ("name", "label", "value")):
            return True
        return any(walk(child) for child in node)

    return walk(root)
