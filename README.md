# 내규챗봇

우체국금융개발원 내규를 근거 조문과 함께 답하는 챗봇. 답은 미리 만들어 검증해 두고, 직원 PC에서는 찾아서 보여주기만 한다(서버·고사양 PC 불필요).

## 폴더 역할

| 무엇 | 위치 |
|---|---|
| 프로그램 코드 | 이 폴더 (`~/Projects/naegyu-chatbot`, git으로 관리) |
| 내규 원본 (hwp, hwpx, xlsx) | iCloud `내규챗봇` 폴더 |
| 변환본, 규정 DB | `data/` (git에 올리지 않음, 원본에서 다시 만든다) |
| 문답 카드 | `knowledge/<분야>/*.json` — 지금은 `birth_childcare`(출산·육아), `service`(복무·휴가) |
| 검증 결과 | `reports/` |
| 시범본 | `dist/index.html` (그대로 열면 됨, 인터넷 없이 동작) |

내규 원본의 기준은 ALIO가 아니라 iCloud 폴더의 파일이다. ALIO 게시본은 실제 시행본보다 늦을 때가 있다(예: 위임전결세칙).

## 만드는 순서

```bash
scripts/convert.sh                   # 1. 한글 원본 → data/md (kordoc)
python3 scripts/build_db.py          # 2. 조문 단위 규정 DB → data/rules.json
python3 scripts/check_knowledge.py   # 3. 문답 카드 프로그램 검사 → reports/check_report.md
python3 scripts/blind_check.py [분야]      # 4. 독립 검증(로컬 ollama qwen3.5:35b) → reports/blind_check.md
python3 scripts/check_approval_table.py    #    위임전결기준 표의 ○ 칸과 카드 전결권자 대조 → reports/approval_table_check.md
python3 scripts/check_changes.py           #    규정 개정 감지 → reports/change_report.md (아래 '규정이 개정되면')
node scripts/test_engine.js -v       # 5. 검색·계산기 시험
python3 scripts/build_web.py         # 6. 시범본 묶기 → dist/
```

## 규정이 개정되면

1. 개정된 한글 원본을 내규 폴더에 넣고 `scripts/convert.sh`, `python3 scripts/build_db.py` 를 다시 돌린다.
2. `python3 scripts/check_changes.py` → `reports/change_report.md`
   - 카드를 확인한 시점의 조문·항·별표·부칙 원문 지문(`knowledge/source_snapshot.json`)과 새 원문을 비교한다.
   - **다시 확인할 카드**: 인용한 조(항까지 적었으면 그 항)가 바뀌었거나 없어진 카드. 바뀐 글자를 diff 로 보여 준다.
   - **참고 카드**: 같은 조의 다른 항만 바뀐 카드. **새 조문**: 카드가 없을 수 있는 신설 조문.
   - 인용 문구가 그대로 남는 개정(예: 같은 항에 "다만, 수습 직원은 10일" 추가)도 잡는다. `check_knowledge.py` 만으로는 못 잡는다.
3. 다시 확인할 카드를 새 원문에 맞게 고치고 `check_knowledge.py`(오류 0건), `blind_check.py <카드 id…>` 로 검증한다. 필요하면 새 조문 카드를 만든다.
4. 그 규정의 카드를 다 확인했으면 `python3 scripts/check_changes.py --accept <규정명>` 으로 지문을 갱신한다.
5. `python3 scripts/build_web.py` 로 묶는다. 아직 확인 못 한 카드는 화면에 **"규정 개정 · 재검수 전"**과 바뀐 조문이 표시되고, 위 안내 줄에 그 개수가 나온다. 화면을 만든 지 90일이 지나면 "최신판인지 확인하세요" 안내가 뜬다.

미리 보기: `python3 scripts/check_changes.py --rules <개정본 rules.json>`, `python3 scripts/build_web.py --rules <개정본> --out <폴더>` 는 실제 결과 파일을 건드리지 않는다.

## 분야 추가하기

`knowledge/<새 분야>/` 폴더에 `_topics.json`(분야 이름·주제), 카드 파일, `_devset.json`(시험 질문)을 만들면 모든 스크립트가 함께 읽는다. 카드를 넣은 뒤에는 `node scripts/calibrate.js`로 기준값을 다시 확인한다.

## 문답 카드 형식

카드 하나 = 답의 칸 하나. `facts` 의 `cite`(조문 위치)와 `quote`(원문 그대로의 문구)는 3번 검사에서 원문과 대조된다. `questions` 는 직원이 칠 법한 예상 질문, `check` 는 담당부서가 확인할 점이다. `_devset.json` 의 시험 질문은 카드에 옮겨 넣지 않는다.

## 인터넷망 AI 보조(선택)

`python3 scripts/export_gpts.py` → `dist/gpts/`. ChatGPT GPTs(또는 프로젝트)를 만들어 `지시문.md` 내용을 지침 칸에 붙여 넣고, 나머지 `카드_*.md`와 `조문_원문.md`(13개 안팎, 20개 한도)를 지식 파일로 올린다. 카드 근거로만 답하고 카드 ID·조문을 밝히게 되어 있어, 조건이 여러 개인 질문이나 이어 묻기를 이 시범본보다 잘 다룬다. 인터넷망 전용이며 폐쇄망은 이 시범본(dist/index.html)을 쓴다. 직원 질문에 개인정보·비공개 정보를 넣지 않도록 첫 인사에서 안내한다(인공지능전환관리세칙 제29조제2항). 운영 전에 정보보안 검토를 받는다(reports/governance).

## 담당부서 검수

`python3 scripts/review_workbook.py export` → `reports/review/검수표_<분류>.xlsx`(11개). 소관부서가 카드마다 판정(정확/수정 필요/삭제)·검수부서·검수일을 적어 돌려주면 `python3 scripts/review_workbook.py import reports/review/*.xlsx` 로 반영한다. '정확' 카드는 화면에 "담당부서 검수 완료 · 날짜 · 부서"로 표시되고, 카드 내용이 나중에 바뀌면 자동으로 "검수 전"으로 돌아간다. 수정 요청은 `reports/review/수정요청.md` 에 모인다.

## 운영 설정

`knowledge/site.json`: 오류 신고를 받을 운영부서(dept)·메일(email)·창구(channel), 오래된 판 안내 기준일 수(maxAgeDays). 채운 뒤 다시 묶는다.
