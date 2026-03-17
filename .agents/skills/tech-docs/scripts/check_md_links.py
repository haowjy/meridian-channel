#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urldefrag, urlsplit

MD_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
WIKI_LINK_RE = re.compile(r"@?\[\[([^\]]+)\]\]")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
FENCE_RE = re.compile(r"^\s*```")
INLINE_CODE_RE = re.compile(r"`[^`]*`")

PLACEHOLDER_WIKI_TARGETS = {
    "...",
    "path",
    "url",
    "target",
    "label",
    "name",
    "document",
}


@dataclass(frozen=True)
class LinkRef:
    source_file: str
    line_no: int
    kind: str  # "md" | "wiki"
    raw_target: str


@dataclass(frozen=True)
class BrokenRef:
    source_rel: str
    line_no: int
    raw_target: str
    reason: str


def list_markdown_files(root_dir: str, respect_gitignore: bool = True) -> list[str]:
    """List markdown files under root_dir.

    When respect_gitignore is True (the default), uses `git ls-files` so that
    paths matched by .gitignore are automatically excluded.  Falls back to a
    plain os.walk if git is unavailable or the directory is outside a repo.
    """
    if respect_gitignore:
        try:
            result = subprocess.run(
                ["git", "ls-files", "--cached", "--others", "--exclude-standard", "*.md"],
                cwd=root_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            files = [os.path.join(root_dir, line) for line in result.stdout.splitlines() if line]
            # `git ls-files --cached` can include paths that are deleted in the
            # working tree but still present in the index; only lint files that
            # currently exist on disk.
            files = [path for path in files if os.path.isfile(path)]
            files.sort()
            return files
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass  # fall through to os.walk

    files: list[str] = []
    for dirpath, _, filenames in os.walk(root_dir):
        for name in filenames:
            if name.lower().endswith(".md"):
                files.append(os.path.join(dirpath, name))
    files.sort()
    return files


def is_external(target: str) -> bool:
    parsed = urlsplit(target)
    if parsed.scheme and parsed.scheme not in {"", "file"}:
        return True
    if "://" in target:
        return True
    return target.startswith(("mailto:", "tel:", "data:"))


def clean_md_target(target: str) -> str:
    target = target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1].strip()
    # Drop optional title in markdown link: (path "title")
    if " " in target and not target.startswith("#"):
        target = target.split(" ", 1)[0]
    return target.strip()


def extract_links(file_path: str, include_wikilinks: bool) -> list[LinkRef]:
    refs: list[LinkRef] = []
    with open(file_path, encoding="utf-8") as f:
        in_fence = False
        for line_no, line in enumerate(f, start=1):
            if FENCE_RE.match(line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue

            # Ignore inline code spans to avoid false positives from syntax examples.
            scan_line = INLINE_CODE_RE.sub("", line)

            for match in MD_LINK_RE.finditer(scan_line):
                target = clean_md_target(match.group(1))
                if target:
                    refs.append(
                        LinkRef(
                            source_file=file_path,
                            line_no=line_no,
                            kind="md",
                            raw_target=target,
                        )
                    )

            if include_wikilinks:
                for match in WIKI_LINK_RE.finditer(scan_line):
                    target = match.group(1).split("|", 1)[0].strip()
                    if not target:
                        continue
                    if target.lower() in PLACEHOLDER_WIKI_TARGETS:
                        continue
                    refs.append(
                        LinkRef(
                            source_file=file_path,
                            line_no=line_no,
                            kind="wiki",
                            raw_target=target,
                        )
                    )

    return refs


def resolve_candidate_paths(ref: LinkRef, repo_root: str) -> tuple[list[str], str]:
    target = ref.raw_target
    path_part, frag = urldefrag(target)
    path_part = path_part.split("?", 1)[0].strip()
    source_dir = os.path.dirname(ref.source_file)

    # Fragment-only links point to current file.
    if path_part == "":
        return [ref.source_file], frag

    candidates: list[str] = []
    if path_part.startswith("/"):
        base = os.path.join(repo_root, path_part.lstrip("/"))
    else:
        base = os.path.normpath(os.path.join(source_dir, path_part))
    candidates.append(base)

    if ref.kind == "wiki":
        # Wiki links can omit extension and can point to folder README.
        _root, ext = os.path.splitext(base)
        if ext == "":
            candidates.append(base + ".md")
            candidates.append(os.path.join(base, "README.md"))

    return candidates, frag


def is_markdown_path(path: str) -> bool:
    return path.lower().endswith(".md")


def github_slug(text: str) -> str:
    s = text.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE)
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")


@lru_cache(maxsize=1024)
def heading_anchors(file_path: str) -> set[str]:
    anchors: set[str] = set()
    counts: dict[str, int] = {}
    with open(file_path, encoding="utf-8") as f:
        for line in f:
            m = HEADING_RE.match(line)
            if not m:
                continue
            base = github_slug(m.group(2))
            if not base:
                continue
            n = counts.get(base, 0)
            anchor = base if n == 0 else f"{base}-{n}"
            counts[base] = n + 1
            anchors.add(anchor)
    return anchors


def check_ref(ref: LinkRef, root_dir: str, repo_root: str, check_anchors: bool) -> BrokenRef | None:
    target = ref.raw_target
    if is_external(target):
        return None

    candidates, frag = resolve_candidate_paths(ref, repo_root)

    # For regular markdown links, only validate .md targets or fragment-only links.
    if ref.kind == "md":
        path_part, _ = urldefrag(target)
        path_part = path_part.split("?", 1)[0].strip()
        if path_part and not path_part.lower().endswith(".md"):
            return None

    existing_md = next((p for p in candidates if os.path.isfile(p) and is_markdown_path(p)), None)
    if existing_md is None:
        return BrokenRef(
            source_rel=os.path.relpath(ref.source_file, root_dir),
            line_no=ref.line_no,
            raw_target=target,
            reason="missing target",
        )

    if check_anchors and frag:
        anchors = heading_anchors(existing_md)
        if frag not in anchors:
            return BrokenRef(
                source_rel=os.path.relpath(ref.source_file, root_dir),
                line_no=ref.line_no,
                raw_target=target,
                reason=f"missing anchor #{frag}",
            )

    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check markdown links and wiki-links for local docs."
    )
    parser.add_argument(
        "root",
        nargs="?",
        default="_docs",
        help="Directory to scan (default: _docs)",
    )
    parser.add_argument(
        "--no-wikilinks",
        action="store_true",
        help="Disable wiki-link checks.",
    )
    parser.add_argument(
        "--no-anchors",
        action="store_true",
        help="Skip anchor existence checks for #fragment links.",
    )
    parser.add_argument(
        "--no-gitignore",
        action="store_true",
        help="Don't respect .gitignore (scan all .md files including ignored ones).",
    )
    args = parser.parse_args()

    root_dir = os.path.abspath(args.root)
    repo_root = os.path.abspath(
        os.popen("git rev-parse --show-toplevel 2>/dev/null").read().strip() or os.getcwd()
    )

    if not os.path.isdir(root_dir):
        print(f"error: directory not found: {args.root}", file=sys.stderr)
        return 2

    md_files = list_markdown_files(root_dir, respect_gitignore=not args.no_gitignore)
    if not md_files:
        print(f"no markdown files found under {args.root}")
        return 0

    include_wikilinks = not args.no_wikilinks
    check_anchors = not args.no_anchors

    broken: list[BrokenRef] = []
    for md_file in md_files:
        refs = extract_links(md_file, include_wikilinks=include_wikilinks)
        for ref in refs:
            issue = check_ref(
                ref, root_dir=root_dir, repo_root=repo_root, check_anchors=check_anchors
            )
            if issue is not None:
                broken.append(issue)

    if broken:
        for issue in broken:
            print(
                f"broken: {issue.source_rel}:{issue.line_no} -> {issue.raw_target} ({issue.reason})"
            )
        return 1

    mode = "markdown + wikilinks" if include_wikilinks else "markdown only"
    anchors = "anchors on" if check_anchors else "anchors off"
    print(f"OK: checked {len(md_files)} markdown files under {args.root} ({mode}, {anchors})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
