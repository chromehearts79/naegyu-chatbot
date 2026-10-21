// 되묻기·답변 기준값(T.HI, T.GAP, T.NEAR) 고르기. 예상 질문 빼고 찾기 + 시험 질문을 함께 본다.
// 점수: 바로 맞게 답함 +1, 되묻기 후보에 정답 +0.6, 틀린 답을 바로 줌 -1.5 (틀린 답이 가장 나쁘다)
const fs = require("fs"), path = require("path"), E = require("../web/engine.js");
const dir = path.join(__dirname, "..", "knowledge", "birth_childcare");
const cards = fs.readdirSync(dir).filter((f) => f.endsWith(".json") && !f.startsWith("_")).flatMap((f) => JSON.parse(fs.readFileSync(path.join(dir, f))));
const dev = JSON.parse(fs.readFileSync(path.join(dir, "_devset.json"))).items;
const idx = new E.CardIndex(cards);
const cases = [];
for (const c of cards) c.questions.forEach((q, qi) => cases.push({ q, expect: [c.id], ranked: idx.score(q, (d) => d.card === c.id && d.kind === "q" && d.qi === qi), qq: idx.lastQuery }));
for (const it of dev) cases.push({ q: it.q, expect: it.expect, ranked: idx.score(it.q), qq: idx.lastQuery });
const T = E.thresholds, keep = { ...T };
let best = null;
for (const HI of [0.4, 0.45, 0.5, 0.55, 0.6]) for (const GAP of [0.04, 0.06, 0.08, 0.1, 0.12]) for (const NEAR of [0.8, 0.85, 0.9]) {
  Object.assign(T, { HI, GAP, NEAR });
  let s = 0, right = 0, wrong = 0, ask = 0;
  for (const k of cases) {
    const d = E.decide(k.ranked, k.q, k.qq);
    if (d.mode === "answer") { if (k.expect.includes(d.id)) { s += 1; right++; } else if (!k.expect.includes("ask")) { s -= 1.5; wrong++; } }
    else if (d.mode === "ask") { ask++; if (k.expect.includes("ask") || k.expect.some((e) => d.ids.includes(e))) s += 0.6; }
    else if (k.expect.includes("fallback")) s += 1;
  }
  if (!best || s > best.s) best = { s, HI, GAP, NEAR, right, wrong, ask };
}
Object.assign(T, keep);
console.log("가장 좋은 기준값:", best, "(질문", cases.length, "개)");
