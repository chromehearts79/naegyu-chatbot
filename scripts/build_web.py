"""시범본 웹페이지를 파일 하나로 묶는다.

- dist/index.html    : 그대로 열 수 있는 독립 파일(인터넷 없이 동작, 외부 연결을 CSP로 막음)
- dist/artifact.html : claude.ai 아티팩트 게시용(문서 머리 태그 없이 본문만)

검사(check_knowledge.py), 독립 검증(reports/blind_check.json), 검색 시험(test_engine.js) 결과를
화면의 '검증 정보'에 넣는다.
"""
import base64
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_knowledge import load_domains  # noqa: E402
import check_changes  # noqa: E402
from review_workbook import card_hash  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
FONTS = ROOT / "web" / "fonts"



def font_faces():
    """web/fonts 의 에이투지체를 파일 안에 넣는다(폐쇄망·PC 글꼴과 상관없이 같은 모양으로 보이게)."""
    css = ["/* 에이투지체: Copyright (c) 2026 PT&, 이주임. SIL Open Font License 1.1 (https://openfontlicense.org) */"]
    for p in sorted(FONTS.glob("a2z-*.woff2")):
        b64 = base64.b64encode(p.read_bytes()).decode()
        css.append(f'@font-face{{font-family:"A2Z";font-weight:{p.stem.split("-")[1]};'
                   f'src:url(data:font/woff2;base64,{b64}) format("woff2")}}')
    return "\n".join(css)


def main():
    # 시험용: --rules 다른 규정 DB, --out 다른 폴더 (개정 감지 표시를 미리 볼 때)
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--rules", default=str(ROOT / "data" / "rules.json"))
    ap.add_argument("--out", default=str(DIST))
    args = ap.parse_args()
    dist = Path(args.out)
    check = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_knowledge.py")], capture_output=True, text=True)
    if check.returncode != 0:
        print(check.stdout)
        sys.exit("프로그램 검사 오류가 있어 묶지 않습니다.")
    test = subprocess.run(["node", str(ROOT / "scripts" / "test_engine.js"), "--json"], capture_output=True, text=True, check=True)
    search = json.loads(next(l for l in test.stdout.splitlines() if l.startswith("JSON "))[5:])

    domains, cards = load_domains()
    for c in cards:
        c.pop("_file", None)
    rules = json.loads(Path(args.rules).read_text())["rules"]
    laws = json.loads((ROOT / "knowledge" / "external_laws.json").read_text())["laws"]
    blind = json.loads((ROOT / "reports" / "blind_check.json").read_text())
    decisions = json.loads((ROOT / "reports" / "review_decisions.json").read_text())["decisions"]
    fixes = json.loads((ROOT / "knowledge" / "rule_fixes.json").read_text())["items"]
    site = json.loads((ROOT / "knowledge" / "site.json").read_text())
    site.pop("_note", None)

    # 독립 검증: 원문 대조로 결론 낸 항목은 '확인 필요'에서 뺀다
    settled = {(d["card"], d["label"]) for d in decisions}
    need = [r for r in blind if r["verdict"] == "확인 필요" and (r["card"], r["label"]) not in settled]
    by_card = {}
    for r in need:
        by_card.setdefault(r["card"], {"need": 0})["need"] += 1
    m = re.search(r"인용 문구 일치: (\d+)/(\d+)", check.stdout)

    # 개정 감지: 카드를 확인한 뒤 원문이 바뀐 조문을 인용한 카드에 표시를 붙인다
    snap = json.loads(check_changes.SNAPSHOT.read_text())
    changes, _, stale, _ = check_changes.compare({r["name"]: r for r in rules}, snap, cards)
    # 계산기 숫자의 근거 조문이 바뀌었으면 그 계산기는 숫자를 고칠 때까지 계산하지 않는다
    calc_stale = {k: [x["cite"] for x in v["cites"]] for k, v in check_changes.calc_stale(changes, {r["name"]: r for r in rules}).items()}
    for c in cards:
        if c["id"] in stale:
            c["stale"] = [{"cite": check_changes.unit_label(x["rule"], x["unit"]), "change": x["change"],
                           "effective": x["effective"]} for x in stale[c["id"]]]
    latest = max((r["effective"] for r in rules if r.get("effective")), default="")
    # 담당부서 검수: 검수한 뒤 카드 내용이 바뀌었으면 검수 표시를 떼고 다시 '검수 전'으로
    reviewed = 0
    for c in cards:
        rv = c.get("reviewed")
        if rv and rv.get("hash") == card_hash(c) and c["id"] not in stale:
            c["reviewed"] = {"date": rv["date"], "dept": rv["dept"]}
            reviewed += 1
        else:
            c.pop("reviewed", None)

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
            "basis": snap["taken"].replace("-", ".") + ".",
            "built": datetime.date.today().isoformat(),
            "latestEffective": latest,
            "stale": len(stale), "reviewed": reviewed, "calcStale": calc_stale,
            "cards": len(cards), "questions": sum(len(c["questions"]) for c in cards),
            "facts": int(m[2]), "quotesOk": int(m[1]),
            "verify": {"total": len(blind), "match": sum(r["verdict"] == "일치" for r in blind),
                       "judged": sum(r["verdict"] == "판정 통과" for r in blind) + len(settled),
                       "need": len(need), "byCard": by_card},
            "search": {"dev": search["dev"], "top3": search["top3"], "top1": search["top1"]},
            "lawChecked": laws[0]["checked"].replace("-", ".") + ".",
            "ruleFixes": fixes,
            "site": site,
        },
        "domains": [{"id": d["id"], "name": d["domain"], "topics": d["topics"]} for d in domains],
        "cards": cards,
        "rules": [{"name": r["name"], "code": r["code"], "kind": r["kind"], "effective": r["effective"],
                   "articles": [{"no": a["no"], "title": a["title"], "chapter": a["chapter"], "text": a["text"]} for a in r["articles"]],
                   "annexes": [{"title": x["title"], "text": x.get("text", "")} for x in r["annexes"]]} for r in rules],
        "buchik": buchik,
    }
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    page = (ROOT / "web" / "app.template").read_text()
    page = (page.replace("/*__FONTS__*/", font_faces())
            .replace("/*__ENGINE__*/", (ROOT / "web" / "engine.js").read_text())
            .replace("/*__DATA__*/", blob))
    dist.mkdir(exist_ok=True)
    (dist / "artifact.html").write_text(page)
    # 폐쇄망용: 외부 주소를 하나도 부르지 않도록 CSP로 막는다(글꼴·스크립트·통신 모두 파일 안의 것만)
    csp = ("default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
           "img-src data:; font-src data:; base-uri 'none'; form-action 'none'")
    standalone = ('<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n'
                  f'<meta http-equiv="Content-Security-Policy" content="{csp}">\n'
                  '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
                  "<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}"
                  "body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>\n</head>\n<body>\n"
                  + page + "\n</body>\n</html>\n")
    (dist / "index.html").write_text(standalone)
    size = (dist / "index.html").stat().st_size / 1e6
    print(f"카드 {len(cards)}장, 규정 {len(rules)}개 → {dist}/index.html ({size:.1f}MB), artifact.html")
    print(f"검증: 인용 {m[1]}/{m[2]}, 독립 검증 확인 필요 {len(need)}, 검색 시험 {search}")
    print(f"개정 감지: 카드 확인 기준 {snap['taken']}, 개정 후 재검수 전 카드 {len(stale)}장 · 담당부서 검수 완료 {reviewed}장")


if __name__ == "__main__":
    main()
