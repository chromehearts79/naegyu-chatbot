"""시범본 웹페이지를 파일 하나로 묶는다.

- dist/index.html    : 그대로 열 수 있는 독립 파일(인터넷 없이 동작, 외부 연결을 CSP로 막음)
- dist/artifact.html : claude.ai 아티팩트 게시용(문서 머리 태그 없이 본문만)

검사(check_knowledge.py), 독립 검증(reports/blind_check.json), 검색 시험(test_engine.js) 결과를
화면의 '검증 정보'에 넣는다. 내규나침반 낱말 경계(knowledge/word_bounds.json)는 원문과 맞을 때만 묶는다.
서식 대장(knowledge/forms.json)에서 받기를 켠 별지는 대장·떼어 낸 파일(data/forms)이 지금 원문과 맞을 때만 한글 파일째 묶는다.
"""
import base64
import collections
import datetime
import json
import re
import subprocess
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_knowledge import load_domains  # noqa: E402
import check_changes  # noqa: E402
from review_workbook import card_hash  # noqa: E402
import build_bounds  # noqa: E402
import build_forms  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
FONTS = ROOT / "web" / "fonts"
FORMS = ROOT / "data" / "forms"


def form_payload(rules, led, index):
    """서식 대장에서 받기를 켠 별지 중 지금 원문과 맞는 것만 한글 파일째 싣는다.
    rules: {내규 이름: 내규}, led: 서식 대장, index: data/forms/index.json 의 forms. 돌려주는 값: (실을 서식, 못 실은 까닭)"""
    bad = build_forms.check(rules, led)
    out, warn = [], []
    # 물은 말·찾은 말에 양식 이름이 들어 있으면 띄우는데, 서식 대장 전체에서 이름이 하나뿐인 양식만(신고서·확인서처럼 겹치는 이름은 하나로 단정하지 않는다)
    flat = lambda s: re.sub(r"\s+", "", s)  # noqa: E731
    names = [flat(f["title"]) for e in led["rules"] for f in e["forms"]]
    # 부르는 항의 글(나침반에서 찾은 낱말이 그 항에 나오면 그 항이 부르는 양식도 맨 위에 띄운다)
    def para_text(rule, art, para):
        a = next((x for x in rules[rule]["articles"] if x["no"] == art), None) if rule in rules else None
        if not a:
            return ""
        return "\n".join(p["text"] for p in a.get("paras", []) if p["no"] == para) or a["text"]

    for e in led["rules"]:
        for f in [x for x in e["forms"] if x.get("download")]:
            name = f"{e['rule']} 별지 제{f['no']}호({f['title']})"
            cut = index.get(f"{e['rule']}/{f['no']}")
            # 양식 칸을 다는 조문: 법령·다른 규정의 별지를 부르는 곳, 부르는 이름이 서식 제목과 다른 곳(원문 번호가 틀렸을 수 있음)은 뺀다
            calls = [{"art": c["art"], "para": c["para"], "phrase": c["phrase"], "text": para_text(e["rule"], c["art"], c["para"])}
                     for c in f["calls"] if not c.get("outside") and not c.get("mismatch")]
            by_name = names.count(flat(f["title"])) == 1
            if e["rule"] in bad:
                warn.append(f"{name}: " + " / ".join(bad[e["rule"]]) + " → python3 scripts/build_forms.py " + e["rule"])
            elif not calls and not by_name:
                continue  # 달 조문도 없고 이름도 겹쳐 띄울 곳이 없다
            elif not cut or cut["effective"] != rules[e["rule"]]["effective"] or not (FORMS / cut["file"]).exists():
                warn.append(f"{name}: 떼어 낸 파일이 없거나 옛 원문에서 나옴 → node scripts/cut_forms.cjs")
            else:
                eff = rules[e["rule"]]["effective"]
                out.append({"rule": e["rule"], "no": f["no"], "title": f["title"], "calls": calls,
                            "file": f"{f['title']}({e['rule']} 별지 제{f['no']}호, {eff} 시행).hwp", "effective": eff,
                            "byName": by_name, "packed": "deflate-raw", "b64": pack_form((FORMS / cut["file"]).read_bytes())})
    return out, warn


def pack_form(data):
    """한글 파일을 압축해(raw deflate) 글자로 싣는다. 파일 안 빈칸이 많아 40%쯤 준다. 화면에서 inflateRaw 로 푼다"""
    z = zlib.compressobj(9, zlib.DEFLATED, -15)
    return base64.b64encode(z.compress(data) + z.flush()).decode()



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
    # 낱말 경계가 원문과 맞는지 먼저 본다. 내규가 바뀌었는데 다시 만들지 않으면 그 조문만 예전처럼(다른 낱말 속도 본 결과로) 보여서 막는다
    rules = json.loads(Path(args.rules).read_text())["rules"]
    bounds = json.loads(build_bounds.OUT.read_text())["docs"] if build_bounds.OUT.exists() else {}
    off = build_bounds.stale(rules, bounds)
    if off:
        print(f"낱말 경계 표시가 없거나 원문과 맞지 않는 조문 {len(off)}개: {', '.join(off[:5])}{' …' if len(off) > 5 else ''}")
        if Path(args.rules).resolve() == (ROOT / "data" / "rules.json").resolve():
            sys.exit("내규 원문이 바뀌었습니다. 먼저 낱말 경계를 다시 만들어 주세요: python3 scripts/build_bounds.py "
                     "(형태소 분석기 필요: pip install -r scripts/requirements-bounds.txt)")
    keys = {k for k, _ in build_bounds.docs_of(rules)} - set(off)
    check = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_knowledge.py")], capture_output=True, text=True)
    if check.returncode != 0:
        print(check.stdout)
        sys.exit("프로그램 검사 오류가 있어 묶지 않습니다.")
    test = subprocess.run(["node", str(ROOT / "scripts" / "test_engine.js"), "--json"], capture_output=True, text=True, check=True)
    search = json.loads(next(l for l in test.stdout.splitlines() if l.startswith("JSON "))[5:])

    domains, cards = load_domains()
    for c in cards:
        c.pop("_file", None)
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

    # 서식 받기: 서식 대장(knowledge/forms.json)에서 받기를 켠 별지 중 원문·떼어 낸 파일과 맞는 것만
    index = json.loads((FORMS / "index.json").read_text())["forms"] if (FORMS / "index.json").exists() else {}
    forms, form_warn = form_payload({r["name"]: r for r in rules}, build_forms.load(), index)

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
        "bounds": {k: v for k, v in bounds.items() if k in keys},
        "forms": forms,
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
    per = collections.Counter(f["rule"] for f in forms)
    print(f"서식 받기: {len(forms)}개 · 내규 {len(per)}개 · 압축해 {sum(len(f['b64']) for f in forms) / 1e6:.1f}MB"
          + (f" (많은 순: {', '.join(f'{k} {v}' for k, v in per.most_common(3))})" if per else ""))
    for w in form_warn:
        print(f"  서식 받기에서 뺌: {w}")


if __name__ == "__main__":
    main()
