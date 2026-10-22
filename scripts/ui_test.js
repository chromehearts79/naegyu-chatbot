// 시범본 화면 자동 점검 (jsdom). 사용법: node scripts/ui_test.js dist/index.html
// 모든 카드를 열고 모든 근거 버튼을 눌러 원문과 인용 표시를 확인한다. jsdom 이 필요하다: npm i --no-save jsdom@24.1.3
const fs = require("fs");
let jsdom;
try { jsdom = require("jsdom"); } catch (e) { console.error("jsdom 이 없습니다. 먼저 실행: npm i --no-save jsdom@24.1.3"); process.exit(2); }
const { JSDOM, VirtualConsole } = jsdom;
const html = fs.readFileSync(process.argv[2], "utf8");
const errors = [];
const vc = new VirtualConsole();
vc.on("jsdomError", (e) => errors.push("jsdom: " + e.message));
vc.on("error", (e) => errors.push("console: " + e));
const dom = new JSDOM(html, {
  runScripts: "dangerously", pretendToBeVisual: true, virtualConsole: vc,
  beforeParse(w) {
    w.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} });
    w.scrollTo = () => {};
    w.Element.prototype.scrollIntoView = function () {};
    w.addEventListener("error", (e) => errors.push("window: " + e.message));
  },
});
const w = dom.window, d = w.document;
const ok = (cond, msg) => { console.log((cond ? "✓ " : "✗ ") + msg); if (!cond) process.exitCode = 1; };
const top = () => d.querySelector("#thread .turn");

const nTopics = w.DATA.domains.reduce((n, dm) => n + dm.topics.length, 0);
ok(d.querySelectorAll("#topics .chip").length === nTopics && d.querySelectorAll("#topics .topic-group").length === w.DATA.domains.length, `상황별 메뉴 ${w.DATA.domains.length}개 분야, ${nTopics}개`);
ok(!top() && !d.querySelector("#examples"), "처음 화면에 예시 답변·예시 질문 없음");
ok(!/출산/.test(d.querySelector("#q").placeholder), "입력칸 안내 문구가 특정 분야에 치우치지 않음");
ok(d.querySelectorAll("#about .stat").length === 6, "검증 정보 숫자 6칸");
ok(!/null|undefined/.test(d.querySelector("#about").textContent), "검증 정보에 'null' 같은 글자 없음");

// 바로 답이면 그 제목, 되묻기면 아래에 펼친 '가장 가까운 답'의 제목
const title = (t) => (t.querySelector(".lead .a-title") || t.querySelector(".a-title")).textContent;
function ask(q) { d.querySelector("#q").value = q; d.querySelector("#ask-form").dispatchEvent(new w.Event("submit", { cancelable: true })); return top(); }
let t = ask("배우자 출산휴가 며칠이에요?");
ok(/배우자 출산전후휴가/.test(title(t)), "질문 → 배우자 출산전후휴가 답변");
ok(t.querySelectorAll(".facts tbody tr").length === 7, "답변 핵심 정리 7줄");
ok(t.querySelector(".calc table"), "답변 계산기 결과 표");
t = ask("출산");
ok(/조금 더 알려주세요/.test(t.textContent) && t.querySelectorAll(".cand").length >= 2, "한 단어 질문 → 되묻기 후보 " + t.querySelectorAll(".cand").length + "개");
t.querySelector(".cand").click();
ok(top().querySelector(".a-title") && top().querySelector(".q .tag").textContent === "선택", "되묻기 후보 누르면 답변");
t = ask("법인카드 분실하면 어떻게 해요");
ok(/법인카드/.test(title(t)), "규정 전체 카드: 법인카드 분실 → 법인카드 카드");
t = ask("오늘 날씨 어때");
ok(/준비된 답이 없습니다/.test(t.textContent), "규정과 무관한 질문 → 준비된 답 없음");
t = ask("회사 근처 맛집 추천해줘");
ok(!t.querySelector(".lead") && t.querySelector(".hits, details.box"), "점수 낮은 질문 → 답 미리보기 없이 후보·관련 조문만");
t = ask("법인카드 분실 신고");
t.querySelector(".a .hit") ? t.querySelector(".a .hit").click() : t.querySelector(".cite").click();
ok(/법인카드/.test(d.querySelector("#source h2").textContent), "근거나 조문 누르면 원문 열림");

// 계산기: 예정일을 바꾸면 결과가 바뀐다
t = ask("와이프 출산 휴가");
const due = t.querySelector(".calc input[type=date]");
due.value = "2027-03-10"; due.dispatchEvent(new w.Event("input", { bubbles: true }));
ok(/2027\.1\.19\./.test(t.querySelector(".calc table").textContent), "계산기: 예정일 2027-03-10 → 첫날 2027.1.19.");

t = ask("장모님 돌아가셨는데 며칠 쉬어요?");
ok(/사망 경조사휴가/.test(title(t)), "복무: 장모님 상 → 사망 경조사휴가");
t = ask("근속 5년이면 연차 몇 일");
const hire = t.querySelector(".calc input[type=date]");
ok(hire && /연가/.test(title(t)), "복무: 연가 일수 답변과 계산기");
hire.value = "2021-10-21"; t.querySelectorAll(".calc input[type=date]")[1].value = "2026-10-21";
hire.dispatchEvent(new w.Event("input", { bubbles: true }));
ok(/17일/.test(t.querySelector(".calc table").textContent), "계산기: 근속 5년 → 연가 17일");
t = ask("징계 받으면 승진 제한");
ok(/승진/.test(title(t)), "징계 받으면 승진 제한 → 승진 제한 카드");
t = ask("시외출장");
ok(/국내 출장 여비/.test(title(t)), "시외출장 → 국내 출장 여비");
ok(/최대/.test(t.querySelector(".calc table").textContent), "여비 계산기 결과 표");
const meals = t.querySelector(".calc input[id$='-meals']");
meals.value = "3"; meals.dispatchEvent(new w.Event("input", { bubbles: true }));
ok(/3끼 × 8,330원 = 25,010원/.test(t.querySelector(".calc table").textContent), "여비 계산기: 다른 예산으로 먹은 3끼 → 식비 25,010원");
t = ask("지하철비용은 일비에 포함됨?");
ok(/지하철/.test(title(t)), "지하철비용 일비 질문 → 지하철·버스 요금과 일비");
// 평가단 지적 반영 확인
ok(!/<link[^>]+href=["']https?:|<script[^>]+src=|@import|url\(\s*["']?https?:/i.test(html), "외부 주소(글꼴·스크립트)를 부르지 않음");
ok((html.match(/@font-face\{font-family:"A2Z"/g) || []).length === 4, "에이투지체 4가지 굵기가 파일 안에 들어 있음");
t = ask("연차몇일이야");
ok(/연가\(연차\) 일수/.test(title(t)), "붙여 쓴 '연차몇일이야' → 연가 일수");
t = ask("챗지피티 업무에 써도돼요?");
ok(/AI|인공지능/.test(title(t)) || /인공지능|AI/.test(t.querySelector(".cand").textContent), "'챗지피티' → AI 세칙 카드");
t = ask("자격증 따면 응시료나 교육비 지원해 주나요");
ok(t.querySelector(".caution") && /담당부서에 확인/.test(t.querySelector(".caution").textContent), "내규에 없을 수 있는 질문 → 담당부서 확인 안내");
w.pick(w.DATA.cards.find((c) => c.check && c.check.length));
ok(!/검수 메모/.test(top().textContent), "검수 메모는 직원 화면에서 숨김");
ok(/담당부서 검수 전/.test(top().querySelector(".pill").textContent), "검수 전 표시");

// 3단계 기능: 이어 묻기, 여러 가지 묻기, 날짜 채우기
t = ask("부산 출장 가면 숙박비 얼마까지 돼요");
t = ask("그럼 일비는?");
ok(/앞 질문/.test(t.textContent) && /여비|출장/.test(title(t)), "이어 묻기 '그럼 일비는?' → 앞 질문(부산 출장)과 이어서");
t = ask("2천만원짜리 용역을 수의계약으로 할 수 있어? 된다면 전결권자랑 절차는?");
ok(t.querySelector(".box.multi") || /수의계약/.test(title(t)) && /여러 규정|계획 결재부터/.test(t.textContent), "여러 가지 묻기 → 나눠 찾은 답 또는 종합 카드");
t = ask("출산휴가 2026년 12월 1일부터 쓰면 언제 끝나?");
const due2 = t.querySelector(".calc input[type=date]");
ok(!due2 || due2.value !== "2026-12-01", "'12월 1일부터'를 출산예정일 칸에 넣지 않음");
t = ask("2023.3.2 입사했는데 2026년 연가 며칠?");
const dIn = t.querySelector(".calc input[type=date]");
ok(dIn && dIn.value === "2023-03-02" && /질문의 날짜/.test(t.textContent), "질문 속 날짜를 계산기에 채움");
ok(![...d.querySelectorAll("button")].some((b) => /도움이 됐어요/.test(b.textContent)), "기록 안 남는 '도움이 됐어요' 버튼 없음");

// 모든 계산기: 칸마다 여러 값을 넣어도 'null' 같은 글자 없이 결과나 안내가 나오는지
const BAD = /null|undefined|NaN|Invalid|Infinity|\[object/;
const VALS = { number: ["", "0", "1", "-3", "2.7", "30", "400"], date: ["", "1950-01-01", "2000-02-29", "2026-10-22", "2045-12-31"] };
let calcRuns = 0; const calcBad = [];
for (const kind of Object.keys(w.CALCS)) {
  const box = w.renderCalc(kind, []);
  for (const f of w.CALCS[kind].fields) {
    const el = box.querySelector("[id$='-" + f[0] + "']"), keep = f[1] === "check" ? el.checked : el.value;
    const vals = f[1] === "check" ? [true, false] : f[1] === "select" ? f[4].map((o) => o[0]) : VALS[f[1]];
    for (const v of vals) {
      if (f[1] === "check") el.checked = v; else el.value = v;
      el.dispatchEvent(new w.Event("change", { bubbles: true }));
      calcRuns++;
      const out = box.lastChild;
      if (BAD.test(box.textContent) || !(out.querySelector("tr") || out.querySelector(".err"))) calcBad.push(kind + "." + f[0] + "=" + JSON.stringify(v));
    }
    if (f[1] === "check") el.checked = keep; else el.value = keep;
    el.dispatchEvent(new w.Event("change", { bubbles: true }));
  }
}
ok(calcBad.length === 0, `계산기 ${Object.keys(w.CALCS).length}종, ${calcRuns}가지 입력에 이상한 글자·빈 결과 없음` + (calcBad.length ? ": " + calcBad.slice(0, 5).join(", ") : ""));

// 모든 카드를 열고, 모든 근거 버튼을 눌러 원문과 인용 표시를 확인
const cards = w.DATA.cards;
let cites = 0, marked = 0, missing = [];
for (const c of cards) {
  w.pick(c);
  const a = top();
  if (!a.querySelector(".a-title")) { missing.push(c.id + " 답변 없음"); continue; }
  if (BAD.test(a.textContent)) missing.push(c.id + " 화면에 '" + a.textContent.match(BAD)[0] + "' 글자");
  a.querySelectorAll(".cite").forEach((b) => {
    cites++;
    b.click();
    const src = d.querySelector("#source-inner");
    if (/원문을 찾지 못했습니다/.test(src.textContent)) missing.push(c.id + " 원문 없음: " + b.textContent);
    else if (src.querySelector("mark")) marked++;
    else missing.push(c.id + " 인용 표시 못함: " + b.textContent);
  });
  a.remove();  // 카드 1천 장을 다 쌓으면 메모리가 넘친다
}
ok(missing.length === 0, `카드 ${cards.length}장 모두 열림, 근거 ${cites}개 중 원문 인용 표시 ${marked}개`);
missing.slice(0, 40).forEach((m) => console.log("   - " + m));
ok(errors.length === 0, "스크립트 오류 없음" + (errors.length ? ": " + errors.slice(0, 3).join(" / ") : ""));
