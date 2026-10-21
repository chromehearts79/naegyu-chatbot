"""data/md 의 변환본을 조문 단위로 나눠 data/rules.json 으로 저장한다.

규정 하나는 본문 조문, 부칙, 별표, 별지 서식으로 나뉜다. 조문은 다시 항(①②…)으로 나눈다.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MD = ROOT / "data" / "md"
OUT = ROOT / "data" / "rules.json"

KIND = {"Ⅰ": "정관", "Ⅱ": "규정", "Ⅲ": "세칙", "Ⅳ": "지침"}
CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"

RE_BUCHIK = re.compile(r"^\s*부\s*칙\s*$")
RE_ANNEX = re.compile(r"^\s*(?:#+\s*)?\[(별표[^\]]*)\]?(.*)$")
RE_FORM = re.compile(r"^\s*(?:#+\s*)?\[(별지[^\]]*)\]?(.*)$")
RE_CHAPTER = re.compile(r"^\s*(?:#+\s*)?(제\d+장\s*.*)$")
RE_SECTION = re.compile(r"^\s*(?:#+\s*)?(제\d+절\s*.*)$")
RE_ARTICLE = re.compile(r"^\s*(?:#+\s*)?(제(\d+)조(?:의(\d+))?)\s*\(([^)]*)\)\s*(.*)$")
RE_EFFECTIVE = re.compile(r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일\s*(?:부터|에)\s*시행")


def normalize(line):
    """변환본의 굵은 글씨·밑줄 표시와 이스케이프를 걷어낸다. 조문 머리가 **제1조(목적)** 처럼 오기도 한다."""
    line = line.replace("**", "").replace("<u>", "").replace("</u>", "")
    return re.sub(r"\\([~*_\[\]()#.-])", r"\1", line)


def clean(lines):
    text = "\n".join(re.sub(r"^#+\s*", "", l) for l in lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def split_paras(text):
    """조문 본문을 항 단위로 나눈다. 항 번호가 없으면 통째로 1개."""
    parts = re.split(r"(?m)(?=^[①-⑳])|(?<=\) )(?=①)", text)
    paras = []
    for p in parts:
        p = p.strip()
        if p and p[0] in CIRCLED:
            paras.append({"no": CIRCLED.index(p[0]) + 1, "text": p})
    return paras


def parse(path):
    stem = path.stem
    m = re.match(r"^([ⅠⅡⅢⅣ][-0-9]*)\.?\s*(.+)$", stem)
    code, name = (m.group(1), m.group(2)) if m else ("", stem)
    rule = {"code": code, "name": name.strip(), "kind": KIND.get(code[:1], ""),
            "articles": [], "annexes": [], "forms": [], "buchik": []}
    state, chapter, section, buf, cur = "head", "", "", [], None

    def flush():
        nonlocal buf, cur
        if cur is not None:
            cur["text"] = clean(buf)
            if state == "article":
                cur["paras"] = split_paras(cur["text"])
        buf, cur = [], None

    for line in map(normalize, path.read_text().splitlines()):
        if RE_BUCHIK.match(line):
            flush(); state = "buchik"
            cur = {}; rule["buchik"].append(cur); buf = [line]; continue
        m = RE_ANNEX.match(line)
        if m:
            flush(); state = "annex"
            cur = {"title": (m.group(1) + " " + m.group(2).strip()).strip()}
            rule["annexes"].append(cur); buf = [line]; continue
        m = RE_FORM.match(line)
        if m:
            flush(); state = "form"
            cur = {"title": (m.group(1) + " " + m.group(2).strip()).strip()}
            rule["forms"].append(cur); buf = [line]; continue
        if state in ("head", "article"):
            m = RE_CHAPTER.match(line)
            if m and len(line) < 60:
                flush(); state = "article" if rule["articles"] else "head"
                chapter, section = m.group(1).strip(), ""; continue
            m = RE_SECTION.match(line)
            if m and len(line) < 60:
                flush(); section = m.group(1).strip(); continue
            m = RE_ARTICLE.match(line)
            if m:
                flush(); state = "article"
                no = m.group(1)
                cur = {"no": no, "title": m.group(4).strip(),
                       "chapter": " > ".join(x for x in (chapter, section) if x)}
                rule["articles"].append(cur); buf = [line]; continue
        if cur is not None:
            buf.append(line)
    flush()

    for b in rule["buchik"]:
        ds = [f"{y}.{int(mo):02d}.{int(d):02d}" for y, mo, d in RE_EFFECTIVE.findall(b.get("text", ""))]
        b["effective"] = max(ds) if ds else ""
    rule["effective"] = max((b["effective"] for b in rule["buchik"]), default="")
    # 별지 서식은 제목만 남긴다. 본문은 빈 칸이 대부분이라 검색을 흐린다.
    rule["forms"] = [{"title": f["title"]} for f in rule["forms"]]
    return rule


def main():
    rules = []
    for path in sorted(MD.glob("*.md")):
        if path.name.startswith("[") or "위임전결기준" in path.name:
            continue
        rules.append(parse(path))
    # 위임전결기준 엑셀은 위임전결세칙의 별표로 붙인다.
    xl = next(MD.glob("*위임전결기준*.md"), None)
    if xl:
        target = next(r for r in rules if r["name"] == "위임전결세칙")
        target["annexes"] = [{"title": "별표 위임전결기준", "text": xl.read_text().strip()}]
    OUT.write_text(json.dumps({"rules": rules}, ensure_ascii=False, indent=1))
    arts = sum(len(r["articles"]) for r in rules)
    paras = sum(len(a["paras"]) for r in rules for a in r["articles"])
    annexes = sum(len(r["annexes"]) for r in rules)
    print(f"규정 {len(rules)}개, 조문 {arts}개, 항 {paras}개, 별표 {annexes}개 → {OUT}")


if __name__ == "__main__":
    sys.exit(main())
