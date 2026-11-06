---
name: naegyu-update
description: 내규챗봇에 개정된 내규나 새 내규를 반영한다. 사용자가 "내규 개정 반영", "개정 반영 이어서", "개정된 내규 올렸어", "새 내규 추가", "내규 바뀌었어", "개정 반영 다음 단계"라고 하거나, GitHub 이슈(개정 의심 등)를 보고 반영해 달라고 하거나, 내규 한글 파일(hwp·hwpx)을 첨부하며 반영해 달라고 할 때 쓴다. 단계마다 결과를 쉬운 말로 설명하고, 끝에 Pull Request 를 연다. Claude 는 합치지 않는다.
---

# 내규 개정·신설 반영 (내규챗봇, Claude 웹)

이 저장소 안에서 Claude 웹(클라우드 세션)으로 한다. 도구: `scripts/update_rules.py`(status → convert → finish). 작성 규칙: `knowledge/AUTHORING.md`. 프로젝트 주의점: `CLAUDE.md`. 담당자용 설명: `docs/유지보수_안내.md`.

사용자는 개발자가 아니다. 모든 말은 쉬운 한국어로, 짧게. 명령어·파일 경로는 꼭 필요할 때만 보여 준다.
**단계가 끝날 때마다** 결과를 3~5줄로 설명하고, 사용자가 다음에 할 말을 글로 알려 준다(예: `다음에는 "내규 개정 반영 2단계: 변환하고 비교해줘"라고 말하면 됩니다`). 버튼 도구가 있으면 같은 문장을 버튼으로 띄워도 된다.
작업 목록 도구가 있으면 다섯 단계를 띄워 둔다.

**알아 둘 것**
- 클라우드 세션에서는 ALIO(알리오)에 접속할 수 없다. ALIO 확인은 GitHub 가 매주 한다.
- 사용 한도: 고친 카드는 자주 갈래에 커밋한다. 한도에 걸려 멈추면 시간이 지난 뒤 사용자가 "개정 반영 이어서"라고 말한다. 이어 할 때는 열린 `claude/…` 갈래를 찾아 거기서 계속하고, 이미 고친 카드는 다시 고치지 않는다(`git log`, `knowledge/stale_cards.json` 으로 확인).
- 하위 작업(서브에이전트)은 새 내규 대량 작성과 3단계의 AI 재확인에만 쓴다.

## 0단계 — 준비 확인

세션을 열면 시작 훅이 `python3 -X utf8 scripts/setup_project.py --full --allow-changes` 를 이미 돌린다. 끝났는지만 확인하고(`data/` 가 있고 `python3 scripts/update_rules.py status` 가 돈다), 아니면 돌린다.
- 처음 시작이면 `python3 -X utf8 scripts/setup_project.py --full`. 개정 작업 도중에 다시 열었으면 `--full --allow-changes`(지문과 달라도 멈추지 않고 보여 주기만 한다).
- 지문(`knowledge/source_snapshot.json`)은 절대 저절로 다시 찍지 않는다. 처음 시작인데 바뀐 단위가 0이 아니거나 다시 확인할 문답이 있다고 나오면 멈추고 사용자에게 알린다.

## 1단계 — 파일 받기와 확인

무엇을 반영할지 정한다. 열린 GitHub 이슈(`개정 의심: …`, `새 내규: …` 등), `대기/` 폴더, 사용자가 말한 내용을 본다.

1. **매주 확인이 받아 둔 파일**: `대기/<내규명>_<숫자 날짜>/` 에 있다. 이슈에 "원본 폴더에 넣을 이름"이 적혀 있다. 그 파일을 그 이름 그대로 `원본/` 으로 옮긴다(개정본이면 기존 파일을 덮어쓴다. 옛 판은 git 기록에 남는다). 옮긴 뒤 `대기/` 의 그 폴더는 지운다.
2. **담당자가 직접 올린 파일**: 내규관리부서가 ALIO 보다 먼저 준 파일은 담당자가 `대기/<내규명>_직접/` 에 올려 둔다. 이 이름의 폴더는 매주 확인이 건드리지 않는다(`<내규명>_<숫자>` 폴더는 매주 확인이 바꿀 수 있다). 파일 이름이 `코드. 규정명.확장자` 가 아니면 맞춘다. 같은 방식으로 `원본/` 에 옮기고 폴더를 지운다.
3. **대화에 첨부한 파일**: 이름을 `코드. 규정명.확장자` 로 맞춰 `원본/` 에 둔다.
4. 새 내규면 분류 코드를 사용자에게 묻는다(내규분류표의 위치, 예 `Ⅳ-30`). 모르면 "Ⅳ-(마지막 번호+1)"을 제안한다.
5. `python3 scripts/update_rules.py status` 로 바뀐 파일·새 파일·사라진 파일을 보여 준다. `[확인 필요]`(같은 규정 파일이 둘, 이름 형식 틀림)가 있으면 무엇을 하면 되는지 한 줄로 알려 주고 사용자가 원하면 정리한다. `[` 로 시작하는 파일은 올리지 않는다.
6. 다음 말: "내규 개정 반영 2단계: 변환하고 비교해줘"

## 2단계 — 변환하고 비교

1. `python3 scripts/update_rules.py convert` (몇 분 걸릴 수 있다).
2. `reports/change_report.md` 를 읽고 규정별로 쉽게 정리한다.
   - 시행일 변경, 바뀐 조문(개정 전 → 후 핵심 한두 줄), 다시 확인할 카드 수, 다시 확인할 계산기, 새로 생긴 조문, 카드가 없는 새 내규, 카드 검사 오류(인용이 깨진 것, 계산기 근거 문구가 원문에서 사라진 것)
   - 양식(별지): convert 출력의 서식 대장 줄(`원문 제목이 바뀜`, `부르는 조문이 바뀜`, `… 그 조문에는 양식 칸을 달지 않음(원문 확인)`, `… 그 번호 별지가 없음`, `법령 이름 뒤에 나오지만 … 이 내규 별지로 보고 양식 칸을 닮(원문 확인)`)
3. 다음 말: "내규 개정 반영 3단계: 카드 고쳐줘"

## 3단계 — 카드 고치기와 AI 재확인

규칙은 `knowledge/AUTHORING.md` 를 따른다. 근거 인용(quote)은 새 원문에서 글자 그대로 복사한다. 시험 질문(`_devset*.json`, `knowledge/holdout.json`)은 카드나 하위 작업 지시문에 옮겨 넣지 않는다.

1. **다시 확인할 카드**(`knowledge/stale_cards.json`): 바뀐 조·항의 새 원문(`python3 scripts/show_rule.py <규정명>`)을 읽고 답·요약·근거를 고친다. 답에 영향이 없으면 그대로 두되 근거 인용만 맞춘다.
2. **카드 검사 오류**: 조문 번호가 바뀌었으면 인용을 새 번호로, 삭제됐으면 카드에서 그 내용을 빼거나 카드를 지운다(지울 때는 다른 카드의 related 에서도 뺀다).
   - **계산기**: '다시 확인할 계산기'(stale_cards.json 의 calcs)나 `[계산기 …] 원문에 "…" 가 없음` 오류가 있으면, 새 원문을 보고 `web/engine.js` 의 그 계산기 숫자와 `knowledge/calc_basis.json` 의 cite·has 를 고친다. 그 계산기 카드의 답·근거도 같이 맞춘다.
3. **새 조문**: 직원이 물을 만한 실질 내용이면 카드를 새로 만들거나 관련 카드에 더한다.
4. **새 내규**: 개요 카드 1장 + 실질 조문 카드(조문 1~3개당 1장), 시험 질문 2~4개(`_devset_<접두어>.json`, 카드 질문과 다른 표현). 파일·접두어 규칙은 AUTHORING.md. 카드가 15장이 넘으면 하위 작업에 나눠 맡겨도 된다(시험 질문은 보여 주지 않는다).
5. 개정 이유가 법령 개정이면 korean-law 도구로 상위 법령을 확인하고, 필요하면 `knowledge/external_laws.json` 과 카드의 law_refs 를 고친다.
   - **양식(`knowledge/forms.json`)**: 2단계의 서식 대장 줄을 원문과 대조한다. 화면 제목이 깨졌으면 그 별지의 `title` 을 고친다. 조문이 부르는 이름과 별지 제목이 다른 곳은 양식 칸이 안 붙으니 사용자에게 알리고 `reports/rule_fix_candidates.md` 에 적는다.
6. **고친 카드를 갈래에 커밋한다**(파일을 지정해서. `git add -A` 금지). 한도로 끊겨도 이어 갈 수 있게 자주 한다.
7. 검사: `python3 scripts/check_knowledge.py` 오류 0건. 위임전결세칙이 바뀌었으면 `python3 scripts/check_approval_table.py` 도.
8. **AI 재확인**: 고치거나 새로 만든 카드만 한다. 카드 값을 모르는 다른 AI가 조문만 보고 값을 다시 찾아 비교하는 단계다.
   1. `python3 scripts/blind_check.py prepare <카드 id…>` → `reports/blind_work/questions.json`
   2. 하위 작업(기본 Sonnet)에게 맡긴다. 지시문: "`reports/blind_work/questions.json` 만 읽고, 각 문제의 `prompt` 대로 답을 `{카드 id: [값, …]}` 꼴로 `reports/blind_work/answers.json` 에 쓴다. `knowledge/` 아래 카드 파일과 다른 파일은 읽지 마라." 문제가 많으면 나누어 답 파일을 여러 개 만든다(답 파일에 적은 AI 이름은 `--ai` 로 넘긴다).
   3. `python3 scripts/blind_check.py first reports/blind_work/answers.json --ai Sonnet` (답 파일 경로는 실제 이름으로). 끝난 만큼 `reports/blind_work/` 에 쌓인다. `python3 scripts/blind_check.py remaining` 으로 아직 답을 못 받은 카드를 본다.
   4. `first` 가 `judge_questions.json` 을 썼으면 같은 방식으로 하위 작업이 `judge_answers.json`(각 문제의 `key` 를 열쇠로 한 `{"<key>": {"판정": "예 또는 아니오", "이유": "…"}}`)을 쓰게 한다.
   5. 남은 카드가 없을 때 `python3 scripts/blind_check.py finish [reports/blind_work/judge_answers.json] --ai Sonnet`. `reports/blind_check.md` 가 만들어지고 `reports/blind_work/` 는 지워진다.
   6. `reports/blind_work/` 는 작업 도중 갈래에 커밋해 둔다(이어 하기 위해). `finish` 로 폴더가 지워진 뒤에는 결과 파일만 커밋한다.
   7. 하위 작업을 쓸 수 없는 환경이면 직접 답하지 말고(카드 값을 이미 알고 있어 재확인이 되지 않는다) 사용자에게 말한다: "새 Claude 웹 세션을 열어 `reports/blind_work/questions.json` 만 주고 답 파일을 만들어 달라고 하세요." 새 세션이 쓴 답 파일을 이 갈래의 `reports/blind_work/` 에 올려 달라고 하고, 올라오면 위 3번부터 이어 간다.
   8. '확인 필요'는 원문과 대조해 카드를 고치거나 `reports/review_decisions.json` 에 결정을 남긴다.
9. 사용자에게 보여 줄 것: 고친·새 카드 목록, 카드마다 "무엇이 바뀌었나" 한 줄(예: "배우자 출산휴가 20일 → 25일"), 고친 계산기와 바뀐 숫자, 담당부서 확인이 필요한 점.
10. 다음 말: "내규 개정 반영 4단계: 승인하고 새 판 준비해줘"

## 4단계 — 새 판 준비

1. `python3 scripts/update_rules.py finish <이번에 바뀐 규정명들>` — 개정 지문 갱신, 판 번호 +1, 낱말 경계·양식 다시 만들기, 화면·GPTs 묶음·검수표 다시 만들기, 시험.
   - **끝의 `경고: ALIO 기록 갱신 실패`(또는 비슷한 경고)는 정상이다.** 클라우드 세션은 ALIO 에 접속할 수 없다. 사용자에게 "놀라지 않으셔도 됩니다. 합친 뒤 GitHub 가 알아서 다시 합니다"라고 알린다.
   - 양식 검사(check_forms)가 "다름"으로 멈추면: 그 별지의 `download` 를 `false`, `cutNote` 에 까닭을 적고 finish 를 다시 돌린 뒤 사용자에게 알린다.
   - 나침반 시험(test_engine.js [4])이 실패하면 낱말 경계가 이미 고친 경우를 되살린 것이다. 실패한 낱말을 보고 `knowledge/word_splits.json` 을 고치거나 사용자에게 알린다.
   - 형태소 분석기가 없다고 멈추면 `python3 -X utf8 scripts/setup_project.py --full` 을 돌리고 다시 한다.
2. 화면 점검: `node --max-old-space-size=8192 scripts/ui_test.js dist/index.html`. 계산기·예시 질문 항목까지 모두 통과해야 한다.
3. 결과를 알린다: 판 번호, 카드 수 변화, 시험 결과, "재검수 전" 카드 0장·멈춘 계산기 0종, 양식 수.
4. 다음 말: "내규 개정 반영 5단계: Pull Request 열어줘"

## 5단계 — 올리고 Pull Request 열기

1. `claude/…` 갈래에 커밋한다(파일을 지정해서. `[` 로 시작하는 파일과 `knowledge/contacts.json`, `reports/contacts/` 는 올리지 않는다). 커밋 메시지: "내규 개정 반영: <규정명>(시행 YYYY.MM.DD) …".
2. Pull Request 글을 쉬운 말로 쓴다.
   - 무엇이 바뀌었나(카드마다 한 줄, 계산기, 담당부서 확인이 필요한 점)
   - 관련 이슈 링크(예: `관련: #12`)
   - 맨 끝에 "합치기 버튼(Merge pull request)을 누르면 새 판이 만들어집니다."
3. **연다.** 지금 가진 도구로 연다. 열 수 없으면 위 글 전체를 대화에 써서 보여 주고, 눌러야 할 버튼을 알린다: Claude 웹에서는 `Create PR`, GitHub 화면에서는 `Compare & pull request`.
4. **Claude 는 합치지 않는다.** 합치는 것은 담당자가 GitHub 에서 `Merge pull request` 를 눌러서 한다. 시험 결과(Checks)가 모두 통과한 것을 확인하라고 알린다.
5. PR 에 "판 번호를 올리지 않았다"는 시험 실패 글이 달리면(다른 PR 이 먼저 합쳐졌거나 `finish` 를 건너뛴 경우) 합치지 말라고 알린다. 글이 Claude 웹에 보이면 `knowledge/site.json` 의 `release.no` 를 알려 준 값 이상으로 올리고(필요하면 4단계를 다시) 같은 갈래에 커밋한다.
6. 다음 할 일을 짧게 안내한다.
   - 합친 뒤: 몇 분 뒤 GitHub 의 Releases 에 새 판이 생긴다. 받는 파일은 `naegyu-chatbot-vN.html`(직원에게 보일 챗봇). 이것을 망연계로 내부망에 옮긴다. 인터넷망용 GPTs 묶음(`gpts-vN.zip`)과 소관부서 검수표(`review-workbooks-vN.zip`)도 같은 곳에 있다.
   - 개정 중 발견한 오기·충돌을 `reports/rule_fix_candidates.md` 에 적었다면 내규관리부서에 전달
   - `새 판 실패` 이슈가 생기면 `docs/유지보수_안내.md` 를 따른다

## 계산기 끄기·켜기 (개정과 별개로 요청받을 때)

"○○ 계산기 꺼줘"(틀린 금액 신고 등): `knowledge/site.json` 의 `calcOff` 에 계산기 이름(calc_basis.json 의 키, 예 `tripExpense`)을 넣고 `python3 scripts/build_web.py`, 화면 점검 후 `release.no` 를 1 올리고 갈래에 올려 Pull Request 를 연다. 켤 때는 빼고 같은 순서.
