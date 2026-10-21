"""시범본 웹페이지를 파일 하나로 묶는다.

- dist/index.html    : 그대로 열 수 있는 독립 파일(인터넷 없이도 동작, 글꼴만 기본 글꼴로 바뀜)
- dist/artifact.html : claude.ai 아티팩트 게시용(문서 머리 태그 없이 본문만)

검사(check_knowledge.py), 독립 검증(reports/blind_check.json), 검색 시험(test_engine.js) 결과를
화면의 '검증 정보'에 넣는다.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KNOW = ROOT / "knowledge" / "birth_childcare"
DIST = ROOT / "dist"


def load_cards():
    cards = []
    for f in sorted(KNOW.glob("*.json")):
        if not f.name.startswith("_"):
            cards += json.loads(f.read_text())
    return cards


def main():
    check = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_knowledge.py")], capture_output=True, text=True)
    if check.returncode != 0:
        print(check.stdout)
        sys.exit("프로그램 검사 오류가 있어 묶지 않습니다.")
    test = subprocess.run(["node", str(ROOT / "scripts" / "test_engine.js"), "--json"], capture_output=True, text=True, check=True)
    search = json.loads(next(l for l in test.stdout.splitlines() if l.startswith("JSON "))[5:])

    cards = load_cards()
    topics = json.loads((KNOW / "_topics.json").read_text())
    rules = json.loads((ROOT / "data" / "rules.json").read_text())["rules"]
    laws = json.loads((ROOT / "knowledge" / "external_laws.json").read_text())["laws"]
    blind = json.loads((ROOT / "reports" / "blind_check.json").read_text())
    decisions = json.loads((ROOT / "reports" / "review_decisions.json").read_text())["decisions"]
    fixes = json.loads((ROOT / "knowledge" / "rule_fixes.json").read_text())["items"]

    # 독립 검증: 원문 대조로 결론 낸 항목은 '확인 필요'에서 뺀다
    settled = {(d["card"], d["label"]) for d in decisions}
    need = [r for r in blind if r["verdict"] == "확인 필요" and (r["card"], r["label"]) not in settled]
    by_card = {}
    for r in need:
        by_card.setdefault(r["card"], {"need": 0})["need"] += 1
    m = re.search(r"인용 문구 일치: (\d+)/(\d+)", check.stdout)

    # 카드가 인용한 부칙만 따로 싣는다(원문 보기용)
    buchik = {}
    for c in cards:
        for f in c["facts"]:
            bm = re.match(r"^(.+?) 부칙\(([\d.]+)\)$", f["cite"])
            if bm:
                r = next(r for r in rules if r["name"] == bm[1])
                b = next(b for b in r["buchik"] if b.get("effective") == bm[2])
                buchik.setdefault(bm[1], {})[bm[2]] = b["text"]

    data = {
        "meta": {
            "basis": topics["basis_date"].replace("-", ".") + ".",
            "cards": len(cards), "questions": sum(len(c["questions"]) for c in cards),
            "facts": int(m[2]), "quotesOk": int(m[1]),
            "verify": {"total": len(blind), "match": sum(r["verdict"] == "일치" for r in blind),
                       "judged": sum(r["verdict"] == "판정 통과" for r in blind) + len(settled),
                       "need": len(need), "byCard": by_card},
            "search": {"dev": search["dev"], "top3": search["top3"], "top1": search["top1"]},
            "lawChecked": laws[0]["checked"].replace("-", ".") + ".",
            "ruleFixes": fixes,
        },
        "topics": topics["topics"],
        "cards": cards,
        "rules": [{"name": r["name"], "code": r["code"], "kind": r["kind"], "effective": r["effective"],
                   "articles": [{"no": a["no"], "title": a["title"], "chapter": a["chapter"], "text": a["text"]} for a in r["articles"]],
                   "annexes": [{"title": x["title"], "text": x.get("text", "")} for x in r["annexes"]]} for r in rules],
        "buchik": buchik,
    }
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    page = (ROOT / "web" / "app.html").read_text()
    page = page.replace("/*__ENGINE__*/", (ROOT / "web" / "engine.js").read_text()).replace("/*__DATA__*/", blob)
    DIST.mkdir(exist_ok=True)
    (DIST / "artifact.html").write_text(page)
    standalone = ('<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n'
                  '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
                  "<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}"
                  "body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>\n</head>\n<body>\n"
                  + page + "\n</body>\n</html>\n")
    (DIST / "index.html").write_text(standalone)
    size = (DIST / "index.html").stat().st_size / 1e6
    print(f"카드 {len(cards)}장, 규정 {len(rules)}개 → dist/index.html ({size:.1f}MB), dist/artifact.html")
    print(f"검증: 인용 {m[1]}/{m[2]}, 독립 검증 확인 필요 {len(need)}, 검색 시험 {search}")


if __name__ == "__main__":
    main()
