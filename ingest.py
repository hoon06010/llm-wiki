#!/usr/bin/env python3
"""
논문 ingest 스크립트
Usage:
  python ingest.py paper.pdf
  python ingest.py paper.docx / .pptx / .xlsx / .html / .txt / .md
  python ingest.py https://arxiv.org/abs/2301.00234
  python ingest.py https://some-blog.com/article
"""

import sys
import re
import subprocess
import shutil
import json
import hashlib
from pathlib import Path
from datetime import date

WIKI_DIR = Path(__file__).parent / "wiki" / "papers"
SOURCES_DIR = Path(__file__).parent / "sources"
CACHE_FILE = Path(__file__).parent / "ingest_cache.json"
LOG_FILE = Path(__file__).parent / "wiki" / "log.md"

PROMPT_TEMPLATE = """\
너는 딥러닝 연구 논문을 분석해서 Obsidian wiki MD 파일을 생성하는 AI야.

아래 논문 전문을 읽고, 지정된 형식의 Markdown을 출력해줘.
Markdown 블록 없이 frontmatter부터 바로 시작해.

## 작성 규칙
- 요약/분석/설명은 한국어로
- 전문 용어, 모델명, 수식, 벤치마크명은 영어 원어 그대로
- 공대생 노트 스타일: 정확성 > 간결함, 1인칭 가능
- 약어 자유롭게: random variable → RV, neural network → NN, ground truth → GT 등
- 각 주장 끝에 [source: {source_ref}] 표기
- 다른 개념/논문 언급 시 [[wikilink]] 사용
- Open Questions: 논문에서 설명 안 된 것, 내가 의문인 것

## 출력 형식

---
title: "[논문 제목 원문]"
authors: [성 et al.] 또는 [성1, 성2] (3명 이상은 et al.)
year: YYYY
tags: [paper, 태그1, 태그2, ...]
relevance: 높음/중간/낮음
added: {today}
status: draft
---

# [논문 제목] ([저자 성], [연도])

## 한 줄 요약
[한 문장. 핵심 contribution + 결과]

[source: {source_ref}]

## 왜 이 논문이 나왔나
[선행 연구의 한계, 이 논문의 동기]

## 핵심 기여
1. ...
2. ...
3. ...

## 방법론
[상세 설명. 수식, 하이퍼파라미터, 설계 결정의 이유 포함]

## 실험 결과
[수치 포함. 표 형식 권장]

## 한계점 / 비판
- ...

## 내 연구 관련성
[직접 작성 예정]

## 인용하는 주요 논문
- [[논문 wikilink]]

## 데이터셋 / 벤치마크
- ...

## 관련 페이지
- [[관련 개념 wikilink]]

## Open Questions
- ...

---

## 논문 전문

{text}
"""


def is_url(arg: str) -> bool:
    return arg.startswith("http://") or arg.startswith("https://")


def extract_arxiv_id(url: str) -> str | None:
    match = re.search(r'arxiv\.org/(?:abs|pdf)/(\d+\.\d+)', url)
    return match.group(1) if match else None


def fetch_web_text(url: str) -> tuple[str, str]:
    """일반 웹 URL에서 텍스트 추출 (markitdown 사용)."""
    from markitdown import MarkItDown
    print(f"웹 페이지 가져오는 중: {url}")
    md = MarkItDown()
    result = md.convert_url(url)
    return result.text_content, f"url:{url}"


def fetch_arxiv_text(arxiv_id: str) -> tuple[str, str]:
    """ar5iv.org에서 HTML 버전 가져오기. 실패 시 PDF fallback."""
    import requests
    from bs4 import BeautifulSoup

    ar5iv_url = f"https://ar5iv.org/abs/{arxiv_id}"
    print(f"ar5iv.org 가져오는 중: {ar5iv_url}")
    try:
        resp = requests.get(ar5iv_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer", "figure"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        if len(text) > 2000:
            return text, f"arxiv:{arxiv_id} (ar5iv HTML)"
    except Exception as e:
        print(f"ar5iv 실패: {e}")

    # fallback: PDF 다운로드
    import tempfile, os
    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"
    print(f"PDF fallback: {pdf_url}")
    resp = requests.get(pdf_url, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(resp.content)
        tmp_path = f.name
    try:
        text = extract_pdf_text(tmp_path)
    finally:
        os.unlink(tmp_path)
    return text, f"arxiv:{arxiv_id} (PDF)"


# ── cache & log ───────────────────────────────────────────────────────────────

def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def load_cache() -> dict:
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    return {}


def save_cache(cache: dict) -> None:
    CACHE_FILE.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")


def check_duplicate(key: str) -> str | None:
    """이미 처리된 항목이면 출력 파일명 반환, 아니면 None."""
    return load_cache().get(key)


def record_cache(key: str, output_path: Path) -> None:
    cache = load_cache()
    root = Path(__file__).parent
    rel = output_path.relative_to(root) if output_path.is_absolute() else output_path
    cache[key] = str(rel)
    save_cache(cache)


def append_log(today: str, source_ref: str, output_path: Path) -> None:
    root = Path(__file__).parent
    rel_out = str(output_path.relative_to(root) if output_path.is_absolute() else output_path)
    row = f"| {today} | {source_ref} | {rel_out} |\n"
    if not LOG_FILE.exists():
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        LOG_FILE.write_text(
            "# Ingest Log\n\n| 날짜 | 입력 | 출력 |\n|------|------|------|\n" + row,
            encoding="utf-8",
        )
    else:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(row)


# markitdown으로 변환 가능한 확장자 (.pdf 제외 — fitz가 수식 추출에 더 정확)
MARKITDOWN_EXTS = {".docx", ".pptx", ".xlsx", ".html", ".htm", ".txt", ".csv", ".md"}


def extract_pdf_text(pdf_path: str) -> str:
    import fitz
    doc = fitz.open(pdf_path)
    pages = [page.get_text() for page in doc]
    return "\n".join(pages)


def extract_with_markitdown(file_path: str) -> str:
    from markitdown import MarkItDown
    md = MarkItDown()
    result = md.convert(file_path)
    return result.text_content


def call_claude(prompt: str) -> str:
    result = subprocess.run(
        ["claude", "--print"],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        print(f"Claude 오류:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def parse_filename_from_md(md: str) -> str:
    author_match = re.search(r'authors:\s*\[([^\]]+)\]', md)
    year_match = re.search(r'year:\s*(\d{4})', md)
    title_match = re.search(r'title:\s*"([^"]+)"', md)

    year = year_match.group(1) if year_match else "unknown"

    # authors 필드: "[Vaswani et al.]" 또는 "Vaswani et al." 둘 다 처리
    author_raw_match = re.search(r'authors:\s*\[?([^\]\n]+)', md)
    if author_raw_match:
        raw = author_raw_match.group(1).split(',')[0].strip().rstrip(']')
        first_author = raw.split()[0].lower().rstrip('.')
    else:
        first_author = "unknown"

    if title_match:
        # 제목에서 첫 번째 의미있는 단어
        words = re.sub(r'[^a-zA-Z0-9 ]', '', title_match.group(1)).lower().split()
        stop = {"a", "an", "the", "of", "in", "on", "for", "with", "and", "is", "are"}
        keywords = [w for w in words if w not in stop]
        keyword = keywords[0] if keywords else "paper"
    else:
        keyword = "paper"

    return f"{first_author}-{year}-{keyword}"


def save_md(md: str, base_name: str) -> Path:
    WIKI_DIR.mkdir(parents=True, exist_ok=True)
    output = WIKI_DIR / f"{base_name}.md"
    counter = 1
    while output.exists():
        output = WIKI_DIR / f"{base_name}-{counter}.md"
        counter += 1
    output.write_text(md, encoding="utf-8")
    return output


def main():
    if len(sys.argv) < 2:
        print("Usage: python ingest.py <file_or_url>")
        print("  파일: .pdf .docx .pptx .xlsx .html .txt .csv .md")
        print("  URL:  arXiv URL 또는 일반 웹 URL")
        sys.exit(1)

    arg = sys.argv[1]
    today = date.today().isoformat()
    arxiv_id = extract_arxiv_id(arg)
    cache_key: str

    if arxiv_id:
        cache_key = f"arxiv:{arxiv_id}"
        prev = check_duplicate(cache_key)
        if prev:
            print(f"이미 처리됨: {prev}")
            sys.exit(0)
        text, source_ref = fetch_arxiv_text(arxiv_id)
    elif is_url(arg):
        cache_key = f"url:{arg}"
        prev = check_duplicate(cache_key)
        if prev:
            print(f"이미 처리됨: {prev}")
            sys.exit(0)
        text, source_ref = fetch_web_text(arg)
    else:
        file_path = Path(arg)
        if not file_path.exists():
            print(f"파일 없음: {file_path}")
            sys.exit(1)

        cache_key = file_hash(file_path)
        prev = check_duplicate(cache_key)
        if prev:
            print(f"이미 처리됨 (동일 파일): {prev}")
            sys.exit(0)

        ext = file_path.suffix.lower()
        # sources/에 복사 (이미 sources/ 안에 있으면 생략)
        # resolve()로 절대경로 변환 후 비교 — 상대경로 인수에서도 올바르게 동작
        try:
            file_path.resolve().relative_to(SOURCES_DIR)
            dest = file_path.resolve()
        except ValueError:
            dest = SOURCES_DIR / file_path.name
            if not dest.exists():
                SOURCES_DIR.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file_path, dest)
                print(f"복사: sources/{file_path.name}")
        source_ref = f"sources/{dest.relative_to(SOURCES_DIR)}"

        if ext == ".pdf":
            print(f"PDF 파싱 중: {file_path.name}")
            text = extract_pdf_text(str(file_path))
        elif ext in MARKITDOWN_EXTS:
            print(f"markitdown 변환 중: {file_path.name} ({ext})")
            text = extract_with_markitdown(str(file_path))
        else:
            print(f"지원하지 않는 형식: {ext}")
            print(f"지원 형식: .pdf {' '.join(sorted(MARKITDOWN_EXTS))}")
            sys.exit(1)

    char_count = len(text)
    print(f"텍스트 추출 완료 ({char_count:,}자, ~{char_count//4:,} 토큰 추정)")

    # 너무 길면 앞부분 위주로 (Claude 200k 컨텍스트 기준 안전하게 400k자)
    MAX_CHARS = 400_000
    if char_count > MAX_CHARS:
        text = text[:MAX_CHARS]
        print(f"텍스트 길이 제한 적용 ({MAX_CHARS:,}자)")

    prompt = PROMPT_TEMPLATE.format(source_ref=source_ref, today=today, text=text)

    print("Claude 분석 중... (30초~2분 소요)")
    md = call_claude(prompt)

    base_name = parse_filename_from_md(md)
    output_path = save_md(md, base_name)

    record_cache(cache_key, output_path)
    append_log(today, source_ref, output_path)

    print(f"\n완료: {output_path}")
    print(f"Obsidian에서 wiki/papers/{output_path.name} 확인하세요.")


if __name__ == "__main__":
    main()
