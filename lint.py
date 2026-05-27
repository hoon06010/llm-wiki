#!/usr/bin/env python3
"""
llm-wiki lint
Usage: python lint.py [--fix]

Checks:
  1. Broken wikilinks  — [[target]] 가리키는 파일 없음
  2. Orphaned pages    — 아무도 링크 안 하는 페이지
  3. Missing sources   — [source: sources/...] 가리키는 파일 없음
"""

import re
import sys
from pathlib import Path

WIKI_ROOT = Path(__file__).parent
WIKI_DIR = WIKI_ROOT / "wiki"
SOURCES_DIR = WIKI_ROOT / "sources"

WIKILINK_RE = re.compile(r'\[\[([^\]|#\n]+?)(?:\|[^\]]*)?\]\]')
SOURCE_REF_RE = re.compile(r'\[source:\s*(sources/[^\]]+?)\s*(?:,\s*[^\]]*)?\]')


EXCLUDE_SLUGS = {"log", "index", "readme"}


def collect_wiki_pages() -> dict[str, Path]:
    """slug → path 매핑. slug는 파일명(확장자 제외), 소문자."""
    pages: dict[str, Path] = {}
    for md in WIKI_DIR.rglob("*.md"):
        slug = md.stem.lower()
        if slug not in EXCLUDE_SLUGS:
            pages[slug] = md
    return pages


def normalize_slug(raw: str) -> str:
    return raw.strip().lower().replace(" ", "-").replace("_", "-")


def extract_wikilinks(text: str) -> list[str]:
    return [normalize_slug(m) for m in WIKILINK_RE.findall(text)]


def extract_source_refs(text: str) -> list[str]:
    return [m.strip() for m in SOURCE_REF_RE.findall(text)]


# ── checks ────────────────────────────────────────────────────────────────────

def check_broken_wikilinks(pages: dict[str, Path]) -> list[tuple[Path, str]]:
    """(page, broken_slug) 목록 반환."""
    broken: list[tuple[Path, str]] = []
    for path in pages.values():
        text = path.read_text(encoding="utf-8")
        for slug in extract_wikilinks(text):
            if slug not in pages:
                broken.append((path, slug))
    return broken


def check_orphaned_pages(pages: dict[str, Path]) -> list[Path]:
    """링크 받는 곳이 없는 페이지 목록. CLAUDE.md 및 index류 제외."""
    incoming: dict[str, int] = {slug: 0 for slug in pages}
    for path in pages.values():
        text = path.read_text(encoding="utf-8")
        for slug in extract_wikilinks(text):
            if slug in incoming:
                incoming[slug] += 1

    return [
        pages[slug]
        for slug, count in incoming.items()
        if count == 0
    ]


def check_missing_sources(pages: dict[str, Path]) -> list[tuple[Path, str]]:
    """[source: sources/...] 참조 중 실제 파일 없는 것."""
    missing: list[tuple[Path, str]] = []
    for path in pages.values():
        text = path.read_text(encoding="utf-8")
        for ref in extract_source_refs(text):
            # ref = "sources/paper.pdf" 형태
            target = WIKI_ROOT / ref
            if not target.exists():
                missing.append((path, ref))
    return missing


# ── fix ───────────────────────────────────────────────────────────────────────

def fix_broken_wikilinks(pages: dict[str, Path], broken: list[tuple[Path, str]]) -> int:
    """[[broken-slug]] → broken-slug (링크 해제, 텍스트 보존). 수정 파일 수 반환."""
    by_page: dict[Path, set[str]] = {}
    for path, slug in broken:
        by_page.setdefault(path, set()).add(slug)

    fixed = 0
    for path, slugs in by_page.items():
        text = path.read_text(encoding="utf-8")
        original = text

        def replacer(m: re.Match) -> str:
            raw = m.group(1)
            display = m.group(0)  # 전체 [[...]]
            if normalize_slug(raw) in slugs:
                # 표시 텍스트만 남기기: [[slug|alias]] → alias, [[slug]] → slug
                alias_match = re.match(r'\[\[([^\]|]+)\|([^\]]+)\]\]', display)
                return alias_match.group(2) if alias_match else raw
            return display

        text = WIKILINK_RE.sub(replacer, text)
        if text != original:
            path.write_text(text, encoding="utf-8")
            fixed += 1
    return fixed


# ── reporting ─────────────────────────────────────────────────────────────────

def rel(path: Path) -> str:
    return str(path.relative_to(WIKI_ROOT))


def main() -> None:
    fix_mode = "--fix" in sys.argv

    if not WIKI_DIR.exists():
        print("wiki/ 디렉토리 없음.")
        sys.exit(1)

    pages = collect_wiki_pages()
    print(f"wiki 페이지 {len(pages)}개 스캔\n")

    broken = check_broken_wikilinks(pages)
    orphans = check_orphaned_pages(pages)
    missing_src = check_missing_sources(pages)

    has_issue = bool(broken or orphans or missing_src)

    # ── 1. broken wikilinks ──
    if broken:
        print(f"[1] Broken wikilinks ({len(broken)}개)")
        for path, slug in sorted(broken, key=lambda x: (str(x[0]), x[1])):
            print(f"    {rel(path)}  →  [[{slug}]]")
        if fix_mode:
            fixed = fix_broken_wikilinks(pages, broken)
            print(f"    → {fixed}개 파일 수정됨 (링크 해제)\n")
        else:
            print()
    else:
        print("[1] Broken wikilinks: 없음")

    # ── 2. orphaned pages ──
    if orphans:
        print(f"\n[2] Orphaned pages ({len(orphans)}개) — 아무도 링크 안 함")
        for path in sorted(orphans):
            print(f"    {rel(path)}")
        print()
    else:
        print("[2] Orphaned pages: 없음")

    # ── 3. missing source files ──
    if missing_src:
        print(f"\n[3] Missing source files ({len(missing_src)}개)")
        for path, ref in sorted(missing_src, key=lambda x: (str(x[0]), x[1])):
            print(f"    {rel(path)}  →  {ref}")
        print()
    else:
        print("[3] Missing source files: 없음")

    # ── summary ──
    print()
    if has_issue:
        total = len(broken) + len(orphans) + len(missing_src)
        if not fix_mode:
            print(f"총 {total}개 문제 발견. 자동 수정: python lint.py --fix (broken wikilink만)")
        sys.exit(1)
    else:
        print("모든 체크 통과.")


if __name__ == "__main__":
    main()
