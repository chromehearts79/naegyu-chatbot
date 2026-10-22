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

// 첫 화면 정리(디자인 개선 2단계): 자주 찾는 분야, 모든 분야 보기, 원문 칸 접기, 한 문장 안내, 검증 한 줄 요약
const FEAT = w.DATA.meta.site.featured || [];
const featChips = [...d.querySelectorAll("#featured .chip")];
ok(FEAT.length >= 8 && featChips.length === FEAT.length, `자주 찾는 분야 ${featChips.length}개`);
const rowNames = [...d.querySelectorAll("#topics .topic-group > span")].map((x) => x.textContent);
ok(!d.querySelector(".all-topics").open && rowNames.length === 1 && rowNames[0] === "규정 전체" && d.querySelectorAll("#topics .chip").length === 11,
  "모든 분야 보기는 접혀 있고, 시범 분야(출산·육아·복무)는 자주 찾는 분야로 합쳐 따로 줄이 없음");
const allRefs = w.DATA.domains.flatMap((dm) => dm.topics.map((t) => dm.id + ":" + t.id));
const shownRefs = new Set([...FEAT.flatMap((f) => f.topics), ...w.DATA.domains.filter((dm) => rowNames.includes(dm.name)).flatMap((dm) => dm.topics.map((t) => dm.id + ":" + t.id))]);
ok(allRefs.every((r) => shownRefs.has(r)), `주제 ${allRefs.length}개 모두 자주 찾는 분야나 모든 분야 보기에서 닿음`);
const emptyFeat = featChips.filter((b) => { b.click(); const x = d.querySelector("#thread .turn"); const n = x.querySelectorAll(".cand").length; x.remove(); return !n; }).map((b) => b.textContent);
ok(emptyFeat.length === 0, "자주 찾는 분야 버튼마다 답 목록이 나옴" + (emptyFeat.length ? ": " + emptyFeat.join(", ") : ""));
ok(!d.querySelector(".wrap").classList.contains("reading") && d.querySelector("#source").dataset.open === "false", "처음에는 오른쪽 원문 칸을 접어 둠");
const notice = d.querySelector("#notice");
ok(/AI가 쓴 답/.test(notice.textContent) && notice.querySelector("details") && !notice.querySelector("details").open && /검수 전/.test(notice.querySelector("details").textContent), "맨 위 안내는 한 문장, 표시의 뜻은 '자세히'에 접어 둠");
ok(/근거 문구 6,671곳/.test(d.querySelector(".about-line").textContent) && !d.querySelector("#about details").open, "검증 정보는 한 줄 요약, 숫자는 '검증 방법 보기'에 접어 둠");
ok(d.querySelectorAll(".howto li").length === 3, "쓰는 법 3단계 안내");
ok(!top(), "처음 화면에 미리 띄운 예시 답변 없음");
const exs = [...d.querySelectorAll("#examples .chip")].map((b) => b.textContent);
ok(exs.length === 4 && /출장/.test(exs[0]) && /연차|연가/.test(exs[1]) && /복지포인트/.test(exs[2]) && /가족수당/.test(exs[3]), "예시 질문 4개: 출장비·연가·복지포인트·가족수당");
ok(/^제\d+판 · \d{4}\.\d{2}\.\d{2}\. 만듦/.test(d.querySelector("#basis").textContent), "맨 위에 판 번호와 만든 날");
ok(!/출산/.test(d.querySelector("#q").placeholder), "입력칸 안내 문구가 특정 분야에 치우치지 않음");
ok(d.querySelectorAll("#about .stat").length === 6, "검증 정보 숫자 6칸");
ok(!/null|undefined/.test(d.querySelector("#about").textContent), "검증 정보에 'null' 같은 글자 없음");

// 바로 답이면 그 제목, 되묻기면 아래에 펼친 '가장 가까운 답'의 제목
const title = (t) => (t.querySelector(".lead .a-title") || t.querySelector(".a-title")).textContent;
function ask(q) { d.querySelector("#q").value = q; d.querySelector("#ask-form").dispatchEvent(new w.Event("submit", { cancelable: true })); return top(); }
let t = ask("배우자 출산휴가 며칠이에요?");
ok(/배우자 출산전후휴가/.test(title(t)), "질문 → 배우자 출산전후휴가 답변");
ok(t.querySelectorAll(".facts tbody tr").length === 7, "답변 핵심 정리 7줄");
ok(!t.querySelector(".calc table") && /출산예정일/.test(t.querySelector(".calc .need-msg").textContent), "날짜 없는 질문: 출산예정일을 '확인 필요'로 비우고 계산하지 않음");
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
ok(d.querySelector(".wrap").classList.contains("reading") && d.querySelector("#source").dataset.open === "true", "근거를 누르면 원문 칸이 열림");
d.querySelector("#source-close").click();
ok(!d.querySelector(".wrap").classList.contains("reading") && d.querySelector("#source").dataset.open === "false", "닫기를 누르면 원문 칸이 다시 접힘");

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
const tf = (n) => t.querySelector(".calc [id$='-" + n + "']");
ok(!t.querySelector(".calc table") && t.querySelectorAll(".calc label.need").length === 3, "여비 계산기: 일수·숙박·지역을 모르면 '확인 필요' 3칸, 금액 없음");
tf("days").value = "2"; tf("nights").value = "1"; tf("region").value = "metro"; tf("region").dispatchEvent(new w.Event("change", { bubbles: true }));
ok(/최대 180,000원/.test(t.querySelector(".calc table").textContent), "여비 계산기: 2일·1박·광역시 → 최대 180,000원");
const meals = t.querySelector(".calc input[id$='-meals']");
meals.value = "3"; meals.dispatchEvent(new w.Event("input", { bubbles: true }));
ok(/3끼 × 8,330원 = 25,010원/.test(t.querySelector(".calc table").textContent) && /10원이 남습니다/.test(t.querySelector(".calc").textContent), "여비 계산기: 다른 예산으로 먹은 3끼 → 식비 25,010원(10원 남는 이유 안내)");
tf("days").value = "1"; tf("nights").value = "0"; meals.value = "1"; meals.dispatchEvent(new w.Event("input", { bubbles: true }));
ok(/빼는 방법이 정해져 있지 않음/.test(t.querySelector(".calc table").textContent) && !/8,330원 =/.test(t.querySelector(".calc table").textContent), "당일 출장 끼니 공제는 계산하지 않고 회계 담당 확인 안내");
t = ask("부산 1박2일 출장 여비");
ok(t.querySelector(".calc-link button"), "계산기 없는 답(국내 출장 종합 안내)에 '계산기 열기' 버튼");
t.querySelector(".calc-link button").click();
ok(t.querySelector(".calc [id$='-days']").value === "2" && t.querySelector(".calc [id$='-nights']").value === "1" && t.querySelector(".calc [id$='-region']").value === "metro" && /최대 180,000원/.test(t.querySelector(".calc table").textContent),
  "'부산 1박2일' → 버튼을 누르면 2일·1박·광역시를 채운 여비 계산기");
// 돈·기간을 묻는 질문은 어떤 답이 나와도 계산기나 '계산기 열기'에 닿는다(평가단이 계산기를 못 찾았던 질문들)
const reach = ["출장비 얼마 받아요", "부산 1박2일 출장 여비", "출장 식비 얼마", "회의비로 밥 먹으면 출장비 깎여요?", "출장 가서 점심을 회사 돈으로 먹었어요",
  "연차 며칠이에요", "가족수당 얼마", "복지포인트 얼마 나와요", "아이 7살인데 육아휴직 돼요?", "출산휴가 언제부터 쓸 수 있어요", "장기재직휴가 언제 받아요", "가족돌봄휴가 유급 며칠"];
const lost = reach.filter((q) => { const x = ask(q); return !(x.querySelector(".calc") || x.querySelector(".calc-link")); });
ok(lost.length === 0, `돈·기간 질문 ${reach.length}개 모두 계산기에 닿음` + (lost.length ? ": " + lost.join(", ") : ""));
// 첫 화면 예시 질문은 맞는 카드와 계산기로 간다
const exWant = [/국내 출장 여비/, /연가\(연차\) 일수/, /복지포인트/, /가족수당/];
const exBad = exs.filter((q, i) => { const x = ask(q); return !exWant[i].test(title(x)) || !x.querySelector(".calc"); });
ok(exBad.length === 0, "예시 질문 4개 모두 맞는 답과 계산기" + (exBad.length ? ": " + exBad.join(", ") : ""));
t = ask("지하철비용은 일비에 포함됨?");
ok(/지하철/.test(title(t)), "지하철비용 일비 질문 → 지하철·버스 요금과 일비");
// 평가단 지적 반영 확인
ok(!/<link[^>]+href=["']https?:|<script[^>]+src=|@import|url\(\s*["']?https?:/i.test(html), "외부 주소(글꼴·스크립트)를 부르지 않음");
ok((html.match(/@font-face\{font-family:"A2Z"/g) || []).length === 4, "에이투지체 4가지 굵기가 파일 안에 들어 있음");
// 디자인 기본기(docs/디자인_개선_계획.md 1단계): 글씨 대비, 테두리 대비, 글씨 크기, 누르는 크기, 화면 읽기 프로그램, 여는 동안 안내
const cssAt = html.lastIndexOf("<style>", html.indexOf("--paper:")), css = html.slice(cssAt, html.indexOf("</style>", cssAt));
const lum = (h) => { const c = [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4)); return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]; };
const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
const themes = [...css.matchAll(/--paper: (#[0-9a-f]{6})[\s\S]*?--ink-3: (#[0-9a-f]{6})[\s\S]*?--line-strong: (#[0-9a-f]{6})/g)].map((m) => {
  const tok = (name) => (css.slice(m.index).match(new RegExp("--" + name + ": (#[0-9a-f]{6})")) || [])[1];
  return { ink3: [tok("paper"), tok("surface"), tok("sunk"), tok("hl")].map((bg) => ratio(m[2], bg)), line: ratio(m[3], tok("surface")) };
});
ok(themes.length === 3 && themes.every((t) => Math.min(...t.ink3) >= 4.5 && t.line >= 3), "흐린 글씨 대비 4.5:1 이상, 입력칸·버튼 테두리 3:1 이상(밝은·어두운 화면) " +
  themes.map((t) => Math.min(...t.ink3).toFixed(2) + "/" + t.line.toFixed(2)).join(" "));
const sizes = [...css.matchAll(/font-size:\s*([\d.]+)px/g)].map((m) => +m[1]);
ok(sizes.length > 20 && Math.min(...sizes) >= 12 && /body \{[^}]*font-size: 16px/.test(css), "본문 16px, 12px보다 작은 글씨 없음(가장 작은 글씨 " + Math.min(...sizes) + "px)");
ok(/\.cite \{[^}]*min-height: 24px/.test(css) && /@media \(max-width: 999px\) \{\s*\.chip, \.btn\.ghost[^}]*min-height: 44px/.test(css), "누르는 크기: 근거 조문 24px 이상, 휴대폰에서 버튼 44px 이상");
ok(!d.querySelector("#loading") && /여는 중/.test(html) && d.querySelector("#ask-form").getAttribute("onsubmit") === "return false", "여는 동안 안내가 있고 다 열리면 사라짐, 열리기 전 '묻기'로 화면이 다시 열리지 않음");
{
  const box = w.renderCalc("tripExpense", "");
  const days = box.querySelector("[id$='-days']"), live = box.querySelector("[role=status]");
  const desc = d.getElementById(days.getAttribute("aria-describedby") || "x") || box.querySelector("#" + days.getAttribute("aria-describedby"));
  const before = days.getAttribute("aria-invalid") === "true" && days.getAttribute("aria-required") === "true" && desc && /확인 필요/.test(desc.textContent) && /확인 필요/.test(live.textContent);
  days.value = "2"; box.querySelector("[id$='-nights']").value = "1"; box.querySelector("[id$='-region']").value = "metro";
  box.querySelector("[id$='-region']").dispatchEvent(new w.Event("change", { bubbles: true }));
  const after = days.getAttribute("aria-invalid") === "false" && !days.hasAttribute("aria-describedby") && /계산 결과: 일비/.test(live.textContent) && box.querySelector(".calc-out").getAttribute("aria-live") === "off";
  ok(before && after, "계산기: 빈 필수 칸은 화면 읽기 프로그램에도 '확인 필요'(aria-invalid·describedby), 결과는 한 줄로 알림");
}
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
ok(dIn && dIn.value === "2023-03-02" && /질문에서 읽어 넣었습니다/.test(t.textContent), "질문 속 날짜를 계산기에 채움");
ok(![...d.querySelectorAll("button")].some((b) => /도움이 됐어요/.test(b.textContent)), "기록 안 남는 '도움이 됐어요' 버튼 없음");

// 모든 계산기: 질문에서 못 읽은 칸은 비워 두고 계산하지 않는지, 칸마다 여러 값을 넣어도 'null' 같은 글자 없이 결과·안내가 나오는지
const BAD = /null|undefined|NaN|Invalid|Infinity|\[object/;
const VALS = { number: ["", "0", "1", "-3", "2.7", "30", "400"], date: ["", "1950-01-01", "2000-02-29", "2026-10-22", "2045-12-31"], yesno: ["", "y", "n"] };
// 필수 칸을 채운 기준값(이 값에서 한 칸씩 바꿔 본다)
const BASE = { spouseBirth: { due: "2026-12-01" }, maternity: { due: "2026-12-01" }, loss: { who: "self", date: "2026-10-01", weeks: "12" },
  childAge: { birth: "2020-03-01" }, familyCare: { children: "2" }, allowance: { spouse: "y", children: "2" }, annualLeave: { hire: "2021-03-02" },
  longService: { hire: "2014-03-02" }, welfarePoints: { years: "7", spouse: "y", children: "2" }, tripExpense: { days: "2", nights: "1", region: "metro" } };
const fire = (el) => el.dispatchEvent(new w.Event("change", { bubbles: true }));
let calcRuns = 0; const calcBad = [], emptyBad = [];
for (const kind of Object.keys(w.CALCS)) {
  const box = w.renderCalc(kind, "");
  const out = () => box.querySelector(".calc-out");
  if (out().querySelector("tr") || !out().querySelector(".need-msg") || !box.querySelector("label.need")) emptyBad.push(kind);
  const field = (n) => box.querySelector("[id$='-" + n + "']");
  for (const [n, v] of Object.entries(BASE[kind] || {})) { field(n).value = v; fire(field(n)); }
  if (!out().querySelector("tr")) calcBad.push(kind + " 기준값으로 결과 없음: " + out().textContent);
  for (const f of w.CALCS[kind].fields) {
    const el = field(f[0]), keep = f[1] === "check" ? el.checked : el.value;
    const vals = f[1] === "check" ? [true, false] : f[1] === "select" ? f[4].map((o) => o[0]) : VALS[f[1]];
    for (const v of vals) {
      if (f[1] === "check") el.checked = v; else el.value = v;
      fire(el);
      calcRuns++;
      if (BAD.test(box.textContent) || !(out().querySelector("tr") || out().querySelector(".err") || out().querySelector(".need-msg"))) calcBad.push(kind + "." + f[0] + "=" + JSON.stringify(v));
    }
    if (f[1] === "check") el.checked = keep; else el.value = keep;
    fire(el);
  }
}
ok(emptyBad.length === 0, "질문에서 못 읽은 칸은 '확인 필요'로 비워 두고 금액·기간을 계산하지 않음" + (emptyBad.length ? ": " + emptyBad.join(", ") : ""));
ok(calcBad.length === 0, `계산기 ${Object.keys(w.CALCS).length}종, ${calcRuns}가지 입력에 이상한 글자·빈 결과 없음` + (calcBad.length ? ": " + calcBad.slice(0, 5).join(", ") : ""));
// 근거 조문이 개정된 계산기, 운영부서가 끈 계산기는 계산하지 않는다
w.DATA.meta.calcStale = { tripExpense: ["여비지급세칙 별표 제1호"] };
let cb = w.renderCalc("tripExpense", "부산 1박2일 출장");
ok(!cb.querySelector("form") && /개정돼 계산기 숫자를 다시 확인/.test(cb.textContent), "근거 조문이 개정된 계산기는 계산 멈춤");
w.DATA.meta.calcStale = {}; w.DATA.meta.site.calcOff = ["allowance"];
cb = w.renderCalc("allowance", "");
ok(!cb.querySelector("form") && /점검 중/.test(cb.textContent), "운영부서가 끈 계산기(calcOff)는 '점검 중'");
w.DATA.meta.site.calcOff = [];

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
