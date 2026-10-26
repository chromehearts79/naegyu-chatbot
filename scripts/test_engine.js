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
console.log("[3] 계산기 시험 통과");
