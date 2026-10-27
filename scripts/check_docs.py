"""Validate local documentation references and SVG metadata without a network."""

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def without_fences(text):
    output, fence = [], None
    for line in text.splitlines():
        marker = re.match(r"^\s*(`{3,}|~{3,})", line)
        if marker:
            current = marker[1][0]
            if fence is None:
                fence = current
            elif fence == current:
                fence = None
            output.append("")
        else:
            output.append(line if fence is None else "")
    return "\n".join(output), fence is not None


def anchors(path):
    text, _ = without_fences(path.read_text(encoding="utf-8"))
    found, counts = set(), {}
    for title in re.findall(r"^#{1,6}\s+(.+?)(?:\s+#+)?$", text, re.M):
        title = re.sub(r"<[^>]+>", "", title)
        title = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", title)
        slug = re.sub(r"[^\w\- ]", "", title.lower()).replace(" ", "-")
        count = counts.get(slug, 0)
        counts[slug] = count + 1
        found.add(f"{slug}-{count}" if count else slug)
    found.update(re.findall(r"\b(?:id|name)=[\"']([^\"']+)[\"']", text))
    return found


def main():
    markdown = sorted(set(ROOT.glob("*.md")) | set((ROOT / "docs").rglob("*.md"))
                      | set((ROOT / ".github").rglob("*.md")))
    errors, links = [], 0
    for path in markdown:
        raw = path.read_text(encoding="utf-8")
        content, unclosed = without_fences(raw)
        relative = path.relative_to(ROOT).as_posix()
        if unclosed:
            errors.append(f"{relative}: unclosed fenced block")
        references = re.findall(r"!?\[[^\]\n]*\]\(([^)\n]+)\)", content)
        references += re.findall(r"\b(?:href|src)=[\"']([^\"']+)[\"']", content)
        for reference in references:
            target = reference.strip().strip("<>")
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc:
                continue
            links += 1
            destination = (path.parent / unquote(parsed.path)).resolve() if parsed.path else path
            if not destination.is_relative_to(ROOT):
                errors.append(f"{relative}: link leaves repository: {target}")
            elif not destination.exists():
                errors.append(f"{relative}: missing local target: {target}")
            elif parsed.fragment and destination.suffix == ".md" and unquote(parsed.fragment) not in anchors(destination):
                errors.append(f"{relative}: missing heading anchor: {target}")
        for diagram in re.findall(r"```mermaid\s*\n(.*?)```", raw, re.S):
            first = diagram.strip().splitlines()[0] if diagram.strip() else ""
            if not first.startswith(("flowchart ", "graph ", "sequenceDiagram", "stateDiagram-v2")):
                errors.append(f"{relative}: unsupported or empty Mermaid block")
    svgs = sorted((ROOT / "docs" / "assets").glob("*.svg"))
    for path in svgs:
        try:
            element = ET.fromstring(path.read_text(encoding="utf-8"))
            namespace = {"svg": "http://www.w3.org/2000/svg"}
            if element.find("svg:title", namespace) is None or element.find("svg:desc", namespace) is None:
                errors.append(f"{path.name}: SVG needs a title and description")
            if "viewBox" not in element.attrib:
                errors.append(f"{path.name}: SVG needs a viewBox")
            if re.search(r"<script\b|\bon\w+\s*=", path.read_text(encoding="utf-8"), re.I):
                errors.append(f"{path.name}: executable SVG content is not allowed")
        except ET.ParseError as error:
            errors.append(f"{path.name}: invalid XML: {error}")
    if errors:
        for error in errors:
            print(error)
        return 1
    print(f"Documentation checks passed: {len(markdown)} Markdown files, {links} local links, {len(svgs)} SVG assets.")
    print("Remote URLs and Mermaid rendering require separate review.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
