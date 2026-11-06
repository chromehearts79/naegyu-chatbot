# 내규챗봇 프로젝트 설명서 (Claude 용)

이 저장소는 (재)우체국금융개발원 내규를 근거 조문과 함께 답하는 챗봇을 만들고 고친다. 답은 미리 써서 검증해 둔 문답 카드에서 나오고, 직원 PC에서는 찾아서 보여 주기만 한다. 먼저 `README.md`(폴더와 도구), `docs/유지보수_안내.md`(담당자 흐름), `knowledge/AUTHORING.md`(카드 작성 규칙)를 본다. 개정 반영은 스킬 `naegyu-update` 를 따른다.

## 사용자와 말하는 법

- 사용자(담당자)는 개발자가 아니다. 모든 답은 **쉬운 한국어**로, 짧게. 개발 용어 대신 평범한 말을 쓴다. 명령어와 파일 경로는 꼭 필요할 때만.
- 결과를 말할 때는 "무엇이 바뀌었나"와 "다음에 할 일"을 먼저 말한다.
- 이슈, 커밋, 로그에 사람 이름과 개인 메일을 적지 않는다. 저장소는 공개다. GitHub 아이디만 쓴다.

## 지켜야 할 것

- **`git add -A` 와 `git add .` 를 쓰지 않는다.** 파일을 지정해서 올린다. 이름이 `[` 로 시작하는 파일(`원본/[…]`, `대기/**/[…]`)과 `knowledge/contacts.json`, `reports/contacts/` 는 올리지 않는다.
- **`main` 에 직접 올리지 않는다.** 클라우드 세션에서도, 맥 등 자기 PC에서도 갈래(`claude/…` 또는 작업 이름)를 만들어 올리고 Pull Request 로 합친다. 합치는 것은 사람이다. 직접 올리면 시험 없이 새 판 흐름이 돌 수 있다.
- **kordoc 판은 `4.24.1` 에 고정**이다(`package.json`, 잠금 파일). 이 판만 지금 변환본과 71개 모두 같게 나온다. 최신판은 내규 일부에서 항 나누기가 어긋난다. 임의로 올리지 않는다. 올려야 하면: 새 판으로 `원본/` 전체를 다시 변환하고(`setup_project.py` 가 지문과 다르면 멈춘다), 바뀐 단위 수와 다시 확인할 문답을 사용자에게 보여 주고, 허락받은 뒤에만 지문(`knowledge/source_snapshot.json`)을 다시 찍는다. 지문을 저절로 다시 찍지 않는다.
- 판정 이름은 `scripts/alio_types.py` 의 상수를 쓴다. 판정 규칙(`watch_alio.judge`)과 재확인 비교 규칙(`blind_check.compare`)은 바꾸기 전에 사용자와 정한다.
- 새 코드는 `encoding="utf-8"`, Python 3.11 에서 돌아야 한다(f-string 식 안에 역슬래시나 같은 따옴표를 쓰지 않는다). 시험은 `python3 -X utf8 scripts/test_watch_alio.py`, `scripts/test_browser_ops.py`, `scripts/test_forms.py`, `node scripts/test_engine.js` 등. 통과는 `✗` 없음과 종료 코드 0.
- GitHub Actions 에 넣는 이슈·댓글 글자는 `env:` 로만 넘기고 `run:` 안에 `${{ }}` 로 직접 넣지 않는다. `pull_request_target` 을 쓰지 않는다.

## 시험 질문은 지킨다

- **시험 질문(`knowledge/**/_devset*.json`, `knowledge/holdout.json`)을 카드에 옮기거나 하위 작업(서브에이전트) 지시문에 넣지 않는다.** 넣으면 점수가 부풀어 처음 보는 질문을 재지 못한다. `test_engine.js` [0] 이 베낀 것을 잡는다.
- AI 재확인에서는 답하는 AI에게 카드 파일을 읽게 하지 않는다. 문제 파일(`reports/blind_work/questions.json`)만 준다.

## 내규 원본과 ALIO 사실

- 원본은 `원본/` 폴더다(내규 71개 한글 파일 + 위임전결 별표 엑셀). ALIO 가 기준이 아니다.
- **ALIO 의 ZIP 에는 개정 이력이 함께 들어 있다.** 맨 앞 항목은 옛 판이다. 현행은 **파일 이름의 가장 최근 일자**로 읽는다(첨부 ZIP, ZIP 속 ZIP 포함. 폴더 이름의 일자는 보지 않는다). 같은 일자 묶음(위임전결 한글+별표 엑셀)은 함께 읽는다. 같은 일자가 둘이면 첨부 번호가 큰 쪽이다.
- ALIO 목록의 날짜는 개정일이고, 파일 부칙의 **시행일**과 다를 수 있다. ALIO 게시는 공포보다 약 1주 늦다. 시행일 칸 비교는 헛알림이 많아 쓰지 않는다. 판단 순서: 게시일 변화 → 파일 지문 → 원문 비교.
- ALIO 기관 번호는 C0352. **클라우드 세션(Claude 웹)에서는 ALIO 에 접속할 수 없다.** ALIO 확인과 기록 갱신은 GitHub Actions 만 한다. 그래서 `update_rules.py finish` 끝의 "ALIO 기록 갱신 실패" 경고는 클라우드에서는 정상이다.
- 위임전결 별표 엑셀은 파일 지문이 달라도 칸 값이 같으면 같은 것으로 본다.

## 카드와 검색의 함정

- 근거 인용(`quote`)은 원문에서 글자 그대로 복사한다. `check_knowledge.py` 가 원문과 대조한다.
- **글자 조각(bigram) 검색의 함정:** 합성어 속 글자가 엉뚱하게 걸린다("시외출장"의 "외출"). 머리 명사 `출장` 은 `content()` 와 `synonymsOf()` 양쪽에서 나눈다. 일반적인 동의어(통제, 이월, 수당 …)는 다른 규정에 번져 엉뚱한 답을 낸다. 맥락 조건이 붙은 동의어(세 번째 값)만 쓴다. 카드를 고치면 `node scripts/calibrate.js` 로 기준값을 다시 본다.
- 위임전결 표는 AI 재확인이 못 읽는다(열 이름이 창에 안 들어간다). 그래서 `check_approval_table.py` 가 표의 ○ 칸과 카드의 전결권자를 대조한다. 위임전결세칙이 바뀌면 같이 돌린다.
- 판 번호는 `knowledge/site.json` 의 `release.no`. `update_rules.py finish` 가 1 올린다. 이미 나간 판은 GitHub 태그 `v<번호>` 로 안다. 문답이나 원본이 바뀌는 PR 은 번호가 최신 태그보다 커야 시험을 통과한다.
- 내규나침반 낱말 경계(`knowledge/word_bounds.json`)는 형태소 분석기 Kiwi(`kiwipiepy==0.24.1`, 버전 고정)로 빌드할 때만 만든다. 개정 반영(`finish`)이 자동으로 다시 만든다. 나침반 시험 [4]가 실패하면 되살아난 경계가 있는 것이니 `knowledge/word_splits.json`(한 글자 머리 말, 고유 이름 확인 목록)을 고친다.
- 서식 받기: 서식 대장(`knowledge/forms.json`)이 별지 번호·제목·부르는 조문을 담고, `cut_forms.cjs` 가 원본에서 별지만 떼어 낸다. 조문이 부르는 이름과 별지 제목이 다르면 양식 칸을 달지 않는다(원문 번호 오류일 수 있다). 사람이 고친 제목과 받기 켜고 끄기는 다시 읽어도 그대로 둔다.

## 기관 제약(인공지능전환관리세칙, 2026-08-18 제정)

- 챗봇은 별표1 "제한적 위험"이다: AI 고지·표시와 정확성 검증이 필요하다(화면의 "AI 작성 · 담당부서 검수 전" 표시).
- 제29조②: 비공개 정보나 개인정보를 외부 AI에 넣지 않는다. 직원 질문과 질문 기록(`logs/`)을 저장소에 올리지 않는다.
- 제31조①: 오류 신고·이의 창구가 있어야 한다(`knowledge/site.json` 의 `feedback`).
- 제18조: 사업은 AX 실무협의회가 확정한 세부실행과제로 공식화된다. 제22조: 위탁업무에 AI 를 쓰려면 상위기관 협의가 필요하다.
- 기관 문서(`reports/governance`)는 제출 여부가 확인되지 않아 고치지 않는다. 바뀌는 점은 `docs/유지보수_안내.md` 끝의 "인계 할 일"에 있다.

## 자주 쓰는 명령

```
python3 -X utf8 scripts/setup_project.py --full [--allow-changes]   # 준비(클라우드 세션은 시작 때 자동)
python3 scripts/update_rules.py status | convert | finish <규정명…>  # 개정 반영
python3 scripts/blind_check.py prepare|first|finish|remaining|sample  # AI 재확인
python3 -X utf8 scripts/check_upload.py --staged                    # 올리기 전 개인정보·키 점검
```
