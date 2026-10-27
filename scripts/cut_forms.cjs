// 서식 대장(knowledge/forms.json)에서 받기를 켠 별지를 내규 원본 한글 파일(.hwp)에서 한 장씩 떼어 data/forms 에 둔다.
// 원본의 글자·표·쪽 설정 레코드를 그대로 옮기므로 원본과 같은 모양이다(한글에서 열어 채우고 인쇄할 수 있다).
// 사용: node scripts/cut_forms.cjs   (원본 폴더는 NAEGYU_SRC 로 바꿀 수 있다)
// 필요: npm i --no-save jsdom@24.1.3 cfb@1.2.2
const fs = require("fs"), path = require("path"), zlib = require("zlib"), crypto = require("crypto");
let CFB;
try { CFB = require("cfb"); } catch (e) { console.error("cfb 가 없습니다. 먼저 실행: npm i --no-save jsdom@24.1.3 cfb@1.2.2"); process.exit(2); }
const ROOT = path.resolve(__dirname, "..");
const SRC = process.env.NAEGYU_SRC || path.join(require("os").homedir(), "Library/Mobile Documents/com~apple~CloudDocs/내규챗봇");
const OUT = path.join(ROOT, "data", "forms");

const T = { HEAD: 66, TEXT: 67, CS: 68, LS: 69, RANGE: 70, CTRL: 71 };
// 한 글자짜리 조판부호(나머지 조판부호는 8글자를 차지한다)
const one = (c) => c === 0 || c === 10 || c === 13 || (c >= 24 && c <= 31);
const norm = (s) => s.replace(/\s+/g, "");

function records(buf) {
  const r = []; let o = 0;
  while (o < buf.length) {
    const h = buf.readUInt32LE(o); let size = h >>> 20, hl = 4;
    if (size === 0xfff) { size = buf.readUInt32LE(o + 4); hl = 8; }
    r.push({ tag: h & 0x3ff, level: (h >>> 10) & 0x3ff, data: Buffer.from(buf.subarray(o + hl, o + hl + size)) });
    o += hl + size;
  }
  return r;
}
function pack(recs) {
  return Buffer.concat(recs.map((x) => {
    const big = x.data.length >= 0xfff, h = Buffer.alloc(big ? 8 : 4);
    h.writeUInt32LE((x.tag | (x.level << 10) | ((big ? 0xfff : x.data.length) << 20)) >>> 0, 0);
    if (big) h.writeUInt32LE(x.data.length, 4);
    return Buffer.concat([h, x.data]);
  }));
}
// 맨 위 문단(level 0 문단 머리)마다 묶고, 문단 안은 level 1 자식마다 하위 레코드째 묶는다
function paras(recs) { const ps = []; for (const x of recs) { if (x.tag === T.HEAD && x.level === 0) ps.push([x]); else ps[ps.length - 1].push(x); } return ps; }
function kids(p) { const k = []; for (const x of p.slice(1)) { if (x.level === 1) k.push([x]); else k[k.length - 1].push(x); } return k; }
function decode(data) {
  let s = "";
  for (let i = 0; i < data.length; i += 2) { const c = data.readUInt16LE(i); if (c < 32) { if (!one(c)) i += 14; if (c === 13) s += "\n"; continue; } s += String.fromCharCode(c); }
  return s;
}
// 문단 안의 모든 글(표 칸·글상자 속 포함)을 줄마다
const texts = (p) => p.filter((x) => x.tag === T.TEXT).map((x) => norm(decode(x.data)));
// '[별지 제8호 서식]'·'[별지 제1호]' 표시 줄인지(번호를 주면 그 번호만). 별지 표시가 표 칸 안에 있어도 찾는다
const isLabel = (s, no) => (no ? new RegExp("^\\[별지제" + no.replace(/-/g, "\\-") + "호(?:서식)?\\]") : /^\[별지/).test(s);
const ctrlId = (c) => { const v = c.data.readUInt32LE(0); return String.fromCharCode(v >>> 24, (v >>> 16) & 255, (v >>> 8) & 255, v & 255); };

// 원본에서 '[별지 제N호 서식]'부터 다음 별지 앞까지만 남긴 한글 파일을 만든다(no: 별지 번호 '8', '5-1')
function cut(buf, no) {
  const cfb = CFB.read(buf, { type: "buffer" });
  const get = (p) => CFB.find(cfb, "/" + p);
  const flags = Buffer.from(get("FileHeader").content).readUInt32LE(36);
  if (flags & 6) throw new Error("암호를 건 문서나 배포용 문서는 떼어 낼 수 없음");
  const packed = !!(flags & 1);
  const unz = (b) => (packed ? zlib.inflateRawSync(Buffer.from(b)) : Buffer.from(b));
  const zip = (b) => (packed ? zlib.deflateRawSync(b) : b);
  // 별지는 가로 쪽 등 뒤 구역(Section1 …)에 따로 있기도 하고, 한 양식이 여러 구역에 걸치기도 한다(앞쪽은 세로, 뒷쪽은 다음 구역)
  const secs = cfb.FullPaths.filter((p) => /BodyText\/Section\d+$/.test(p)).map((p) => "/BodyText/" + p.split("/").pop())
    .sort((a, b) => +a.match(/\d+$/) - +b.match(/\d+$/));
  const all = secs.map((nm) => paras(records(unz(CFB.find(cfb, nm).content))));
  let si = 0, from = -1;
  for (; si < all.length; si++) { from = all[si].findIndex((p) => texts(p).some((s) => isLabel(s, no))); if (from >= 0) break; }
  if (from < 0) throw new Error("원본에서 '[별지 제" + no + "호]' 표시를 못 찾음");
  // 앞 양식의 뒷장과 이 양식의 첫머리(또는 이 양식의 끝과 다음 양식)가 한 덩어리(표·글상자) 안에 들어 있으면 깨끗하게 나눌 수 없다:
  // 별지 표시가 그 덩어리의 첫 글이어야 뗀다(아니면 남의 양식이 섞이거나 이 양식이 잘린다)
  const lead = (p) => texts(p).find(Boolean) || "";
  const nextAt = (ps, i0) => ps.findIndex((p, i) => i >= i0 && texts(p).some((s) => isLabel(s)));
  if (!isLabel(lead(all[si][from]), no)) throw new Error("앞 양식과 한 덩어리 안에 있어 깨끗하게 뗄 수 없음");
  // 남길 곳: [구역, 처음, 끝) 목록. 다음 별지 표시가 나올 때까지 뒤 구역으로 이어 간다
  const parts = [];
  for (let sj = si, a = from; sj < all.length; sj++, a = 0) {
    const b = nextAt(all[sj], sj === si ? from + 1 : 0);
    if (b >= 0 && !isLabel(lead(all[sj][b]))) throw new Error("다음 양식과 한 덩어리 안에 있어 깨끗하게 뗄 수 없음");
    if (b !== a) parts.push([sj, a, b < 0 ? all[sj].length : b]);
    if (b >= 0) break;
  }
  const out = parts.map(([sj, a, b]) => {
    const ps = all[sj], keep = ps.slice(a, b).map((p) => p.map((x) => ({ ...x, data: Buffer.from(x.data) })));
    // 구역 한가운데서 시작하면, 구역 첫 문단의 구역 정의(secd)·단 정의(cold) 조판부호를 첫 문단 앞에 옮겨 붙인다(쪽 크기·여백이 여기 들어 있다).
    // 구역 첫 문단부터면 이미 들어 있다
    if (a > 0) {
      const first = ps[0], ftext = first.find((x) => x.tag === T.TEXT).data, ext = [];
      for (let i = 0; i < ftext.length; i += 2) { const c = ftext.readUInt16LE(i); if (c < 32 && !one(c)) { ext.push(ftext.subarray(i, i + 16)); i += 14; } }
      const sec = [], secText = [];
      kids(first).filter((k) => k[0].tag === T.CTRL).forEach((k, j) => { const id = ctrlId(k[0]); if (id === "secd" || id === "cold") { sec.push(...k); secText.push(ext[j]); } });
      if (!sec.length) throw new Error("구역 정의를 못 찾음");
      const add = secText.length * 8, L = keep[0], lk = kids(L), lh = L[0].data;
      lh.writeUInt32LE(((lh.readUInt32LE(0) & 0x7fffffff) + add) >>> 0, 0);  // 글자 수
      lh.writeUInt32LE((lh.readUInt32LE(4) | (1 << 2)) >>> 0, 4);             // 구역·단 정의 조판부호가 있다는 표시
      lh.writeUInt8(0, 11);                                                    // 쪽 나누기를 지워 첫 쪽에서 시작
      lk.find((k) => k[0].tag === T.TEXT)[0].data = Buffer.concat([...secText, lk.find((k) => k[0].tag === T.TEXT)[0].data]);
      for (const [r] of lk) {   // 글자 위치가 조판부호만큼 밀린다(맨 앞 0 은 그대로)
        if (r.tag === T.CS) for (let o = 8; o < r.data.length; o += 8) r.data.writeUInt32LE(r.data.readUInt32LE(o) + add, o);
        if (r.tag === T.LS) for (let o = 36; o < r.data.length; o += 36) r.data.writeUInt32LE(r.data.readUInt32LE(o) + add, o);
        if (r.tag === T.RANGE) for (let o = 0; o < r.data.length; o += 12) { r.data.writeUInt32LE(r.data.readUInt32LE(o) + add, o); r.data.writeUInt32LE(r.data.readUInt32LE(o + 4) + add, o + 4); }
      }
      // 문단 머리 → 글 → 글자 모양 → 줄 → 조판부호 차례를 지킨다: 구역 정의는 원래 조판부호 앞에
      keep[0] = [L[0], ...lk.filter((k) => k[0].tag !== T.CTRL).flat(), ...sec, ...lk.filter((k) => k[0].tag === T.CTRL).flat()];
    }
    // 구역의 마지막 문단 표시
    keep.forEach((p, i) => { const d = p[0].data, n = d.readUInt32LE(0) & 0x7fffffff; d.writeUInt32LE((i === keep.length - 1 ? n | 0x80000000 : n) >>> 0, 0); });
    return keep;
  });

  // 문서 정보: 구역 수, 커서는 맨 앞
  const info = records(unz(get("DocInfo").content)), prop = info.find((x) => x.tag === 16);
  if (prop && prop.data.length >= 26) { prop.data.writeUInt16LE(out.length, 0); prop.data.writeUInt32LE(0, 14); prop.data.writeUInt32LE(0, 18); prop.data.writeUInt32LE(0, 22); }
  const put = (p, b) => { CFB.utils.cfb_del(cfb, p); CFB.utils.cfb_add(cfb, p, b); };
  secs.forEach((nm) => CFB.utils.cfb_del(cfb, nm));
  out.forEach((keep, i) => put("/BodyText/Section" + i, zip(pack(keep.flat()))));
  put("/DocInfo", zip(pack(info)));
  // 미리보기 글은 별지 글로, 원본 첫 쪽 미리보기 그림과 문서 요약(제목 '정관' 등)은 뺀다
  const allText = out.flat(2).filter((x) => x.tag === T.TEXT).map((x) => decode(x.data)).join("\n").replace(/\n+/g, "\r\n");
  put("/PrvText", Buffer.from(allText.slice(0, 1023), "utf16le"));
  ["/PrvImage", "/\u0005HwpSummaryInformation"].forEach((p) => { try { CFB.utils.cfb_del(cfb, p); } catch (e) { /* 없으면 그만 */ } });
  CFB.utils.cfb_gc(cfb);
  return Buffer.from(CFB.write(cfb, { type: "buffer", fileType: "cfb" }));
}

function main() {
  const led = JSON.parse(fs.readFileSync(path.join(ROOT, "knowledge", "forms.json"), "utf8"));
  const rules = new Map(JSON.parse(fs.readFileSync(path.join(ROOT, "data", "rules.json"), "utf8")).rules.map((r) => [r.name, r]));
  fs.mkdirSync(OUT, { recursive: true });
  const index = {};
  let bad = 0;
  for (const e of led.rules) {
    const r = rules.get(e.rule);
    for (const f of e.forms.filter((x) => x.download)) {
      const key = e.rule + "/" + f.no, src = path.join(SRC, e.code + ". " + e.rule + ".hwp");
      try {
        if (!r) throw new Error("data/rules.json 에 내규가 없음");
        if (!fs.existsSync(src)) throw new Error("원본 .hwp 가 없음(" + src + "). .hwpx 원본은 아직 못 뗌");
        const out = cut(fs.readFileSync(src), f.no), file = e.rule + "_별지" + f.no + ".hwp";
        fs.writeFileSync(path.join(OUT, file), out);
        index[key] = { file, effective: r.effective, bytes: out.length, sha: crypto.createHash("sha256").update(out).digest("hex").slice(0, 16) };
        console.log("✓ " + key + " " + f.title + " → data/forms/" + file + " (" + out.length + "바이트, 원문 시행 " + r.effective + ")");
      } catch (err) { bad++; console.log("✗ " + key + " " + f.title + ": " + err.message); }
    }
  }
  fs.writeFileSync(path.join(OUT, "index.json"), JSON.stringify({ cut: new Date().toISOString().slice(0, 10), forms: index }, null, 1) + "\n");
  if (bad) process.exitCode = 1;
}

if (require.main === module) main();
module.exports = { cut };
