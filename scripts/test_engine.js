// 검색 엔진과 계산기 시험.
//  1) 예상 질문 하나씩 빼고 찾기(leave-one-out): 처음 보는 표현을 얼마나 맞히는지
//  2) 카드에 없는 시험 질문(_devset.json): 답·되묻기·조문 검색 판단이 맞는지
//  3) 계산기 결과가 손으로 계산한 값과 같은지
const fs = require("fs");
const path = require("path");
const assert = require("assert");
const E = require("../web/engine.js");

const dir = path.join(__dirname, "..", "knowledge", "birth_childcare");
const cards = fs.readdirSync(dir).filter((f) => f.endsWith(".json") && !f.startsWith("_"))
  .flatMap((f) => JSON.parse(fs.readFileSync(path.join(dir, f), "utf8")));
const dev = JSON.parse(fs.readFileSync(path.join(dir, "_devset.json"), "utf8")).items;
const idx = new E.CardIndex(cards);
const verbose = process.argv.includes("-v");

// 1) leave-one-out
let n = 0, top1 = 0, top3 = 0;
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
    if (!ok) misses.push(`${c.id} ← "${q}" → ${dec.mode} ${dec.id || (dec.ids || []).join(",")} (${ranked.slice(0, 2).map((r) => r.id + ":" + r.score.toFixed(2)).join(" ")})`);
  });
}
const pct = (a, b) => (100 * a / b).toFixed(1) + "%";
console.log(`[1] 예상 질문 빼고 찾기 ${n}개: 1위 정답 ${pct(top1, n)}, 3위 안 ${pct(top3, n)}`);
console.log(`    판단: 바로 답 ${modes.answer}, 되묻기 ${modes.ask}, 조문 검색 ${modes.fallback}`);
console.log(`    바로 답했거나 되묻기 후보에 정답이 있음: ${pct(n - misses.length, n)}`);
if (verbose) misses.forEach((m) => console.log("    ✗ " + m));

// 2) 시험 질문
let devOk = 0;
const devRows = [];
for (const it of dev) {
  const ranked = idx.score(it.q);
  const dec = E.decide(ranked, it.q, idx.lastQuery);
  const got = dec.mode === "answer" ? dec.id : dec.mode;
  const ok = it.expect.includes(got) || (dec.mode === "ask" && it.expect.some((e) => dec.ids.includes(e)) && !it.expect.includes("fallback"));
  if (ok) devOk++;
  devRows.push(`${ok ? "✓" : "✗"} ${it.q} → ${got}${dec.mode === "ask" ? " [" + dec.ids.join(", ") + "]" : ""} (기대 ${it.expect.join("|")}, 1위 ${ranked[0] ? ranked[0].id + ":" + ranked[0].score.toFixed(2) : "-"})`);
}
console.log(`[2] 카드에 없는 시험 질문 ${dev.length}개: 맞게 처리 ${devOk}개 (${pct(devOk, dev.length)})`);
devRows.filter((r) => verbose || r.startsWith("✗")).forEach((r) => console.log("    " + r));

if (process.argv.includes("--json")) {
  // 빌드 스크립트가 화면의 '검증 정보'에 쓸 숫자
  console.log("JSON " + JSON.stringify({ loo: n, top1: pct(top1, n), top3: pct(top3, n), dev: `${devOk}/${dev.length}` }));
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
console.log("[3] 계산기 시험 통과");
