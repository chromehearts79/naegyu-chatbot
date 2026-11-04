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

내규 원본의 기준은 ALIO가 아니라 iCloud 폴더의 파일이다. ALIO 게시는 시행일보다 약 1주 늦다. ALIO ZIP에는 개정 이력이 함께 들어 있어 파일 이름의 가장 최근 일자를 현행본으로 읽어야 한다(맨 앞 항목은 옛 판). 2025년 10월 이후 개정분의 현행본은 내부 원본과 파일이 같다.

## 만드는 순서

```bash
scripts/convert.sh                   # 1. 한글 원본 → data/md (kordoc)
python3 scripts/build_db.py          # 2. 조문 단위 규정 DB → data/rules.json
python3 scripts/check_knowledge.py   # 3. 문답 카드 프로그램 검사 → reports/check_report.md
python3 scripts/blind_check.py [분야]      # 4. 독립 검증(로컬 ollama qwen3.5:35b) → reports/blind_check.md
python3 scripts/check_approval_table.py    #    위임전결기준 표의 ○ 칸과 카드 전결권자 대조 → reports/approval_table_check.md
python3 scripts/check_changes.py           #    규정 개정 감지 → reports/change_report.md (아래 '규정이 개정되면')
node scripts/test_engine.js -v       # 5. 검색·계산기 시험
python3 scripts/build_forms.py <규정명…> | --check   #    서식 대장(별지 번호·제목·부르는 조문) → knowledge/forms.json
node scripts/cut_forms.cjs                 #    원본 .hwp·.hwpx 에서 별지 한 장씩 떼기 → data/forms (npm i --no-save jsdom@24.1.3 cfb@1.2.2)
python3 scripts/check_forms.py             #    떼어 낸 양식이 원본 별지와 같은지 검사
python3 scripts/build_web.py         # 6. 시범본 묶기 → dist/ (양식은 압축해 싣는다)
```

## 규정이 개정되면 (쉬운 안내: docs/유지보수_안내.md)

가장 쉬운 방법: Claude 에게 개정본 파일을 주며 "내규 개정 반영해줘" → 단계마다 버튼(스킬 `skills/naegyu-update`, 설치 위치 `~/.claude/skills/naegyu-update`).
도구: `python3 scripts/update_rules.py status | convert | finish <규정명…>` — 바뀐 파일만 골라 변환·비교하고, 승인 뒤 새 판을 만든다.

아래는 그 안에서 일어나는 일이다.

1. 개정된 한글 원본을 내규 폴더에 넣고 `scripts/convert.sh`, `python3 scripts/build_db.py` 를 다시 돌린다.
2. `python3 scripts/check_changes.py` → `reports/change_report.md`
   - 카드를 확인한 시점의 조문·항·별표·부칙 원문 지문(`knowledge/source_snapshot.json`)과 새 원문을 비교한다.
   - **다시 확인할 카드**: 인용한 조(항까지 적었으면 그 항)가 바뀌었거나 없어진 카드. 바뀐 글자를 diff 로 보여 준다.
   - **참고 카드**: 같은 조의 다른 항만 바뀐 카드. **새 조문**: 카드가 없을 수 있는 신설 조문.
   - 인용 문구가 그대로 남는 개정(예: 같은 항에 "다만, 수습 직원은 10일" 추가)도 잡는다. `check_knowledge.py` 만으로는 못 잡는다.
   - **다시 확인할 계산기**: 계산기 숫자의 근거 조문(`knowledge/calc_basis.json`)이 바뀐 계산기. 숫자는 `web/engine.js` 안에 있어 카드만 고쳐서는 바뀌지 않는다.
3. 다시 확인할 카드를 새 원문에 맞게 고치고 `check_knowledge.py`(오류 0건), `blind_check.py <카드 id…>` 로 검증한다. 필요하면 새 조문 카드를 만든다.
   다시 확인할 계산기가 있으면 `web/engine.js` 의 그 계산기 숫자와 `knowledge/calc_basis.json` 의 근거 문구(has)를 새 원문대로 고친다. 근거 문구가 원문에서 사라지면 `check_knowledge.py` 가 오류로 알린다.
4. 그 규정의 카드를 다 확인했으면 `python3 scripts/check_changes.py --accept <규정명>` 으로 지문을 갱신한다.
5. `python3 scripts/build_web.py` 로 묶는다. 아직 확인 못 한 카드는 화면에 **"규정 개정 · 재검수 전"**과 바뀐 조문이 표시되고, 위 안내 줄에 그 개수가 나온다. 근거 조문이 바뀐 계산기는 숫자를 고칠 때까지 계산하지 않는다. 화면을 만든 지 90일이 지나면 "최신판인지 확인하세요" 안내가 뜬다.

미리 보기: `python3 scripts/check_changes.py --rules <개정본 rules.json>`, `python3 scripts/build_web.py --rules <개정본> --out <폴더>` 는 실제 결과 파일을 건드리지 않는다.

## 분야 추가하기

`knowledge/<새 분야>/` 폴더에 `_topics.json`(분야 이름·주제), 카드 파일, `_devset.json`(시험 질문)을 만들면 모든 스크립트가 함께 읽는다. 카드를 넣은 뒤에는 `node scripts/calibrate.js`로 기준값을 다시 확인한다.

## 문답 카드 형식

카드 하나 = 답의 칸 하나. `facts` 의 `cite`(조문 위치)와 `quote`(원문 그대로의 문구)는 3번 검사에서 원문과 대조된다. `questions` 는 직원이 칠 법한 예상 질문, `check` 는 담당부서가 확인할 점이다. `_devset.json` 의 시험 질문은 카드에 옮겨 넣지 않는다.

## 매주 ALIO 확인 (쉬운 안내: docs/유지보수_안내.md)

ALIO의 우리 내규가 배포한 판과 달라졌는지 매주 확인하는 루틴이다. AI와 외부 전송 없이 ALIO와 `release_url` 에만 접속한다. 윈도우 이전 뒤에 시작한다(맥 자동 실행은 없다).

```bash
python3 -X utf8 scripts/watch_alio.py --config 설정.json [--force]   # 한 번 확인(작업 스케줄러가 부른다)
python3 -X utf8 scripts/alio_confirm.py --config 설정.json            # 담당자 '확인함'(확인함.bat)
python -X utf8 scripts/install_watch.py --mode full|alert [--repo 폴더] [--url 주소] [--dry-run]   # 작업 스케줄러 등록
python -X utf8 scripts/install_watch.py --pack 부담당.zip              # 부 담당 PC용 묶음
python3 -X utf8 scripts/test_watch_alio.py                             # 시험
```

- `scripts/alio_types.py`(판정 이름·자료 꼴), `alio_client.py`(ALIO 접속), `alio_pick.py`(현행 묶음 고르기), `alio_release.py`(기록·배포판 목록), `alio_report.py`(결과 화면·기록), `watch_alio.py`(판정과 실행), `alio_compare.py`(정 담당 PC의 원문 비교), `alio_confirm.py`(확인함), `install_watch.py`(설치). 앞의 다섯과 `watch_alio.py`, `install_watch.py` 는 저장소 없이도 돈다(부 담당 PC).
- `knowledge/alio_seen.json`: 배포한 판을 만들 때 ALIO에서 본 값(게시일·목록 날짜·최신 첨부)과 담당자 확인함 기록. `update_rules.py finish` 가 올린다.
- `dist/release.json`: 내규별 이름·ALIO 값·원본 지문을 담은 배포판 목록. 새 판과 함께 만들어 배포하며, 공개 내규의 이름·날짜·지문만 들어 있다. 설정의 `release_url` 이 이 파일의 배포 주소다.

## 검색 시험 (`node scripts/test_engine.js`)

- **[0] 베끼기 검사**: 시험 질문이 정답 카드의 예상 질문과 글자 조각 60% 넘게 겹치면 알린다. 시험지를 카드에 옮겨 적으면 처음 보는 질문을 재지 못하기 때문이다.
- **[1] 예상 질문 빼고 찾기**: 카드마다 예상 질문 하나를 빼고 그 카드를 다시 찾는다. '정확히 그 카드'만 정답으로 치는 엄격한 숫자와, 같은 내용 카드·종합 카드도 인정한 숫자를 함께 보여 준다. 고칠 때마다 나빠졌는지 보는 비교용이다.
- **[2] 시험 질문**(`_devset*.json`): 처음 보는 표현 333개. '엉뚱한 답을 바로 냄'(되묻지 않고 틀린 카드로 답함)을 따로 센다. 신뢰를 가장 크게 깎는 경우라 0개를 목표로 한다.
- **[2b] 얼려 둔 새 시험 질문**(`knowledge/holdout.json`): 시험 질문 오답을 고치기 전에 써 두고, 고치는 동안 보지 않은 질문. [2]를 보며 고친 탓에 점수가 부풀었는지 확인한다. 이 질문도 카드에 옮겨 넣지 않는다.
- 정답 인정 기준: 기대 카드, 그 카드를 묶은 종합 카드, 같은 내용을 두 규정이 옮겨 적은 카드(`knowledge/same_content.json`, 질문의 답을 두 카드가 모두 직접 적을 때만). 질문마다 답을 직접 적은 다른 카드가 있으면 그 시험 질문의 `expect` 에 더한다.
- **[4] 내규나침반**: 낱말을 넣으면 글자 그대로 나오는 조문·별표를 시험 쪽에서 따로 찾은 목록과 하나도 다르지 않은지 대조한다(본 결과 + 접힌 곳 = 글자 그대로, 빠뜨리거나 더하면 실패). 낱말 경계로 이미 고친 경우(‘개인정보’의 ‘인정’, ‘위하여 비상임’의 ‘여비’, ‘비정규직 채용’의 ‘정규직채용’ 등은 접힘 / ‘임직원’의 ‘직원’, ‘성과평가 결과’의 ‘평가결과’ 등은 본 결과)가 되살아나지 않는지도 대조한다.

## 내규나침반 (입력칸 위 '내규나침반')

낱말이 어느 내규 어디에 나오는지 원문에서 찾는다(`web/engine.js` 의 `Compass`). 키워드-조문 짝 맞춤표를 따로 만들지 않는다.

- **글자 그대로**: 내규 71개 원문 전체에서 Ctrl+F 처럼 찾아 내규별로 묶는다. 띄어쓰기·표 칸·가운뎃점 차이만 무시하고 하나도 빠뜨리지 않는다. 두 낱말을 띄어 쓰면 둘 다 나오는 곳. 이름에 낱말이 든 내규를 맨 앞에, 그 내규가 "법인카드(이하 “카드”라 한다)"처럼 줄여 부르면 줄인 말이 나오는 조문도 함께.
- **낱말 경계(본 결과·접힌 곳)**: 걸린 곳마다 형태소 분석으로 만든 낱말 경계(`knowledge/word_bounds.json`)에 맞는지 본다. 경계에 맞으면 본 결과, 다른 낱말 속(‘개인정보’의 ‘인정’, ‘위원회의’의 ‘회의’)·반대말 머리 뒤(‘비공개’의 ‘공개’)·엉뚱하게 띄어 걸린 곳(‘위하여 비상임’의 ‘여비’, ‘재직 중 징계’의 ‘중징계’)은 접는다. 접힌 곳은 지우지 않고 '다른 낱말 속' 단추로 펼친다. 한 덩어리로 된 긴 말은 원문 낱말로 쪼개 보고(‘공직자윤리법’의 ‘윤리’는 본 결과), 한 글자 머리가 붙은 말(임직원·중징계·공휴일)과 속 낱말이 걸리면 안 되는 고유 이름(우체국금융개발원)은 확인 목록(`knowledge/word_splits.json`)으로 다룬다.
- **걸린 말별 단추**: 걸린 곳을 감싼 낱말 덩어리별로 묶어 단추로 보여 준다. 같은 글자 다른 뜻(‘이사’ → 이사회 / 이사화물)은 단추를 꺼서 뺀다. 원문 칸에서 꺼 둔 곳은 점선으로 그리고 ▲▼·곳 수에서 뺀다.
- **글자 그대로 없을 때(참고용)**: ① 일상어→규정어 짝(`SYNONYMS`, '반차'→'반일연가'). 조문 60곳 넘게 나오는 흔한 말은 뺀다. ② 그 낱말을 예상 질문·제목에 글자 그대로 가진 답 카드의 근거 조문(카드 이름을 이유로 붙임). ③ 둘 다 없으면 글자가 비슷한 조문. '내규에 없음' 카드는 이름에 낱말이 들 때만 알린다.
- 화면: 왼쪽에 낱말이 나오는 내규 목록(많이 나오는 순, 줄인 말 포함, 8개 넘으면 '더 보기'), 오른쪽에 고른 내규의 원문 전체. 처음엔 첫 번째로 나오는 곳에 가 있고, 찾은 조문 바로가기 단추로 건너뛰거나 ▲▼로 하나씩 오간다. 노란색은 넣은 낱말, 파란색은 같은 뜻의 다른 말·답 카드 근거 문구. 이름에 낱말이 든 내규는 맨 위 칸에 따로 알린다. 휴대폰 폭에서는 목록 → 원문 → '← 내규 목록'으로 번갈아 보인다.
- 결과는 한 번에 하나만(챗봇도 같음). 지난 낱말·질문은 입력칸 아래 '최근 찾은 낱말'·'최근 질문' 단추로 다시 찾는다(화면을 닫으면 사라지고 저장하지 않음).
- 원문에 없고 그 낱말을 묻는 카드도 없으면 '찾지 못함'으로 정직하게 알린다. 자주 못 찾는 일상어는 `SYNONYMS` 에 짝을 더하면 된다.
- **낱말 경계 다시 만들기**: 내규 원문이 바뀌면 `python3 scripts/build_bounds.py`(형태소 분석기 Kiwi, 버전 고정: `python3 -m venv .venv && .venv/bin/pip install -r scripts/requirements-bounds.txt`, 그다음 `.venv/bin/python scripts/build_bounds.py`). 분석은 유지보수 PC에서만 하고 폐쇄망 화면에는 결과 표시만 들어간다. 원문과 표시가 맞지 않으면 `build_web.py` 가 묶지 않는다. 개정 반영(`update_rules.py finish`)은 이 단계를 자동으로 돈다.

## 인터넷망 AI 보조(선택)

`python3 scripts/export_gpts.py` → `dist/gpts/`. ChatGPT GPTs(또는 프로젝트)를 만들어 `지시문.md` 내용을 지침 칸에 붙여 넣고, 나머지 `카드_*.md`와 `조문_원문.md`(13개 안팎, 20개 한도)를 지식 파일로 올린다. 카드 근거로만 답하고 카드 ID·조문을 밝히게 되어 있어, 조건이 여러 개인 질문이나 이어 묻기를 이 시범본보다 잘 다룬다. 인터넷망 전용이며 폐쇄망은 이 시범본(dist/index.html)을 쓴다. 직원 질문에 개인정보·비공개 정보를 넣지 않도록 첫 인사에서 안내한다(인공지능전환관리세칙 제29조제2항). 운영 전에 정보보안 검토를 받는다(reports/governance).

## 담당부서 검수

`python3 scripts/review_workbook.py export` → `reports/review/검수표_<분류>.xlsx`(11개). 소관부서가 카드마다 판정(정확/수정 필요/삭제)·검수부서·검수일을 적어 돌려주면 `python3 scripts/review_workbook.py import reports/review/*.xlsx` 로 반영한다. '정확' 카드는 화면에 "담당부서 검수 완료 · 날짜 · 부서"로 표시되고, 카드 내용이 나중에 바뀌면 자동으로 "검수 전"으로 돌아간다. 수정 요청은 `reports/review/수정요청.md` 에 모인다.

## 운영 설정

`knowledge/site.json`: 채운 뒤 다시 묶는다(`python3 scripts/build_web.py`).
- `release`: 판 번호(no, 화면 맨 위 "제N판", `update_rules.py finish` 가 1씩 올린다)와 최신본 받는 곳(where).
- `feedback`: 오류 신고를 받을 운영부서(dept)·메일(email)·창구(channel).
- `featured`: 첫 화면 '자주 찾는 분야' 버튼(`topics`: `"분야id:주제id"`, `cards`: 함께 보여 줄 카드 id). 여기에 전부 들어간 분야는 '모든 분야 보기'에서 빠진다. 잘못된 주제·카드는 `check_knowledge.py` 가 오류로 알린다.
- `examples`: 첫 화면 '이렇게 물어보세요' 질문. 한 분야에 치우치지 않게, 화면 점검(`scripts/ui_test.js`)에서 맞는 답과 계산기에 닿는 것만.
- `calcOff`: 끌 계산기 이름(예: `["tripExpense"]`). 시범 운영 중 틀린 금액이 신고되면 바로 넣고 다시 묶는다. 그 계산기는 '점검 중'으로 멈춘다.
- `maxAgeDays`: 오래된 판 안내 기준일 수.

## 계산기

카드의 `calc` 에 계산기 이름을 적으면 답 아래에 계산기가 붙는다(11종, `web/engine.js` 의 `calc`). 계산기가 없는 관련 카드에는 `calc_link` 로 '계산기 열기' 버튼을 단다. 질문에 금액·기간을 묻는 말과 주제어가 있으면(예: "가족수당 얼마") 어느 답이 나와도 같은 버튼이 붙는다.
- 질문 속 날짜·일수·지역·자녀 수 등을 읽어 칸을 채운다. 못 읽은 칸은 비워 두고 '확인 필요'로 표시하며, 채우기 전에는 계산하지 않는다(기본값 금액을 자기 금액으로 믿지 않게).
- 숫자의 근거 조문과 원문 문구는 `knowledge/calc_basis.json`. 계산기 숫자를 고치면 이 표도 고친다.
- 평가등급 인원배분(`gradeQuota`): '함께 등급을 나누는 인원' 한 칸으로 평가세칙 별표 제2호 인원배분표(4~100명)에서 등급별 인원을 찾는다. 누구와 함께 나누는지(팀·실 단위, 포함 인원)는 성과관리편람·운영기준(평가세칙 제19조)에서 정해 해마다 달라질 수 있어 셈하지 않고, 칸 아래와 답에서 관련 부서 확인을 안내한다. 표는 `GRADE_TABLE` 에 옮겨 두었고 `test_engine.js` [3]이 원문 표와 한 칸씩 대조한다(별표가 개정되면 시험이 실패해 알려 준다).
