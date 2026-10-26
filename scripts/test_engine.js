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

// 4) 내규나침반: 낱말이 어느 내규 어디에 나오는지. 글자 그대로 나오는 곳은 하나도 빠뜨리면 안 된다
const rules = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "data", "rules.json"), "utf8")).rules;
const compass = new E.Compass(rules, idx, cards);
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
const found = (res) => new Set(res.exact.flatMap((g) => g.hits.map((x) => g.rule + "|" + x.no)));
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
console.log("[4] 내규나침반 시험 통과");
