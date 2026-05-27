# LLM Wiki Schema

## 구조

- `sources/`: 원본 자료 (논문 PDF, 아티클, 코드). 절대 수정 금지. 읽기 전용.
- `wiki/`: 너가 유지하는 지식 베이스. 마크다운 파일.

## wiki/ 하위 카테고리

- `papers/`: 개별 논문 페이지. 파일명은 `[저자]-[연도]-[키워드].md`
  - 예: `vaswani-2017-attention.md`
- `concepts/`: 개념 페이지 (residual connection, attention, layer norm 등)
- `architectures/`: 모델 아키텍처 (resnet, transformer, gpt 등)
- `notes/`: 임시 메모, 질문, 발견
- `synthesis/`: 여러 출처를 종합한 페이지

## 페이지 규칙

1. **Wikilink로 연결**: `[[concept-name]]` 형식. 다른 페이지 언급 시 항상 사용.
2. **Source attribution**: 각 주장 끝에 `[source: papers/[파일명]]` 또는 `[source: sources/[원본파일]]`
3. **YAML frontmatter** (선택): tags, status (stub/draft/mature)

## 논문 자동 ingest

`ingest.py`로 다양한 형식 → `wiki/papers/` MD 파일 자동 생성.

```bash
cd ~/Desktop/yh/llm-wiki

# 로컬 파일 (.pdf .docx .pptx .xlsx .html .txt .csv .md)
python3 ingest.py path/to/paper.pdf
python3 ingest.py path/to/notes.docx

# arXiv URL
python3 ingest.py https://arxiv.org/abs/1706.03762

# 일반 웹 URL (블로그, 아티클 등)
python3 ingest.py https://some-blog.com/article
```

- 로컬 파일: `sources/`에 자동 복사
- PDF: PyMuPDF(fitz)로 파싱 (수식 추출 정확도 우선)
- 그 외 파일/URL: markitdown으로 변환
- arXiv URL: ar5iv.org HTML 버전 스크래핑 (실패 시 PDF fallback)
- 논문 전문을 Claude에 넘겨 분석 → 30초~2분 소요
- 파일명: `저자-연도-키워드.md`

생성 후 `내 연구 관련성` 섹션은 직접 작성 필요.

## 새 source 수동 ingest 워크플로우

ingest.py 사용 불가한 자료 (블로그, 강의 노트 등):

1. 자료를 읽고 핵심 내용 파악
2. 관련 papers/, concepts/, architectures/ 페이지가 이미 있는지 확인
3. 있으면: 해당 페이지를 업데이트 (새 정보 통합, 모순되면 명시)
4. 없으면: 새 페이지 생성
5. 다른 페이지와 wikilink 연결 추가
6. 변경 사항을 사용자에게 간략히 보고

## ingest 시 추구할 패턴 (학습된 것)

- 단순한 코드 paraphrase X vs "왜 이렇게 했는가"의 디자인 원칙 O
- 일반적 통념 받아쓰기 X vs 통념과 다른 진짜 이유 명시 O
  - 예: weight-tying은 "파라미터 절약"이 아니라 "이론적 정합성"
- 각 페이지에 Open Questions 섹션 (확신 없는 부분 명시)
- paper 페이지는 hub 역할 (다른 concept들의 entry point)

## 톤

- 학술 논문이 아닌 "내 노트" 톤. 1인칭 가능
- 정확성 > 간결함. 정확한 표현 인용은 ""로 표시
- 모순되는 정보는 양쪽 다 기록 + 어느 쪽이 더 신뢰할 만한지 의견
- **수학/ML 전문용어는 영어 원어 그대로 사용** (variance, std, residual, attention, gradient 등). 굳이 한국어로 번역하지 말 것. 한국어 문장 안에 영어 텀을 그대로 박는 자연스러운 공대생 노트 스타일.

## Lint

`lint.py`로 wiki 상태를 점검할 수 있다.

```bash
cd ~/Desktop/yh/llm-wiki

# 체크만
python3 lint.py

# broken wikilink 자동 수정 (링크 해제, 텍스트 보존)
python3 lint.py --fix
```

세 가지 체크:

1. **Broken wikilinks**: `[[target]]` 가리키는 파일 없는 것
2. **Orphaned pages**: 아무도 링크 안 하는 고립된 페이지
3. **Missing source files**: `[source: sources/...]` 참조 중 실제 파일 없는 것

broken wikilink는 주로 아직 ingest 안 된 논문/개념 참조. `--fix`는 `[[slug]]` → `slug` 텍스트로 바꿔준다.

## 절대 금지

- sources/ 디렉토리 수정/삭제 금지
- 기존 wiki 페이지 무단 삭제 금지 (수정 OK, 삭제는 사용자 확인 필요)
- 출처 없이 새로운 사실 주장 금지
