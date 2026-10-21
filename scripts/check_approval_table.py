"""위임전결기준 표 대조: 카드가 적은 전결권자가 표의 ○ 칸과 맞는지 프로그램으로 확인한다.

검증 모델은 긴 표의 일부만 받아 칸 제목(팀장·실장·처장)을 보지 못하므로, 표를 칸 단위로 펼쳐
행마다 ○ 가 있는 칸의 제목을 구한 뒤 카드 값과 비교한다.
사용: python3 scripts/check_approval_table.py  → reports/approval_table_check.md
"""
import json, re, glob
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARK = re.compile(r"[○◯●◎O]")
INFO_COLS = {"구분", "일련번호", "업무내용", "단위사무", "사무분장내용", "팀명", "비고"}


class Tables(HTMLParser):
    def __init__(self):
        super().__init__(); self.tables = []; self.row = None; self.cell = None
    def handle_starttag(self, tag, a):
        a = dict(a)
        if tag == "table": self.tables.append([])
        elif tag == "tr": self.row = []
        elif tag in ("td", "th"): self.cell = {"t": "", "rs": int(a.get("rowspan", 1)), "cs": int(a.get("colspan", 1))}
        elif tag == "br" and self.cell is not None: self.cell["t"] += " "
    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None: self.row.append(self.cell); self.cell = None
        elif tag == "tr" and self.row is not None and self.tables: self.tables[-1].append(self.row); self.row = None
    def handle_data(self, d):
        if self.cell is not None: self.cell["t"] += d


def grid(rows):
    """rowspan·colspan 을 펼쳐 칸 격자로 만든다."""
    out, carry = [], {}
    for r in rows:
        line, ci = [], 0
        cells = list(r)
        while cells or carry.get(ci):
            if carry.get(ci):
                t, left = carry[ci]; line.append(t)
                carry[ci] = (t, left - 1) if left > 1 else None
                ci += 1; continue
            if not cells: break
            c = cells.pop(0); t = re.sub(r"\s+", " ", c["t"]).strip()
            for k in range(c["cs"]):
                line.append(t)
                if c["rs"] > 1: carry[ci] = (t, c["rs"] - 1)
                ci += 1
        out.append(line)
    return out


def norm(s):
    return re.sub(r"[\s·ㆍ‧∙,.()]", "", s or "")


def parse():
    rules = {r["name"]: r for r in json.loads((ROOT / "data" / "rules.json").read_text())["rules"]}
    p = Tables()
    for a in rules["위임전결세칙"]["annexes"]:
        p.feed(a.get("text") or "")
    rows_out = []
    for t in p.tables:
        g = grid(t)
        h = next((i for i, l in enumerate(g) if any("전결권자" in x.replace(" ", "") for x in l)), None)
        if h is None or h + 1 >= len(g): continue
        names = g[h + 1]
        top = g[h]
        cols = {}
        for j, x in enumerate(top):
            x = x.replace(" ", "")
            if "전결권자" in x and j < len(names): cols[j] = names[j].replace(" ", "")
            elif x and x not in INFO_COLS: cols[j] = x  # 두 줄 제목(비상임감사, 원장 등)
        for l in g[h + 2:]:
            auth = [cols[j] for j in cols if j < len(l) and MARK.search(l[j])]
            text = " ".join(x for j, x in enumerate(l) if j not in cols)
            rows_out.append({"text": text, "last": next((x for j, x in reversed(list(enumerate(l))) if j not in cols and x), ""), "auth": auth})
    return rows_out


NAMES = ["실·지사장", "비상임감사", "감사실장", "상담파트장", "청약담당", "지급담당", "팀원", "팀장", "실장", "처장", "지사장", "센터장", "원장", "이사회", "감사"]


def names_in(s):
    found, s = [], s.replace("ㆍ", "·")
    for n in NAMES:
        if n in s: found.append(n); s = s.replace(n, " ")
    return set(found)


def first_name(s):
    s = s.replace("ㆍ", "·")
    hits = [(s.find(n), n) for n in NAMES if n in s]
    hits.sort(key=lambda x: (x[0], -len(x[1])))
    return hits[0][1] if hits else None


def main():
    rows = parse()
    bad, ok, unk, unknown = [], 0, 0, []
    for f in glob.glob(str(ROOT / "knowledge" / "*" / "[!_]*.json")):
        for c in json.loads(Path(f).read_text()):
            for fct in c["facts"]:
                if not fct["cite"].startswith("위임전결세칙 별표"): continue
                q = norm(fct["quote"])
                groups = []
                for i, r in enumerate(rows):
                    if q and q in norm(r["last"]) or (q and q in norm(r["text"]) and len(q) >= 8):
                        grp = [r]
                        if not r["auth"]:  # 상위 행: 아래 '- ' 행들을 함께 본다
                            for s in rows[i + 1:]:
                                if not s["last"].startswith("-"): break
                                grp.append(s)
                        groups.append(grp)
                want = names_in(fct["value"])
                if not groups or not want:
                    unk += 1; unknown.append((c["id"], fct["label"], fct["value"])); continue
                got_sets = [set(a for r in g for a in r["auth"]) for g in groups]
                # 표의 ○ 칸이 모두 카드 값에 있고, 카드 값의 첫 전결권자가 표에 있으면 일치로 본다.
                # 괄호 속 보충 설명("지사는 지사장", "이하는 팀원")은 다른 행이나 비고에서 온 것이라 허용한다.
                first = first_name(fct["value"])
                if any(gs and gs <= want and first in gs for gs in got_sets):
                    ok += 1
                else:
                    bad.append((c["id"], fct["label"], fct["value"], fct["quote"], [" / ".join(f"{r['last']}→{'·'.join(r['auth']) or '-'}" for r in g) for g in groups[:3]]))
    lines = ["# 위임전결기준 표 대조", "", f"카드의 전결권자 {ok + len(bad) + unk}개 중 표와 일치 {ok}, 불일치 {len(bad)}, 자동 대조 불가 {unk}", ""]
    for b in bad:
        lines.append(f"- [{b[0]}] {b[1]}: 카드 '{b[2]}' / 인용 '{b[3]}'")
        for g in b[4]: lines.append(f"  - 표: {g}")
    if unknown:
        lines += ["", "## 자동 대조 불가(전결권자 이름이 없거나 표 행을 못 찾음, 사람이 확인)", ""]
        lines += [f"- [{u[0]}] {u[1]}: {u[2]}" for u in unknown]
    (ROOT / "reports" / "approval_table_check.md").write_text("\n".join(lines) + "\n")
    print(lines[2])


if __name__ == "__main__":
    main()
