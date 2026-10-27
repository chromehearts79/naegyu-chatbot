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
const nFacts = w.DATA.cards.reduce((n, c) => n + c.facts.length, 0);
ok(new RegExp("근거 문구 " + nFacts.toLocaleString("en-US") + "곳").test(d.querySelector(".about-line").textContent) && !d.querySelector("#about details").open, "검증 정보는 한 줄 요약, 숫자는 '검증 방법 보기'에 접어 둠");
ok(d.querySelectorAll(".howto li").length === 3, "쓰는 법 3단계 안내");
{
  // 화면 색 고르기: 자동·밝게·어둡게
  const root = d.documentElement, pick3 = (v) => { d.querySelector(`#theme button[data-choice=${v}]`).click(); return root.getAttribute("data-theme"); };
  const pressed = () => d.querySelector("#theme button[aria-pressed=true]").dataset.choice;
  const start = pressed();
  const dark = pick3("dark") === "dark" && pressed() === "dark";
  const light = pick3("light") === "light" && pressed() === "light";
  const auto = pick3("auto") === null && pressed() === "auto";
  ok(start === "auto" && dark && light && auto && /:root\[data-theme="light"\] \{ color-scheme: light; \}/.test(html), "화면 색 고르기: 자동(처음)·밝게·어둡게가 바뀌고 누른 버튼이 표시됨");
}
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
ok(/빼는 방법이 정해져 있지 않음/.test(t.querySelector(".calc table").textContent) && !/8,330원 =/.test(t.querySelector(".calc table").textContent), "당일 출장 끼니 공제는 계산하지 않고 관련 부서 문의 안내");
t = ask("부산 1박2일 출장 여비");
ok(t.querySelector(".calc-link button"), "계산기 없는 답(국내 출장 종합 안내)에 '계산기 열기' 버튼");
t.querySelector(".calc-link button").click();
ok(t.querySelector(".calc [id$='-days']").value === "2" && t.querySelector(".calc [id$='-nights']").value === "1" && t.querySelector(".calc [id$='-region']").value === "metro" && /최대 180,000원/.test(t.querySelector(".calc table").textContent),
  "'부산 1박2일' → 버튼을 누르면 2일·1박·광역시를 채운 여비 계산기");
t = ask("팀원이 총 12명인데 S는 몇명나오나요?");
const gq = (n) => t.querySelector(".calc [id$='-" + n + "']"), grow = (g) => [...t.querySelectorAll(".calc tr")].find((tr) => tr.firstChild.textContent === g);
ok(/평가등급 배분/.test(title(t)) && /12명이라면/.test(t.querySelector(".a").textContent) && gq("size") && gq("size").value === "12" && !gq("senior") &&
  /함께 등급을 나누는 인원/.test(gq("size").closest("label").textContent) && grow("가(탁월)") && /^가\(탁월\)1명$/.test(grow("가(탁월)").textContent),
  "‘팀원 12명인데 S 몇 명’ → ‘그 인원이 12명이라면’으로 답하고, ‘함께 등급을 나누는 인원’ 한 칸 계산기(12명 → 가(탁월) 1명)");
const hint = document => t.querySelector("#" + gq("size").getAttribute("aria-describedby").split(" ")[0]);
ok(/팀 단위면 팀원 수, 실 단위면 실 인원/.test(t.querySelector(".calc").textContent) && /성과관리편람·운영기준/.test(t.querySelector(".calc").textContent) && hint() && /실 단위/.test(hint().textContent),
  "칸 아래 안내: 팀 단위면 팀원 수, 실 단위면 실 인원, 단위와 포함 인원은 편람·운영기준(화면 읽기 프로그램에도 칸 설명으로 연결)");
gq("size").value = "10"; gq("size").dispatchEvent(new w.Event("input", { bubbles: true }));
ok(/^다\(보통\)5명$/.test(grow("다(보통)").textContent) && /aria-describedby/.test(gq("size").outerHTML), "인원을 10명으로 바꾸면 다시 찾음(다 5명)");
// 돈·기간을 묻는 질문은 어떤 답이 나와도 계산기나 '계산기 열기'에 닿는다(평가단이 계산기를 못 찾았던 질문들)
const reach = ["출장비 얼마 받아요", "부산 1박2일 출장 여비", "출장 식비 얼마", "회의비로 밥 먹으면 출장비 깎여요?", "출장 가서 점심을 회사 돈으로 먹었어요",
  "연차 며칠이에요", "가족수당 얼마", "복지포인트 얼마 나와요", "아이 7살인데 육아휴직 돼요?", "출산휴가 언제부터 쓸 수 있어요", "장기재직휴가 언제 받아요", "가족돌봄휴가 유급 며칠"];
const lost = reach.filter((q) => { const x = ask(q); return !(x.querySelector(".calc") || x.querySelector(".calc-link")); });
ok(lost.length === 0, `돈·기간 질문 ${reach.length}개 모두 계산기에 닿음` + (lost.length ? ": " + lost.join(", ") : ""));
// 관련 조문 미리보기(규정 전체에서 찾은 조문)에 별표 표 태그·굵게 표시·표 칸막이가 날것으로 찍히지 않는지
{
  const RAWQ = /<\/?(?:td|tr|th|br|table)\b|\*\*|\|\s*---/;
  const rawBad = reach.concat(["서울 2박3일 출장 여비 얼마예요", "회사 근처 맛집 추천해줘", "오늘 날씨 어때", "경조사 휴가 며칠", "출장 숙박비 상한"]).filter((q) => {
    const x = ask(q); x.querySelectorAll("details").forEach((dd) => { dd.open = true; });
    return RAWQ.test(x.textContent);
  });
  ok(rawBad.length === 0, "답·관련 조문 미리보기에 표 태그(<td>)·굵게 표시(**)·표 칸막이가 날것으로 안 찍힘" + (rawBad.length ? ": " + rawBad.join(", ") : ""));
}
// 첫 화면 예시 질문은 맞는 카드와 계산기로 간다
const exWant = [/국내 출장 여비/, /연가\(연차\) 일수/, /복지포인트/, /가족수당/];
const exBad = exs.filter((q, i) => { const x = ask(q); return !exWant[i].test(title(x)) || !x.querySelector(".calc"); });
ok(exBad.length === 0, "예시 질문 4개 모두 맞는 답과 계산기" + (exBad.length ? ": " + exBad.join(", ") : ""));
// 출장 질문의 지명: 카드에 없는 지명(세종·춘천 …)도 목적지로만 보고 출장 답을 찾는다. '수원'이 '연수원'에 걸리지 않는다
{
  const trip = new Set(w.DATA.cards.filter((c) => (c.domain === "service" && c.topics.includes("trip")) || c.id === "combo-domestic-trip" ||
    (c.id.startsWith("r3-6-3-") && !/training|overseas/.test(c.id))).map((c) => c.id));
  const places = ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종시", "제주도", "수원", "성남", "춘천", "강릉", "청주", "천안", "전주시", "목포", "여수", "포항", "경주", "창원", "진주", "원주", "안동", "서귀포", "나주"];
  const forms = ["{p}로 시외출장을 가려고하는데 여비계산이 어떻게 됨?", "{p} 출장 여비 얼마예요?", "{p}에 1박2일 출장 가요. 숙박비 얼마까지 돼요?"];
  const bad = [];
  for (const p of places) for (const f of forms) {
    const q = f.replace("{p}", p), r = w.cardIndex.score(q), dec = w.E.decide(r, q, w.cardIndex.lastQuery);
    const top = dec.id || (dec.ids || [])[0], miss = (dec.missing || []).filter((m) => m.indexOf(p.replace(/(시|도)$/, "")) === 0 || /려고/.test(m));
    if (!trip.has(top) || miss.length) bad.push(q + " → " + top + (miss.length ? " (찾지 못함: " + miss.join(", ") + ")" : ""));
  }
  ok(bad.length === 0, `지명 ${places.length}개 × 출장 질문 3가지 모두 출장 답, 지명·'가려고하는데'를 모르는 낱말로 보지 않음` + (bad.length ? ": " + bad.slice(0, 3).join(" / ") : ""));
  // 지명이 곧 주제인 답, 헷갈리는 낱말, 출장 아닌 질문은 그대로(바꾸기 전과 같은 결과)
  const keep = [["제주 출장 일비 더 받나요", "r3-6-3-survey-allowance"], ["김포에서 김해 비행기 타도 돼요", "r3-6-3-domestic-flight"], ["광주지사 어디야", "r3-8-1-org-teams-branch"],
    ["연수원 교육 가면 여비 나와요?", "r3-6-3-training"], ["부산 1박2일 출장 여비", "combo-domestic-trip"]];
  const moved = keep.filter(([q, id]) => { const r = w.cardIndex.score(q), dec = w.E.decide(r, q, w.cardIndex.lastQuery); return (dec.id || (dec.ids || [])[0]) !== id; }).map((x) => x[0]);
  const dq = (q) => w.E.decide(w.cardIndex.score(q), q, w.cardIndex.lastQuery);
  const sejongMove = dq("세종시 이주 지원금 있어요?"), budget = dq("예산 범위 안에서 출장 가도 되나요"), alone = dq("세종");
  ok(moved.length === 0 && (sejongMove.missing || []).includes("세종시") && (budget.missing || []).includes("예산") && alone.mode === "fallback",
    "지명이 주제인 답(제주 일비 가산·김포·김해 항공·지사), 연수원, '예산', 출장 아닌 '세종시 이주', 지명만 묻기는 그대로" + (moved.length ? ": " + moved.join(", ") : ""));
  // 해외 출장에는 국내 여비 계산기를 붙이지 않는다
  t = ask("베트남 출장 일비 얼마예요");
  ok(!t.querySelector(".calc-link") && !t.querySelector(".calc"), "해외 출장 질문(베트남)에는 국내 여비 계산기를 붙이지 않음");
  // 세종: 숙박 지역 칸은 비워 두고 왜 비웠는지 알린다
  t = ask("세종시로 1박2일 출장 가면 여비 얼마예요?");
  if (!t.querySelector(".calc") && t.querySelector(".calc-link button")) t.querySelector(".calc-link button").click();
  const sc = t.querySelector(".calc");
  ok(sc && /세종특별자치시는 여비지급세칙 별표 제1호에 따로 적혀 있지 않습니다/.test(sc.textContent) && sc.querySelector("[id$='-region']").value === "",
    "세종 출장: 계산기에 '별표 제1호에 따로 없음, 관련 부서 문의' 안내, 숙박 지역 칸은 비워 둠");
}
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
// 줄바꿈: 문단 폭을 글자 수(ch)로 묶으면 칸이 넓어도 그 앞에서 줄이 바뀐다(계산기 안내가 '세칙 금액 / 그대로 계산).'처럼 끊겨 보였다).
// 글은 칸 끝까지 쓰고, 마지막 줄에 한두 낱말만 남지 않게 한다
ok(![...css.matchAll(/max-width:\s*[\d.]+ch/g)].length && /\.a p \{[^}]*text-wrap: pretty/.test(css), "문단 폭을 글자 수로 묶지 않음(칸 끝까지 쓰고 줄 끝을 고르게)");
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
ok(t.querySelector(".caution") && /관련 부서에 문의/.test(t.querySelector(".caution").textContent), "내규에 없을 수 있는 질문 → 관련 부서 문의 안내");
ok(!/담당부서에 확인|담당부서 기준/.test(d.querySelector("#notice").textContent + d.querySelector(".howto").textContent), "맨 위 안내·쓰는 법도 ‘관련 부서에 문의’로 같은 말");
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
const RAW = /<\/?(?:td|tr|th|br|table)\b|\*\*|\|\s*---/;
const VALS = { number: ["", "0", "1", "-3", "2.7", "30", "400"], date: ["", "1950-01-01", "2000-02-29", "2026-10-22", "2045-12-31"], yesno: ["", "y", "n"] };
// 필수 칸을 채운 기준값(이 값에서 한 칸씩 바꿔 본다)
const BASE = { spouseBirth: { due: "2026-12-01" }, maternity: { due: "2026-12-01" }, loss: { who: "self", date: "2026-10-01", weeks: "12" },
  childAge: { birth: "2020-03-01" }, familyCare: { children: "2" }, allowance: { spouse: "y", children: "2" }, annualLeave: { hire: "2021-03-02" },
  longService: { hire: "2014-03-02" }, welfarePoints: { years: "7", spouse: "y", children: "2" }, tripExpense: { days: "2", nights: "1", region: "metro" }, gradeQuota: { size: "12" } };
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
// 계산기 조작감: 고치는 도중의 값(연도를 치는 중, 지운 칸, 음수·소수)으로는 계산하지 않고, 마지막 결과를 흐리게 남겨 화면이 들썩이지 않게
{
  const put = (el, v) => { el.value = v; el.dispatchEvent(new w.Event("input", { bubbles: true })); };
  let box = w.renderCalc("annualLeave", "");
  const out = () => box.querySelector(".calc-out"), hire = box.querySelector("[id$='-hire']");
  put(hire, "2021-10-21");
  const fresh = out().querySelector("table") && !out().querySelector(".stale");
  put(hire, "0202-10-21");  // 크롬 날짜 칸은 연도를 한 글자씩 칠 때마다 0002 → 0020 → 0202 → 2021 로 바뀐다
  ok(fresh && !/1824년/.test(out().textContent) && /날짜를 끝까지/.test((out().querySelector(".need-msg") || {}).textContent) && out().querySelector(".stale table") &&
    hire.parentNode.classList.contains("need"), "날짜 연도를 치는 도중(0202년)에는 계산하지 않고 이전 결과를 흐리게 남김");
  put(hire, "2021-10-21");
  ok(out().querySelector("table") && !out().querySelector(".stale") && !out().querySelector(".need-msg"), "연도를 다 치면 바로 다시 계산");
  box = w.renderCalc("allowance", "");
  const kids = box.querySelector("[id$='-children']");
  ok(kids.getAttribute("step") === "1" && kids.getAttribute("inputmode") === "numeric", "숫자 칸은 정수만(step 1, 휴대폰은 숫자 자판)");
  box.querySelector("[id$='-spouse']").value = "y"; put(kids, "2");
  put(kids, "");
  const keptOnEmpty = out().querySelector(".stale table") && /확인 필요/.test((out().querySelector(".need-msg") || {}).textContent);
  put(kids, "1.5"); const dec = out().textContent;
  put(kids, "-1"); const neg = out().textContent;
  ok(keptOnEmpty && /0 이상의 정수/.test(dec) && /0 이상의 정수/.test(neg) && out().querySelector(".stale table"), "칸을 지우거나 음수·소수를 넣으면 계산하지 않고 알림(이전 결과는 흐리게 남김)");
  put(kids, "3");
  ok(/셋째부터 자녀 1명/.test(out().textContent) && !out().querySelector(".stale"), "다시 바른 값을 넣으면 그 값으로 바로 계산");
  box = w.renderCalc("tripExpense", "부산 1박2일 출장");
  const note = [...box.querySelectorAll("p.soft")].find((p) => /질문에서 읽/.test(p.textContent));
  put(box.querySelector("[id$='-days']"), "3");
  ok(note && !/출장 일수 2/.test(note.textContent) && /고친 값/.test(note.textContent), "질문에서 읽어 넣은 값을 고치면 '질문에서 읽어 넣었습니다(…)' 안내도 바뀜");
  put(box.querySelector("[id$='-days']"), "1");
  ok(out().querySelector(".err") && out().querySelector(".stale table"), "숙박이 출장 일수보다 많아지면 오류를 알리되 이전 결과는 흐리게 남김");
}
// 근거 조문이 개정된 계산기, 운영부서가 끈 계산기는 계산하지 않는다
w.DATA.meta.calcStale = { tripExpense: ["여비지급세칙 별표 제1호"] };
let cb = w.renderCalc("tripExpense", "부산 1박2일 출장");
ok(!cb.querySelector("form") && /개정돼 계산기 숫자를 다시 확인/.test(cb.textContent), "근거 조문이 개정된 계산기는 계산 멈춤");
w.DATA.meta.calcStale = {}; w.DATA.meta.site.calcOff = ["allowance"];
cb = w.renderCalc("allowance", "");
ok(!cb.querySelector("form") && /점검 중/.test(cb.textContent), "운영부서가 끈 계산기(calcOff)는 '점검 중'");
w.DATA.meta.site.calcOff = [];

// 내규나침반: 같은 입력칸에서 고르면 왼쪽에 낱말이 나오는 내규 목록, 오른쪽에 고른 내규의 원문 전체(찾은 곳 표시)를 보여 준다
{
  const wrap = d.querySelector(".wrap"), btn = (m) => d.querySelector(`#modes button[data-mode=${m}]`);
  btn("compass").click();
  ok(wrap.classList.contains("compassing") && btn("compass").getAttribute("aria-pressed") === "true" && d.querySelector("#ask-btn").textContent === "찾기" &&
    /내규 71개 원문/.test(d.querySelector("#compass-help").textContent) && d.querySelector("#examples").classList.contains("ask-only"),
    "나침반 고르면 '찾기' 단추와 안내가 나오고 예시 질문은 숨김");
  ok(/\.compassing \.source \{ display: none; \}/.test(html) && /\.wrap\.compassing \{ max-width: 1200px; \}/.test(html), "나침반은 화면 너비를 다 쓰고 챗봇 근거 원문 칸은 숨김");
  // 같은 입력칸·같은 단추. 나침반 결과는 챗봇 대화와 다른 칸(#compass-thread)에 하나만
  const compassBad = [];
  const find = (q) => {
    d.querySelector("#q").value = q; d.querySelector("#ask-form").dispatchEvent(new w.Event("submit", { cancelable: true }));
    const x = d.querySelector("#compass-thread .turn"); if (x && BAD.test(x.textContent)) compassBad.push(q); return x;
  };
  const rules = (c) => [...c.querySelectorAll(".clist .rl")];
  const pane = (c) => c.querySelector(".cpane"), lab = (c) => pane(c).querySelector(".cnav span").textContent;
  const now = (c) => pane(c).querySelector("mark.now"), chips = (c) => [...pane(c).querySelectorAll(".jump button")];
  let c = find("법인카드");
  ok(c.querySelector(".q .tag").textContent === "나침반" && /글자 그대로 7곳 · 내규 5개/.test(c.querySelector(".pill").textContent) && rules(c).length === 5,
    "‘법인카드’ → 왼쪽에 내규 5개");
  ok(/법인카드 관리 및 사용지침/.test(c.querySelector(".named").textContent) && /^법인카드 관리 및 사용지침\s*12$/.test(rules(c)[0].textContent.trim()) &&
    rules(c)[0].getAttribute("aria-pressed") === "true", "이름에 든 내규는 위 칸에, 목록은 많이 나오는 순(2곳 + 줄인 말 10곳 = 12)이고 첫 내규를 골라 둠");
  ok(pane(c).querySelector("h3").textContent === "법인카드 관리 및 사용지침" && pane(c).querySelectorAll("section.art").length === 12 && /‘법인카드·카드’ 1\/\d+/.test(lab(c)) &&
    [...pane(c).querySelectorAll("mark.sim")].some((m) => m.textContent === "카드") && pane(c).querySelector(".legend"),
    "오른쪽에 그 내규 원문 전체, 넣은 낱말은 노란색·줄인 말 ‘카드’는 파란색");
  ok(chips(c).map((b) => b.textContent).join(",") === "제1조,제2조,제3조,제4조,제5조,제6조,제7조,제8조,제9조,제10조,제11조,제12조", "찾은 조문 바로가기 단추(조문 순서)");
  rules(c).find((b) => /^해외사무소운영세칙/.test(b.textContent)).click();
  ok(pane(c).querySelector("h3").textContent === "해외사무소운영세칙" && /‘법인카드’ 1\/3/.test(lab(c)) && now(c).closest("section").dataset.no === "제27조" &&
    chips(c).map((b) => b.textContent).join(",") === "제27조,제28조" && c.querySelector(".cbody").classList.contains("picked"),
    "왼쪽에서 다른 내규를 누르면 오른쪽이 그 내규로 바뀌고 첫 번째 낱말에 가 있음(1/3)");
  chips(c)[1].click();
  const atChip = lab(c), chipOn = chips(c)[1].getAttribute("aria-current");
  const [up, down] = pane(c).querySelectorAll(".cnav button");
  down.click(); const third = lab(c); up.click(); up.click(); up.click();
  ok(/2\/3/.test(atChip) && now(c).closest("section").dataset.no === "제28조" && chipOn === "true" && /3\/3/.test(third) && /3\/3/.test(lab(c)) && pane(c).querySelectorAll("mark.now").length === 1,
    "바로가기 단추로 그 조문의 낱말로 건너뛰고, ▲▼로 하나씩(처음에서 ▲면 마지막으로)");
  ok([...pane(c).querySelectorAll(".cnav button, .back")].some((x) => /내규 목록/.test(x.textContent)), "휴대폰 폭에서 목록으로 돌아가는 단추");
  pane(c).querySelector(".back").click();
  ok(!c.querySelector(".cbody").classList.contains("picked") && /\.cbody:not\(\.picked\) \.cpane \{ display: none; \}/.test(html), "‘← 내규 목록’을 누르면 목록으로(휴대폰 폭에서는 목록과 원문을 번갈아 보임)");
  c = find("출장");
  const more = c.querySelector(".clist .more");
  ok(/공무국외출장세부지침/.test(c.querySelector(".named").textContent) && /^여비지급세칙\s*17$/.test(rules(c)[0].textContent.trim()) &&
    rules(c).filter((b) => !b.hidden).length === 8 && more && /10개/.test(more.textContent), "‘출장’: 여비지급세칙(17)부터, 9번째부터는 접어 둠");
  more.click();
  ok(rules(c).filter((b) => !b.hidden).length === 18 && !c.querySelector(".clist .more"), "‘더 보기’를 누르면 18개 모두");
  c = find("반차");
  ok(/글자 그대로 나오는 곳이 없습니다/.test(c.textContent) && /‘반일연가’/.test(c.textContent) && /반반차/.test(c.textContent) && /^복무세칙/.test(rules(c)[0].textContent.trim()),
    "‘반차’ → 원문에 없다고 먼저 알리고, ‘반일연가’로 찾은 복무세칙을 맨 앞에, 반반차는 내규에 없음");
  ok(pane(c).querySelector("h3").textContent === "복무세칙" && [...pane(c).querySelectorAll("mark.sim")].some((m) => m.textContent === "반일연가") && /반일연가/.test(pane(c).querySelector(".why").textContent),
    "비슷한 말은 파란색, 이 내규를 보여 주는 이유도 씀");
  c = find("장");
  ok(/두 글자 이상/.test(c.textContent) && !c.querySelector(".cbody"), "한 글자는 찾지 않고 안내");
  c = find("직원");
  ok(/많이 나오는 낱말/.test(c.textContent) && rules(c).length > 50 && rules(c).filter((b) => !b.hidden).length === 8, "넓은 낱말은 8개만 보이고 좁히는 법 안내");
  c = find("직원 징계");
  ok(/‘직원’·‘징계’ 함께 나오는 곳/.test(c.querySelector(".a-title").textContent) && /‘직원·징계’/.test(lab(c)), "두 낱말이면 함께 나오는 곳");
  c = find("유니폼");
  ok(/찾지 못했습니다/.test(c.textContent) && !c.querySelector(".cbody"), "아무것도 못 찾으면 목록 없이 안내");
  ok(compassBad.length === 0, "나침반 결과에 'null' 같은 글자 없음" + (compassBad.length ? ": " + compassBad.join(", ") : ""));
  // 결과는 하나만, 지난 낱말은 '최근 찾은 낱말' 단추로
  const recentC = () => [...d.querySelectorAll("#recent-compass .chip")].map((b) => b.textContent);
  ok(d.querySelectorAll("#compass-thread .turn").length === 1 && /유니폼/.test(d.querySelector("#compass-thread .q").textContent) &&
    ![...d.querySelectorAll("#thread .tag")].some((x) => x.textContent === "나침반"),
    "나침반 결과는 하나만 보이고(새로 찾으면 이전 결과를 지움) 챗봇 대화 칸에 섞이지 않음");
  ok(!d.querySelector("#recent-compass").hidden && recentC()[0] === "유니폼" && recentC().includes("직원 징계") && recentC().length === 6,
    "최근 찾은 낱말이 단추로 보임(최근 것이 맨 앞, 6개까지)");
  find("법인카드");
  [...d.querySelectorAll("#recent-compass .chip")].find((b) => b.textContent === "반차").click();
  ok(/‘반차’ 나오는 곳/.test(d.querySelector("#compass-thread .a-title").textContent) && d.querySelectorAll("#compass-thread .turn").length === 1 && recentC()[0] === "반차",
    "최근 찾은 낱말 단추를 누르면 그 낱말로 다시 찾음");
  ok(/\.rl \{[^}]*color: var\(--accent\)/.test(html), "내규 이름은 강조색(청록)으로 조문 글씨와 구분");
  btn("ask").click();
  ok(!wrap.classList.contains("compassing") && d.querySelector("#ask-btn").textContent === "묻기" && /배우자 출산전후휴가/.test(title(ask("배우자 출산휴가 며칠이에요?"))),
    "질문하기로 돌아오면 다시 준비된 답을 찾음");
  // 내규챗봇도 결과는 하나만, 지난 질문은 '최근 질문' 단추로
  const t2 = ask("가족수당 얼마예요");
  const recentA = () => [...d.querySelectorAll("#recent-ask .chip")].map((b) => b.textContent);
  ok(d.querySelectorAll("#thread .turn").length === 1 && t2 === top() && !d.querySelector("#recent-ask").hidden && recentA()[0] === "가족수당 얼마예요" && recentA().includes("배우자 출산휴가 며칠이에요?"),
    "챗봇 답도 하나만 보이고 최근 질문이 단추로 보임");
  [...d.querySelectorAll("#recent-ask .chip")].find((b) => b.textContent === "배우자 출산휴가 며칠이에요?").click();
  ok(/배우자 출산전후휴가/.test(title(top())) && d.querySelectorAll("#thread .turn").length === 1, "최근 질문 단추를 누르면 그 질문으로 다시 찾음");
  btn("compass").click();
  ok(d.querySelector("#compass-thread .turn") && /반차/.test(d.querySelector("#compass-thread .a-title").textContent) && d.querySelector("#recent-compass").classList.contains("compass-only"),
    "나침반으로 돌아가면 하던 나침반 결과가 그대로");
  d.querySelector("#compass-thread .caution .linkish").click();
  ok(!wrap.classList.contains("compassing") && /반반차/.test(title(top())), "‘내규에 없음’의 ‘챗봇 답 보기’는 질문하기로 넘어가 그 답을 보여 줌");
  // 낱말 경계: 다른 낱말 속·엉뚱하게 띄어 걸린 곳은 접고(원문에서 점선, 세지 않음), 걸린 말별 단추로 켜고 끈다
  btn("compass").click();
  const gchips = (x) => [...x.querySelectorAll(".groups .gchip")], gchip = (x, re) => gchips(x).find((b) => re.test(b.firstChild.textContent));
  c = find("여비");
  ok(/^여비지급세칙/.test(rules(c)[0].textContent.trim()) && !rules(c).some((b) => /^(정관|보안업무처리세칙|정보보안지침)\s*\d/.test(b.textContent.trim())),
    "‘여비’: ‘위하여 비상임’처럼 엉뚱하게 띄어 걸린 곳만 있는 내규(정관·정보보안지침 등)는 목록에 없음");
  c = find("인정");
  const pi = gchip(c, /^개인정보$/);
  ok(pi && pi.getAttribute("aria-pressed") === "false" && pi.classList.contains("fold") && gchip(c, /^인정$/).getAttribute("aria-pressed") === "true" && /다른 낱말 속에서 걸린 \d+곳/.test(c.textContent),
    "‘인정’: 걸린 말별 단추, ‘개인정보’ 묶음은 ‘다른 낱말 속’으로 꺼 두고 몇 곳인지 알림");
  const pps = () => rules(c).find((b) => /^개인정보보호세칙/.test(b.textContent.trim())), nPps = +pps().lastChild.textContent;
  pps().click();
  const offs = pane(c).querySelectorAll(".law-all mark.off").length, ons = pane(c).querySelectorAll(".law-all mark:not(.off)").length;
  ok(offs > 0 && ons > 0 && new RegExp("/" + ons + "$").test(lab(c)) && /점선/.test(pane(c).querySelector(".legend").textContent),
    "원문에서 ‘개인정보’ 속 ‘인정’은 점선(세지 않음), 실제 ‘인정’만 노란색으로 세고 ▲▼로 오감");
  ok(chips(c).every((b) => !/개$/.test(b.title.split("인정")[0] || "")), "바로가기 단추의 미리보기도 실제 ‘인정’을 보여 줌");
  pi.click();
  ok(pi.getAttribute("aria-pressed") === "true" && +pps().lastChild.textContent > nPps, "‘개인정보’ 단추를 누르면 그 묶음도 목록에 들어옴(개인정보보호세칙 " + nPps + " → " + pps().lastChild.textContent + "곳)");
  pps().click();
  ok(pane(c).querySelectorAll(".law-all mark.off").length < offs, "켠 묶음은 원문에서도 노란색으로 세어짐");
  c = find("이사");
  const hw = gchip(c, /^이사화물$/);
  ok(hw && hw.getAttribute("aria-pressed") === "true" && gchip(c, /^이사회$/), "‘이사’: 이사회(임원)와 이사화물(이사 가기)이 다른 단추");
  const yb = () => ((rules(c).find((b) => /^여비지급세칙/.test(b.textContent.trim())) || { textContent: "없음" }).textContent.trim());
  const yb0 = yb();
  hw.click();
  ok(hw.getAttribute("aria-pressed") === "false" && yb() !== yb0, "‘이사화물’ 단추를 끄면 그 말로만 걸린 조문이 목록에서 빠짐(" + yb0 + " → " + yb() + ")");
  ok(/\.law mark\.off \{/.test(html) && /\.gchip\[aria-pressed="true"\]/.test(html), "점선 표시·묶음 단추 모양");
  btn("ask").click();
  d.querySelectorAll("#thread .turn, #compass-thread .turn").forEach((x) => x.remove());
}

// 모든 카드를 열고, 모든 근거 버튼을 눌러 원문과 인용 표시를 확인
const cards = w.DATA.cards;
let cites = 0, marked = 0, missing = [];
for (const c of cards) {
  w.pick(c);
  const a = top();
  if (!a.querySelector(".a-title")) { missing.push(c.id + " 답변 없음"); continue; }
  if (BAD.test(a.textContent)) missing.push(c.id + " 화면에 '" + a.textContent.match(BAD)[0] + "' 글자");
  // 날것 기호: 별표 표 태그(<td> 등)·굵게 표시(**)·마크다운 표 칸막이가 화면 글자로 찍히면 안 된다(관련 조문 미리보기 포함)
  if (RAW.test(a.textContent)) missing.push(c.id + " 화면에 날것 기호 '" + a.textContent.match(RAW)[0] + "'");
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
