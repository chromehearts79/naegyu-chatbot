// 검색 엔진과 계산기 시험.
//  1) 예상 질문 하나씩 빼고 찾기(leave-one-out): 처음 보는 표현을 얼마나 맞히는지
//  2) 카드에 없는 시험 질문(_devset.json): 답·되묻기·조문 검색 판단이 맞는지
//  3) 계산기 결과가 손으로 계산한 값과 같은지
const fs = require("fs");
const path = require("path");
const assert = require("assert");
const E = require("../web/engine.js");

const L = require("./load_cards.js");
const cards = L.cards();
const dev = L.devset();
// 고치기 전에 써서 얼려 둔 새 시험 질문(knowledge/holdout.json). 오답을 고칠 때 보지 않은 질문이라 고친 효과를 정직하게 잰다
const holdout = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "knowledge", "holdout.json"), "utf8")).items;
const idx = new E.CardIndex(cards);
const byId = new Map(cards.map((c) => [c.id, c]));
const verbose = process.argv.includes("-v");
// 같은 내용을 두 규정이 옮겨 적은 카드 쌍(knowledge/same_content.json): 어느 쪽으로 답해도 맞음
const same = new Map();
JSON.parse(fs.readFileSync(path.join(__dirname, "..", "knowledge", "same_content.json"), "utf8")).pairs.forEach((p) => {
  p.cards.forEach((a) => { if (!byId.has(a)) throw new Error("same_content.json 에 없는 카드: " + a); p.cards.forEach((b) => { if (a !== b) (same.get(a) || same.set(a, new Set()).get(a)).add(b); }); });
});
// 정답 카드 want 대신 got 으로 답해도 같은 답인지: 같은 내용 쌍, 또는 종합 카드와 그 카드가 묶은 카드
const sameAnswer = (want, got) => want === got || (same.get(want) || new Set()).has(got) ||
  (got.startsWith("combo-") && (byId.get(got).related || []).includes(want)) || (want.startsWith("combo-") && (byId.get(want).related || []).includes(got));

// 0) 시험 질문을 정답 카드의 예상 질문에 베끼지 않았는지(글자 조각이 60% 넘게 겹치면 알림). 베끼면 시험이 처음 보는 질문을 재지 못한다
const grams = (t) => { const x = String(t).replace(/[^0-9a-z가-힣]/gi, ""), g = new Set(); for (let i = 0; i + 1 < x.length; i++) g.add(x.slice(i, i + 2)); return g; };
const cardQs = cards.flatMap((c) => c.questions.map((q) => ({ id: c.id, q, g: grams(q) })));
const leaks = [];
for (const it of dev.concat(holdout)) {
  const g = grams(it.q);
  let best = null, bj = 0;
  const counts = (id) => it.expect.some((y) => byId.has(y) && sameAnswer(y, id));
  for (const cq of cardQs) {
    if (!counts(cq.id)) continue;
    let inter = 0; g.forEach((k) => { if (cq.g.has(k)) inter++; });
    const j = inter / (g.size + cq.g.size - inter || 1);
    if (j > bj) { bj = j; best = cq; }
  }
  if (bj >= 0.6) leaks.push(`${it.q} ≈ [${best.id}] ${best.q} (${Math.round(bj * 100)}%)`);
}
console.log(`[0] 시험 질문과 거의 같은 카드 예상 질문: ${leaks.length}개` + (leaks.length ? " — 카드에서 빼거나 표현을 바꿀 것" : ""));
leaks.forEach((l) => console.log("    ! " + l));

// 1) leave-one-out
let n = 0, top1 = 0, top3 = 0, okSame = 0;
const modes = { answer: 0, ask: 0, fallback: 0 }, misses = [];
for (const c of cards) {
  c.questions.forEach((q, qi) => {
    const ranked = idx.score(q, (d) => d.card === c.id && d.kind === "q" && d.qi === qi);
    const dec = E.decide(ranked, q, idx.lastQuery);
    n++;
    if (ranked[0] && ranked[0].id === c.id) top1++;
    if (ranked.slice(0, 3).some((r) => r.id === c.id)) top3++;
    modes[dec.mode]++;
    const ok = (dec.mode === "answer" && dec.id === c.id) || (dec.mode === "ask" && dec.ids.includes(c.id));
    if (ok || (dec.mode === "answer" && sameAnswer(c.id, dec.id)) || (dec.mode === "ask" && dec.ids.some((x) => sameAnswer(c.id, x)))) okSame++;
    if (!ok) misses.push(`${c.id} ← "${q}" → ${dec.mode} ${dec.id || (dec.ids || []).join(",")} (${ranked.slice(0, 2).map((r) => r.id + ":" + r.score.toFixed(2)).join(" ")})`);
  });
}
const pct = (a, b) => (100 * a / b).toFixed(1) + "%";
console.log(`[1] 예상 질문 빼고 찾기 ${n}개: 1위 정답 ${pct(top1, n)}, 3위 안 ${pct(top3, n)}`);
console.log(`    판단: 바로 답 ${modes.answer}, 되묻기 ${modes.ask}, 조문 검색 ${modes.fallback}`);
console.log(`    바로 답했거나 되묻기 후보에 정답이 있음: ${pct(n - misses.length, n)} (같은 내용 카드·종합 카드도 인정하면 ${pct(okSame, n)})`);
if (verbose) misses.forEach((m) => console.log("    ✗ " + m));

// 2) 시험 질문
function judge(it) {
  const ranked = idx.score(it.q);
  const dec = E.decide(ranked, it.q, idx.lastQuery);
  const got = dec.mode === "answer" ? dec.id : dec.mode;
  // 정답 카드를 묶은 '여러 규정 종합' 카드로 답해도 맞음으로 센다(그 카드에 정답 카드의 근거가 들어 있다)
  // 같은 내용을 옮겨 적은 카드(same_content.json)도 맞음으로 센다
  const fam = (x) => it.expect.some((y) => y === x || (byId.has(y) && sameAnswer(y, x)));
  const ok = (dec.mode === "answer" ? fam(got) : it.expect.includes(got)) || (dec.mode === "ask" && dec.ids.some(fam) && !it.expect.includes("fallback"));
  // 엉뚱한 답을 바로 낸 경우(되묻지 않고 틀린 카드로 답함)는 따로 센다. 신뢰를 가장 크게 깎는다
  const wrongDirect = !ok && dec.mode === "answer";
  return { ok, wrongDirect, row: `${ok ? "✓" : wrongDirect ? "✗!" : "✗"} ${it.q} → ${got}${dec.mode === "ask" ? " [" + dec.ids.join(", ") + "]" : ""} (기대 ${it.expect.join("|")}, 1위 ${ranked[0] ? ranked[0].id + ":" + ranked[0].score.toFixed(2) : "-"})` };
}
const devRes = dev.map(judge), devRows = devRes.map((r) => r.row), devOk = devRes.filter((r) => r.ok).length;
console.log(`[2] 카드에 없는 시험 질문 ${dev.length}개: 맞게 처리 ${devOk}개 (${pct(devOk, dev.length)}), 엉뚱한 답을 바로 냄 ${devRes.filter((r) => r.wrongDirect).length}개`);
L.domains().forEach((dm) => { const items = devRows.filter((_, i) => dev[i].domain === dm); const okN = items.filter((r) => r.startsWith("✓")).length; console.log(`    ${dm}: ${okN}/${items.length}`); });
devRows.filter((r) => verbose || r.startsWith("✗")).forEach((r) => console.log("    " + r));
const hoRes = holdout.map(judge), hoOk = hoRes.filter((r) => r.ok).length;
console.log(`[2b] 고치기 전에 얼려 둔 새 시험 질문 ${holdout.length}개: 맞게 처리 ${hoOk}개 (${pct(hoOk, holdout.length)}), 엉뚱한 답을 바로 냄 ${hoRes.filter((r) => r.wrongDirect).length}개`);
{
  // 직원이 실제로 물었는데 답을 못 찾던 질문: 등급 글자('S는')와 '팀원 N명 … 몇 명'을 평가등급 배분으로 잇는다
  const q = "팀원이 총 12명인데 S는 몇명나오나요?", dec = E.decide(idx.score(q), q, idx.lastQuery);
  assert.ok((dec.mode === "answer" && dec.id === "r3-2-3-grade-distribution") || (dec.mode === "ask" && dec.ids[0] === "r3-2-3-grade-distribution"),
    "‘팀원 12명인데 S 몇 명’ → 평가등급 배분 카드: " + JSON.stringify(dec));
}
hoRes.filter((r) => verbose || !r.ok).forEach((r) => console.log("    " + r.row));

if (process.argv.includes("--json")) {
  // 빌드 스크립트가 화면의 '검증 정보'에 쓸 숫자
  console.log("JSON " + JSON.stringify({ loo: n, top1: pct(top1, n), top3: pct(top3, n), dev: `${devOk}/${dev.length}`, holdout: `${hoOk}/${holdout.length}` }));
}

// 3) 계산기
const C = E.calc;
const rows = (r) => Object.fromEntries(r.rows);
let r = rows(C.spouseBirth({ due: "2027-03-10", multiple: true }));
assert.match(r["휴가일수"], /^25일/);
assert.match(r["쓸 수 있는 첫날"], /^2027\.1\.19\./);
assert.match(r["쓸 수 있는 마지막 무렵"], /^2027\.7\.8\./);
r = C.spouseBirth({ due: "2026-10-01" });
assert.match(Object.fromEntries(r.rows)["쓸 수 있는 첫날"], /^2026\.9\.18\./, "출산 전 사용은 2026.9.18. 이후");
r = rows(C.maternity({ due: "2027-03-10" }));
assert.match(r["출산 전 최대"], /45일 → 예정일 기준 가장 이른 시작일 2027\.1\.24\./);
assert.match(r["유급 기간"], /최초 60일 → 2027\.3\.24\./);
r = rows(C.loss({ who: "self", date: "2026-10-01", weeks: 18 }));
assert.match(r["휴가 기간"], /30일까지/);
assert.match(r["끝나는 날"], /^2026\.10\.30\./);
assert.match(rows(C.loss({ who: "self", date: "2026-10-01", weeks: 30 }))["급여"], /최초 60일/);
assert.match(rows(C.loss({ who: "spouse", date: "2026-09-17" }))["휴가일수"], /^3일/);
assert.match(rows(C.loss({ who: "spouse", date: "2026-09-18" }))["휴가일수"], /^5일/);
r = rows(C.childAge({ birth: "2018-05-01", today: "2026-10-21" }));
assert.match(r["육아휴직 (만 8세 이하 또는 초2 이하)"], /가능 \(2027\.4\.30\./);
assert.match(r["육아기 근로시간 단축 (만 12세 이하 또는 초6 이하)"], /가능 \(2031\.4\.30\./);
r = rows(C.childAge({ birth: "2017-01-15", today: "2026-10-21" }));
assert.match(r["육아휴직 (만 8세 이하 또는 초2 이하)"], /기간 지남 \(2026\.2\.28\./, "1월생은 초2가 끝나는 2월 말이 아니라 만 9세 전날이 더 늦은지 확인");
assert.match(rows(C.familyCare({ children: 2 }))["그중 유급 (자녀 돌봄)"], /^3일/);
assert.match(rows(C.familyCare({ children: 2, disabledOrSingle: true }))["그중 유급 (자녀 돌봄)"], /^4일/);
assert.strictEqual(rows(C.allowance({ spouse: true, children: 3 }))["월 합계"], "210,000원");
r = rows(C.annualLeave({ hire: "2021-10-21", today: "2026-10-21" }));
assert.match(r["연가일수"], /^17일/);
assert.match(r["다음에 1일 늘어나는 때"], /근속 7년/);
assert.match(rows(C.annualLeave({ hire: "2000-01-01", today: "2026-10-21" }))["연가일수"], /^25일/);
assert.match(rows(C.annualLeave({ hire: "2026-03-02", today: "2026-10-21" }))["연가"], /최대 7일/);
r = rows(C.longService({ hire: "2014-05-01", today: "2026-10-21" }));
assert.match(r["5일을 써야 하는 기한"], /^2034\.4\.30\./);
assert.match(rows(C.longService({ hire: "2020-05-01", today: "2026-10-21" }))["장기재직휴가"], /2030\.5\.1\./);
r = rows(C.tripExpense({ days: 2, nights: 1, region: "seoul" }));
assert.match(r["합계(운임 제외)"], /최대 200,000원/);
assert.match(rows(C.tripExpense({ days: 1, nights: 0, region: "other", car: true }))["합계(운임 제외)"], /최대 25,000원/);
// 평가등급 인원배분(평가세칙 별표 제2호): '함께 등급을 나누는 인원' 한 칸으로 표를 찾는다. 계산기 표가 원문 표와 한 칸도 다르지 않은지 대조한다.
// 누구와 함께 나누는지(팀·실, 포함 인원)는 성과관리편람·운영기준(제19조)에서 정하므로 계산기가 셈하지 않는다
{
  const ax = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "data", "rules.json"), "utf8")).rules
    .find((x) => x.name === "평가세칙").annexes.find((x) => x.title.includes("제2호")).text;
  const table = {};
  for (const tr of ax.matchAll(/<tr>([\s\S]*?)<\/tr>/g)) {
    const cells = [...tr[1].matchAll(/<t[dh][^>]*>([\s\S]*?)<\/t[dh]>/g)].map((m) => m[1].trim()), m = /^인원수\s*(\d+)$/.exec(cells[0] || "");
    if (m && cells.length === 6) table[+m[1]] = cells.slice(1).map((x) => (x === "" ? 0 : +x));
  }
  for (const line of ax.split("\n")) {
    const c = line.split("|").map((x) => x.trim()), m = /^인원수\s*(\d+)$/.exec(c[1] || "");
    if (m) table[+m[1]] = c.slice(2, 7).map((x) => (x === "" ? 0 : +x));
  }
  const G = ["가(탁월)", "나(우수)", "다(보통)", "라(미흡)", "마(부족)"];
  for (let n = 4; n <= 100; n++) {
    const got = rows(C.gradeQuota({ size: n }));
    assert.deepStrictEqual(G.map((g) => got[g]), table[n].map((v) => v + "명"), `인원 ${n}명: 계산기가 별표 제2호 인원배분표와 같음`);
  }
  r = rows(C.gradeQuota({ size: 12 }));
  assert.ok(r["함께 등급을 나누는 인원"] === "12명이라면" && r["가(탁월)"] === "1명" && r["다(보통)"] === "6명", "12명이라면 가 1·다 6");
  assert.match(rows(C.gradeQuota({ size: 3 }))["등급"], /나\(우수\)~라\(미흡\)/, "1~3명은 나~라만");
  assert.ok(C.gradeQuota({}).error && C.gradeQuota({ size: 0 }).error && C.gradeQuota({ size: 101 }).error, "인원이 없거나 표(100명) 밖이면 알림");
  const nt = C.gradeQuota({ size: 12 }).notes.join(" ");
  assert.ok(/성과관리편람/.test(nt) && /관련 부서에 확인/.test(nt) && !("senior" in C.gradeQuota({ size: 12 })), "누구와 함께 나누는지는 편람·운영기준에서 정한다고 알리고, 팀 빼기 셈은 하지 않음");
  assert.strictEqual(E.valuesIn("팀원이 총 12명인데 S는 몇명나오나요?").size, 12, "질문의 인원을 읽음");
  assert.strictEqual(E.valuesIn("자녀 2명이면 가족수당 얼마").size, undefined, "자녀 수는 인원으로 읽지 않음");
}
console.log("[3] 계산기 시험 통과");

// 4) 내규나침반: 낱말이 어느 내규 어디에 나오는지. 글자 그대로 나오는 곳은 하나도 빠뜨리면 안 된다
const rules = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "data", "rules.json"), "utf8")).rules;
// 낱말 경계(scripts/build_bounds.py): 다른 낱말 속에서 걸린 곳(개인정보의 '인정')을 접는 데 쓴다
const bounds = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "knowledge", "word_bounds.json"), "utf8")).docs;
const compass = new E.Compass(rules, idx, cards, bounds);
// 시험 쪽 정답: 띄어쓰기·표 태그를 빼고 모든 조문·별표에서 글자 그대로 찾는다
const flatTxt = (s) => String(s || "").normalize("NFC").replace(/<[^>]+>/g, "").replace(/\s+/g, "");
function literal(words) {
  const out = new Set();
  rules.forEach((rl) => {
    rl.articles.forEach((a) => { if (words.every((wd) => flatTxt(a.text).includes(wd))) out.add(rl.name + "|" + a.no); });
    rl.annexes.forEach((x) => { if (words.every((wd) => flatTxt(x.title + " " + (x.text || "")).includes(wd))) out.add(rl.name + "|" + x.title); });
  });
  return out;
}
// 본 결과와 접힌 곳을 합치면 글자 그대로 찾은 곳과 같아야 한다(접기만 하고 지우지 않음)
const found = (res) => new Set(res.exact.concat(res.folded || []).flatMap((g) => g.hits.map((x) => g.rule + "|" + x.no)));
const sameSet = (a, b) => a.size === b.size && [...a].every((x) => b.has(x));
for (const wd of ["법인카드", "육아휴직", "겸직", "재택근무", "반일연가", "복지포인트"]) {
  assert.ok(sameSet(found(compass.find(wd)), literal([wd])), `나침반 '${wd}': 글자 그대로 나오는 조문·별표를 빠짐없이, 더하지도 않고 찾음`);
}
let cp = compass.find("법인카드");
assert.deepStrictEqual(cp.named.map((x) => x.rule), ["법인카드 관리 및 사용지침"], "이름에 낱말이 든 내규");
assert.strictEqual(cp.order[0], "법인카드 관리 및 사용지침", "목록은 많이 나오는 순(줄인 말 포함): 지침이 2곳 + 줄인 말 ‘카드’ 10곳으로 맨 앞");
assert.strictEqual(cp.exact.length, 5);
{
  // 이름에 낱말이 든 내규는 named 로 따로 알리고, 목록 순서는 나오는 곳 수로만 정한다
  const tr = compass.find("출장"), cnt = (rl) => (tr.exact.find((g) => g.rule === rl) || { n: 0 }).n + tr.aliases.filter((a) => a.rule === rl).reduce((x, a) => x + a.hits.length, 0);
  assert.deepStrictEqual(tr.named.map((x) => x.rule), ["공무국외출장세부지침"]);
  assert.deepStrictEqual(tr.order.slice(0, 2), ["여비지급세칙", "공무국외출장세부지침"], "‘출장’: 17곳인 여비지급세칙이 이름에 ‘출장’이 든 지침(11곳)보다 앞");
  assert.ok(tr.order.every((rl, i) => i === 0 || cnt(tr.order[i - 1]) >= cnt(rl)) && tr.exact.every((g, i) => tr.order[i] === g.rule), "목록 순서는 나오는 곳이 많은 순");
}
const al = cp.aliases.find((x) => x.rule === "법인카드 관리 및 사용지침");
assert.ok(al && al.alias === "카드" && al.at === "제1조" && al.hits.some((x) => x.no === "제5조"), "‘법인카드(이하 “카드”라 한다)’처럼 줄여 부르는 말도 그 내규 안에서 찾음");
assert.strictEqual(cp.similar.length, 0, "글자 그대로 나오면 비슷한 말은 찾지 않음");
cp = compass.find("직원 징계");
assert.ok(cp.mode === "all" && cp.exact.length && sameSet(found(cp), literal(["직원", "징계"])), "두 낱말이면 둘 다 나오는 곳");
cp = compass.find("반차");
assert.strictEqual(cp.exact.length, 0, "‘반차’는 원문에 없음");
assert.ok(cp.simWords.some((x) => x.word === "반일연가"), "원문에서 쓰는 말 ‘반일연가’로 바꿔 찾음");
const bok = cp.similar.find((g) => g.rule === "복무세칙");
assert.ok(bok && ["제15조", "제16조"].every((no) => bok.hits.some((x) => x.no === no)) && bok.hits.every((x) => x.why), "비슷한 말로 찾은 곳에 이유를 붙임");
assert.ok(compass.find("장").short && !compass.find("장").exact.length, "한 글자는 찾지 않음(거의 모든 조문에 나옴)");
assert.ok(cp.outside.length && cp.outside.every((o) => /반차/.test(o.title)), "‘내규에 없음’ 안내는 찾은 낱말이 이름에 든 것만(생일 휴가 같은 곁가지 빼고)");
assert.ok(!compass.find("직원").aliases.some((x) => x.alias === "행동강령책임관"), "‘직원(이하 “행동강령책임관”)’은 직원의 줄임말이 아님(줄인 말 글자가 모두 원래 말에 있어야)");
cp = compass.find("야근");
assert.ok(cp.simWords.some((x) => x.word === "시간외") && !cp.simWords.some((x) => x.word === "근로"), "바꿔 찾는 말이 너무 흔하면(‘근로’) 빼고 찾음");
assert.strictEqual(compass.find("장례").similar[0].rule, "복무세칙", "그 낱말을 묻는 답 카드의 근거 내규(경조사휴가)를 맨 앞에, 바꿔 찾은 말(‘사망’)로만 나온 곳은 뒤에");
const inCard = (id, wd) => { const cd = byId.get(id); return [cd.title].concat(cd.questions).some((x) => flatTxt(x).includes(wd)); };
for (const wd of ["휴가비", "회식", "택시"]) {
  const viaCard = compass.find(wd).similar.flatMap((g) => g.hits).filter((x) => x.card);
  assert.ok(viaCard.every((x) => inCard(x.card, wd)), `‘${wd}’: 답 카드로 찾은 곳은 그 낱말을 실제로 묻는 카드에서만`);
}
// 원문 표시용: 띄어쓰기가 달라도 낱말을 표시하고, 미리보기는 낱말 앞뒤만 잘라 낸다
assert.deepStrictEqual("법인 카드와 법인카드".match(E.wordRe(["법인카드"])), ["법인 카드", "법인카드"]);
assert.deepStrictEqual("반일연가 2회".match(E.wordRe(["연가", "반일연가"])), ["반일연가"], "긴 낱말을 먼저");
const ex = E.excerpt(rules.find((rl) => rl.name === "해외사무소운영세칙").articles.find((a) => a.no === "제27조").text, ["법인카드"], 30);
assert.ok(!/[<>|]|---/.test(E.snippet("<table><tr><td>실비<br>(상한액: 서울특별시 100,000)</td></tr></table> | 구분 | 대상 |\n| --- | --- |", "실비 상한액")), "관련 조문 미리보기에 표 태그·칸막이를 그대로 찍지 않음");
assert.ok(!/\||---/.test(JSON.stringify(E.excerpt("| 구분 | 대상 |\n| --- | --- |\n| 사망 | 배우자 |", ["사망"], 30))), "미리보기에 표 칸막이(| ---) 기호를 빼고 보여 줌");
assert.ok(ex.hit === "법인카드" && ex.pre.length <= 31 && /법인수표, $/.test(ex.pre) && ex.post.length <= 31, "미리보기: 낱말 앞뒤 30자");
// 4-2) 낱말 경계: 다른 낱말 속·반대말 머리 뒤·엉뚱하게 띄어 걸린 곳은 접고, 맞는 곳은 본 결과로. 이미 고친 문제가 되살아나지 않는지 대조한다
{
  assert.deepStrictEqual(compass.unbounded, [], "모든 조문·별표에 낱말 경계 표시가 있고 원문과 맞음(내규가 바뀌면 build_bounds.py 를 다시 돌린다)");
  const occs = (w) => { const r = compass.find(w); return r.exact.concat(r.folded).flatMap((g) => g.hits.flatMap((x) => x.occ.map((o) => ({ ...o, rule: g.rule, no: x.no })))); };
  const mainN = (xs) => xs.filter((o) => o.main).length;
  const inGroup = (w, re) => occs(w).filter((o) => re.test(o.group));
  // ① 붙여 쓴 곳의 엉뚱한 결과
  for (const [w, re, allow] of [["인정", /개인정보/, 0], ["전보", /안전보건/, 0], ["원장", /위원장|정보원장/, 0], ["회의", /(위원|이사|심의|동호|협의)회의/, 11], ["정직", /행정직/, 0], ["직급", /퇴직급/, 0], ["장비", /출장비/, 0], ["비자", /소비자/, 0], ["조사", /경조사/, 0], ["개발", /금융개발원/, 0], ["사업", /우정사업본부/, 0]]) {
    const xs = inGroup(w, re);
    assert.ok(xs.length && mainN(xs) <= allow, `‘${w}’ ← ${re.source}: ${xs.length}곳 중 본 결과 ${mainN(xs)}(허용 ${allow})`);
  }
  for (const [w, re] of [["이익", /^불이익/], ["공개", /^(비|미)공개/], ["정규직", /^비정규직/], ["가능", /^불가능/], ["지급", /^부지급/]]) {
    const xs = inGroup(w, re);
    assert.ok(xs.length && mainN(xs) === 0 && xs.every((o) => o.why === "fold-neg"), `반대말 머리 ‘${w}’ ← ${re.source}: 모두 접힘`);
  }
  // ② 처음 문제: 엉뚱하게 띄어 걸린 곳("위하여 비상임"의 '여비')
  for (const w of ["여비", "의장", "의결", "시작"]) {
    const xs = occs(w).filter((o) => o.spaced);
    assert.ok(xs.length && mainN(xs) === 0, `‘${w}’: 띄어 걸린 ${xs.length}곳은 모두 접힘`);
  }
  const yb = compass.find("여비");
  assert.ok(yb.exact.reduce((n, g) => n + g.hits.length, 0) < literal(["여비"]).size, "‘여비’: 엉뚱하게 띄어 걸린 조문은 본 결과에서 빠짐");
  // ③ 띄어 걸렸지만 뜻이 다른 곳
  for (const [w, re] of [["회의운영", /(위원|이사|심의|협의)회의 운영/], ["회의소집", /(위원|이사)회의 소집/], ["정규직채용", /비정규직 채용/], ["지급대상", /부지급 대상/], ["중징계", /중 징계/]]) {
    const xs = inGroup(w, re);
    assert.ok(xs.length && mainN(xs) === 0, `‘${w}’ ← ${re.source}: ${xs.length}곳 모두 접힘`);
  }
  // ④ 맞는 곳은 본 결과(형태소 경계, 낱말 쪼개기, 확인 목록, 다시 보기)
  for (const [w, re] of [["여비", /출장여비|국내여비|국외여비/], ["수당", /가족수당|초과근무수당|연차수당|제수당/], ["휴가", /특별휴가|출산전후휴가/], ["근무", /재택근무|초과근무|원격근무/], ["출장", /공무국외출장|출장비/], ["시간", /근무시간|근로시간|단시간/], ["정보", /개인정보/], ["연가", /반일연가|저축연가/], ["이사", /비상임이사|사외이사|이사회/], ["휴직", /육아휴직/], ["직원", /임직원/], ["징계", /중징계|경징계/], ["근로", /근로자/], ["퇴직", /명예퇴직/], ["가족", /부양가족/], ["사고", /안전사고|보험사고/], ["휴일", /공휴일/], ["개정", /제·개정/], ["윤리", /공직자윤리법/], ["분류표", /내규분류표/]]) {
    const xs = inGroup(w, re);
    assert.ok(xs.length && mainN(xs) / xs.length >= 0.9, `‘${w}’ ← ${re.source}: ${xs.length}곳 중 본 결과 ${mainN(xs)}`);
  }
  for (const [w, re] of [["평가결과", /성과평가 결과/], ["고득점순", /고득점 순/], ["수사중", /수사 중/], ["퇴직전", /퇴직 전/], ["시간외", /^시 간 외$/], ["시간외근무", /시 간 외 근무/], ["전직원", /^전 직원/], ["타기관", /^타 기관/]]) {
    const xs = inGroup(w, re);
    assert.ok(xs.length && mainN(xs) === xs.length, `띄어 쓴 맞는 곳 ‘${w}’ ← ${re.source}: ${xs.length}곳 모두 본 결과`);
  }
  // ⑤ 접기만 하고 지우지 않음: 본 결과 + 접힌 곳 = 글자 그대로
  for (const wd of ["인정", "회의", "여비", "직원", "이사", "공개"]) {
    assert.ok(sameSet(found(compass.find(wd)), literal([wd])), `‘${wd}’: 본 결과와 접힌 곳을 합치면 글자 그대로 찾은 곳과 같음`);
  }
  // ⑥ 걸린 말별 묶음: 같은 글자 다른 뜻이 따로 묶인다
  const isa = compass.find("이사").groups;
  assert.ok(isa.some((g) => /이사화물/.test(g.key)) && isa.some((g) => /^이사회$/.test(g.key)), "‘이사’: 이사회와 이사화물(이사 가기)이 다른 묶음");
  assert.ok(!compass.find("인정").named.length && compass.find("출장").named.length === 1, "‘이름에 들어간 내규’도 같은 기준: ‘인정’ → 개인정보보호세칙은 아님, ‘출장’ → 공무국외출장세부지침");
  const ij = compass.find("인정").groups;
  assert.ok(ij.some((g) => /개인정보/.test(g.key) && !g.main) && ij.some((g) => g.main), "‘인정’: 개인정보 묶음은 접힌 묶음, 실제 ‘인정’은 본 묶음");
  assert.ok(isa.every((g, i) => i === 0 || isa[i - 1].main > g.main || (isa[i - 1].main === g.main && isa[i - 1].n >= g.n)), "묶음 순서: 본 묶음 먼저, 많은 순");
  // ⑦ 미리보기는 접힌 곳 말고 본 결과를 보여 준다
  const ins = compass.find("인정"), d0 = ins.exact.flatMap((g) => g.hits.map((x) => ({ g, x }))).find(({ x }) => x.occ.some((o) => !o.main) && x.occ.some((o) => o.main));
  assert.ok(d0, "본 결과와 접힌 곳이 함께 있는 조문");
  const ok = new Set(d0.x.occ.filter((o) => o.main).map((o) => o.at));
  const txt = (rules.find((rl) => rl.name === d0.g.rule).articles.find((a) => a.no === d0.x.no) || {}).text || "";
  assert.ok(E.excerpt(txt, ["인정"], 30, (at) => ok.has(at)).post !== undefined && !/개$/.test(E.excerpt(txt, ["인정"], 30, (at) => ok.has(at)).pre), "미리보기: ‘개인정보’의 ‘인정’을 건너뛰고 본 결과를 보여 줌");
}
console.log("[4] 내규나침반 시험 통과");
