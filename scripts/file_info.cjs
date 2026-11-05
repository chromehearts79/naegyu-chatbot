// .hwp 파일의 작성 정보(\x05HwpSummaryInformation)를 읽어 JSON 으로 낸다.
// 사람이 읽는 참고용이다. 속성 표를 다 해석하지 않고, 읽을 수 있는 글자만 뽑는다.
//   node scripts/file_info.cjs 파일1.hwp 파일2.hwp ...
const fs = require("fs");
let CFB;
try { CFB = require("cfb"); } catch (e) { console.error("cfb 가 없습니다. 먼저 실행: npm ci"); process.exit(2); }

function readable(buf) {
  const text = buf.toString("utf16le");
  const out = [];
  for (const part of text.split("\u0000")) {
    const s = part.replace(/[\u0000-\u001f]/g, "").trim();
    if (s.length >= 2) out.push(s);
  }
  return out;
}

function info(path) {
  try {
    const cfb = CFB.read(fs.readFileSync(path), { type: "buffer" });
    const entry = CFB.find(cfb, "\u0005HwpSummaryInformation");
    if (!entry) return { path, strings: [], note: "작성 정보 없음" };
    return { path, strings: readable(Buffer.from(entry.content)) };
  } catch (e) {
    return { path, error: String(e.message || e) };
  }
}

console.log(JSON.stringify(process.argv.slice(2).map(info)));
