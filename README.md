# LLM Wiki

LLM / Deep Learning 논문과 개념을 정리하는 개인 지식 베이스.

## 구조

```
sources/   # 원본 자료 (논문 PDF, 코드 등) — 읽기 전용
wiki/
  papers/        # 논문 페이지 (저자-연도-키워드.md)
  concepts/      # 개념 페이지 (attention, residual 등)
  architectures/ # 모델 아키텍처 (transformer, gpt 등)
  notes/         # 임시 메모, 질문
  synthesis/     # 여러 출처 종합 페이지
```

## 세팅

**1. Python 패키지 설치**
```bash
pip install -r requirements.txt
```

**2. Claude Code CLI 설치**

`ingest.py`는 논문 분석에 `claude --print`를 사용합니다.
설치: https://claude.ai/code

## 논문 ingest

```bash
# 로컬 파일
python3 ingest.py path/to/paper.pdf

# arXiv URL
python3 ingest.py https://arxiv.org/abs/1706.03762

# 일반 웹 URL
python3 ingest.py https://some-blog.com/article
```

## Lint

```bash
python3 lint.py        # 상태 체크
python3 lint.py --fix  # broken wikilink 자동 수정
```
