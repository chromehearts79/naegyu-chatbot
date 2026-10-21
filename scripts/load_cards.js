// 분야 폴더(knowledge/<분야>/)의 카드와 시험 질문을 모두 읽는다. check_knowledge.py 의 load_domains 와 같은 규칙.
const fs = require("fs");
const path = require("path");

const KNOWLEDGE = path.join(__dirname, "..", "knowledge");

function domains() {
  return fs.readdirSync(KNOWLEDGE).filter((d) => fs.existsSync(path.join(KNOWLEDGE, d, "_topics.json"))).sort();
}

function cards() {
  return domains().flatMap((dm) => fs.readdirSync(path.join(KNOWLEDGE, dm)).sort()
    .filter((f) => f.endsWith(".json") && !f.startsWith("_"))
    .flatMap((f) => {
      // 여럿이 동시에 쓰는 중이라 읽히지 않는 파일은 건너뛴다
      try { return JSON.parse(fs.readFileSync(path.join(KNOWLEDGE, dm, f), "utf8")).map((c) => ({ ...c, domain: dm })); } catch (e) { return []; }
    }));
}

function devset() {
  // 분야마다 _devset.json 하나 또는 규정별 _devset_<규정>.json 여러 개
  return domains().flatMap((dm) => fs.readdirSync(path.join(KNOWLEDGE, dm)).sort()
    .filter((f) => /^_devset.*\.json$/.test(f))
    .flatMap((f) => JSON.parse(fs.readFileSync(path.join(KNOWLEDGE, dm, f), "utf8")).items.map((it) => ({ ...it, domain: dm, file: f }))));
}

module.exports = { domains, cards, devset };
