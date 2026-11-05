"""규정 개정 감지: 카드가 인용한 조문의 원문이 카드를 확인한 뒤 바뀌었는지 찾는다.

인용 문구가 원문에 그대로 있는지만 보는 check_knowledge.py 로는, 같은 조문에 단서가 새로 붙는 개정
("다만, 수습 직원은 10일")을 놓친다. 그래서 카드를 확인한 시점의 조문·별표·부칙 원문 지문(hash)을
knowledge/source_snapshot.json 에 남겨 두고, 규정 원본을 다시 변환할 때마다 비교한다.

사용:
  python3 scripts/check_changes.py                 # 비교 → reports/change_report.md, knowledge/stale_cards.json
                                                   # (계산기 숫자 근거 조문이 바뀌면 '다시 확인할 계산기'도 알린다)
  python3 scripts/check_changes.py --accept 복무세칙  # 그 규정의 카드를 다시 확인했으면 지문을 지금 원문으로 갱신
  python3 scripts/check_changes.py --accept-all    # 전부 갱신(처음 만들 때)
  python3 scripts/check_changes.py --rules 다른.json  # 다른 규정 DB와 비교(시험용)
"""
import argparse
import datetime
import difflib
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_knowledge import RE_ANNEX, RE_ART, RE_BUCHIK, RULES, ROOT, KNOWLEDGE, load_domains, norm  # noqa: E402

SNAPSHOT = KNOWLEDGE / "source_snapshot.json"
STALE = KNOWLEDGE / "stale_cards.json"
CALC_BASIS = KNOWLEDGE / "calc_basis.json"
REPORT = ROOT / "reports" / "change_report.md"
# 바뀐 조문을 글자 단위로 보여 주기 위한 원문 사본(규정 원문이라 data/ 처럼 저장소에는 넣지 않는다)
TEXTS = ROOT / "data" / "snapshot_texts.json"


def units_of(rule):
    """규정 하나를 조문·별표·부칙 단위로 나눈다. {단위 이름: 원문}"""
    u = {}
    for a in rule["articles"]:
        u[a["no"]] = a["text"]
        for p in a.get("paras") or []:  # 항 단위도 따로 본다(같은 조의 다른 항만 바뀐 경우를 가려내려고)
            u[f"{a['no']}제{p['no']}항"] = p["text"]
    for x in rule.get("annexes") or []:
        u["별표:" + x["title"]] = x["text"]
    for b in rule.get("buchik") or []:
        u["부칙:" + (b.get("effective") or "")] = b["text"]
    return u


def digest(text):
    return hashlib.sha1(norm(text).encode()).hexdigest()[:16]


def para_of_cite(cite):
    """인용이 항(호·목 포함)까지 적었으면 그 항 단위 이름, 아니면 None"""
    m = RE_ART.match(cite)
    return f"{m['art']}제{m['para']}항" if m and m["para"] else None


def unit_of_cite(cite, rules):
    """인용 → (규정명, 단위 이름). 조·항·호를 인용해도 조 전체를 단위로 본다(같은 조의 다른 항이 바뀌어도 알 수 있게)."""
    m = RE_BUCHIK.match(cite)
    if m:
        return m["rule"], "부칙:" + m["date"]
    m = RE_ANNEX.match(cite)
    if m and "조" not in m["annex"]:
        r = rules.get(m["rule"])
        key = m["annex"].replace(" ", "")
        hit = next((x["title"] for x in (r or {}).get("annexes") or [] if x["title"].replace(" ", "").startswith(key)), None)
        return m["rule"], "별표:" + (hit or m["annex"])
    m = RE_ART.match(cite)
    if m:
        return m["rule"], m["art"]
    return None, None


def load_rules(path):
    return {r["name"]: r for r in json.loads(Path(path).read_text())["rules"]}


def take(rules, only=None, old=None, texts_old=None):
    """지문을 만든다. only 가 있으면 그 규정만 새로 찍고 나머지는 old 를 그대로 둔다."""
    snap = {"taken": datetime.date.today().isoformat(), "rules": dict((old or {}).get("rules", {}))}
    texts = dict(texts_old or {})
    for name, r in rules.items():
        if only is not None and name not in only:
            continue
        u = units_of(r)
        snap["rules"][name] = {"effective": r.get("effective"), "units": {k: digest(v) for k, v in u.items()}}
        texts[name] = u
    if only is not None:  # 사라진 규정 정리
        for name in list(snap["rules"]):
            if name in only and name not in rules:
                del snap["rules"][name]
    return snap, texts


def compare(rules, snap, cards):
    """바뀐 단위와 영향받는 카드를 찾는다."""
    changes = {}  # (규정, 단위) → 'changed' | 'removed' | 'added'
    eff = {}
    for name, s in snap["rules"].items():
        r = rules.get(name)
        if not r:
            for k in s["units"]:
                changes[(name, k)] = "removed"
            continue
        cur = {k: digest(v) for k, v in units_of(r).items()}
        for k, h in s["units"].items():
            if k not in cur:
                changes[(name, k)] = "removed"
            elif cur[k] != h:
                changes[(name, k)] = "changed"
        for k in cur:
            if k not in s["units"]:
                changes[(name, k)] = "added"
        if r.get("effective") != s.get("effective"):
            eff[name] = (s.get("effective"), r.get("effective"))
    for name in rules:
        if name not in snap["rules"]:
            for k in units_of(rules[name]):
                changes[(name, k)] = "added"
            eff[name] = (None, rules[name].get("effective"))
    # 다시 확인할 카드(stale): 인용한 조(항까지 적었으면 그 항)가 바뀜. 같은 조의 다른 항만 바뀐 카드는 참고(related)로만 둔다.
    stale, related = {}, {}
    for c in cards:
        for f in c["facts"]:
            key = unit_of_cite(f["cite"], rules)
            kind = changes.get(key)
            if kind not in ("changed", "removed"):
                continue
            para = para_of_cite(f["cite"])
            pk = changes.get((key[0], para)) if para else None
            # 조는 바뀌었는데 바뀐 항을 하나도 못 찾으면(항 나누기가 어긋난 경우) 안전하게 그 조를 인용한 카드 모두 다시 확인
            if para and kind == "changed" and not any(k[0] == key[0] and k[1].startswith(key[1] + "제") for k in changes):
                para = None
            target = stale if (not para or kind == "removed" or pk in ("changed", "removed") or (key[0], para) not in changes and para not in snap["rules"].get(key[0], {}).get("units", {})) else related
            item = {"rule": key[0], "unit": para if target is stale and para and pk else key[1], "change": pk or kind,
                    "effective": (rules.get(key[0]) or {}).get("effective")}
            lst = target.setdefault(c["id"], [])
            if item not in lst:
                lst.append(item)
    for cid in list(related):
        if cid in stale:
            del related[cid]
    return changes, eff, stale, related


def calc_stale(changes, rules):
    """계산기 숫자 근거(calc_basis.json) 조문이 바뀐 계산기 → {계산기: {title, cites: [{cite, change}]}}"""
    basis = json.loads(CALC_BASIS.read_text())
    basis.pop("_note", None)
    out = {}
    for kind, b in basis.items():
        for x in b["basis"]:
            key = unit_of_cite(x["cite"], rules)
            ch = changes.get(key)
            if ch not in ("changed", "removed"):
                continue
            para = para_of_cite(x["cite"])
            pk = changes.get((key[0], para)) if para else None
            # 항까지 적었는데 같은 조의 다른 항만 바뀌었으면 넘어간다(바뀐 항을 하나도 못 찾으면 안전하게 포함)
            if para and pk is None and any(k[0] == key[0] and k[1].startswith(key[1] + "제") for k in changes):
                continue
            out.setdefault(kind, {"title": b["title"], "cites": []})["cites"].append({"cite": x["cite"], "change": pk or ch})
    return out


def unit_label(name, unit):
    if unit.startswith("별표:"):
        return f"{name} {unit[3:]}"
    if unit.startswith("부칙:"):
        return f"{name} 부칙({unit[3:]})"
    return f"{name} {unit}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rules", default=str(RULES))
    ap.add_argument("--accept", nargs="*", help="다시 확인을 마친 규정 이름(들)")
    ap.add_argument("--accept-all", action="store_true")
    args = ap.parse_args()

    rules = load_rules(args.rules)
    old = json.loads(SNAPSHOT.read_text()) if SNAPSHOT.exists() else None
    texts_old = json.loads(TEXTS.read_text()) if TEXTS.exists() else {}

    if (args.accept_all or args.accept is not None) and Path(args.rules).resolve() != RULES.resolve():
        sys.exit("시험용 규정 DB로는 지문을 갱신하지 않습니다.")
    if args.accept_all or args.accept is not None or old is None:
        only = None if (args.accept_all or old is None) else set(args.accept)
        unknown = [n for n in (only or []) if n not in rules and n not in (old or {}).get("rules", {})]
        if unknown:
            sys.exit(f"없는 규정 이름: {', '.join(unknown)}")
        snap, texts = take(rules, only, old, texts_old)
        SNAPSHOT.write_text(json.dumps(snap, ensure_ascii=False, indent=1) + "\n")
        TEXTS.write_text(json.dumps(texts, ensure_ascii=False))
        print(f"지문 갱신: {'전체' if only is None else ', '.join(sorted(only))} ({snap['taken']})")
        old = snap

    _, cards = load_domains(tolerant=True)
    changes, eff, stale, related = compare(rules, old, cards)
    # 시험용 다른 규정 DB와 비교할 때는 실제 결과 파일을 건드리지 않고 그 DB 옆에 보고서만 쓴다
    trial = Path(args.rules).resolve() != RULES.resolve()
    report = Path(args.rules).with_suffix(".change_report.md") if trial else REPORT
    calcs = calc_stale(changes, rules)
    if not trial:
        STALE.write_text(json.dumps({"taken": old["taken"], "cards": stale, "calcs": calcs}, ensure_ascii=False, indent=1) + "\n")

    # 보고서
    cited = {}
    for c in cards:
        for f in c["facts"]:
            cited.setdefault(unit_of_cite(f["cite"], rules), set()).add(c["id"])
    lines = ["# 규정 개정 감지 결과", "",
             f"카드 확인 기준(지문) {old['taken']} · 비교한 규정 원본 {Path(args.rules).name}", ""]
    is_para = lambda u: "항" in u and "조제" in u  # noqa: E731
    changed = [(k, v) for k, v in sorted(changes.items()) if v != "added" and not is_para(k[1])]
    added = [k for k, v in sorted(changes.items()) if v == "added" and not k[1].startswith("부칙:") and not is_para(k[1])]
    new_buchik = [k for k, v in sorted(changes.items()) if v == "added" and k[1].startswith("부칙:")]
    lines += [f"- 바뀌거나 없어진 조문·별표·부칙: {len(changed)}개",
              f"- 다시 확인해야 할 카드: **{len(stale)}장** (인용한 조·항이 바뀜)",
              f"- 참고할 카드: {len(related)}장 (같은 조의 다른 항만 바뀜)",
              f"- 다시 확인할 계산기: **{len(calcs)}종** (계산기 숫자의 근거 조문이 바뀜)",
              f"- 새로 생긴 조문·별표(카드가 없을 수 있음): {len(added)}개",
              f"- 새 부칙(개정 이력): {len(new_buchik)}개", ""]
    if eff:
        lines += ["## 시행일이 바뀐 규정", ""] + [f"- {n}: {a or '-'} → {b or '-'}" for n, (a, b) in sorted(eff.items())] + [""]
    if changed:
        lines += ["## 바뀐 조문과 영향받는 카드", ""]
        for (name, unit), kind in changed:
            ids = sorted(cited.get((name, unit), []))
            must = [i for i in ids if any(x["rule"] == name and x["unit"].startswith(unit) for x in stale.get(i, []))]
            ref = [i for i in ids if i not in must]
            paras = [k[1] for k, v in sorted(changes.items()) if k[0] == name and is_para(k[1]) and k[1].startswith(unit + "제")]
            lines.append(f"### {unit_label(name, unit)} ({'삭제' if kind == 'removed' else '변경'})" + (f" — 바뀐 항: {', '.join(p[len(unit):] for p in paras)}" if paras else ""))
            if must:
                lines.append("다시 확인할 카드: " + ", ".join(must))
            if ref:
                lines.append("참고(다른 항 인용): " + ", ".join(ref))
            before = texts_old.get(name, {}).get(unit)
            after = units_of(rules[name]).get(unit) if name in rules else None
            if before is not None and after is not None:
                diff = list(difflib.unified_diff(before.splitlines(), after.splitlines(), "개정 전", "개정 후", lineterm="", n=0))
                if diff:
                    lines += ["", "```diff"] + diff[:60] + ["```"]
            lines.append("")
    if calcs:
        lines += ["## 다시 확인할 계산기", "",
                  "계산기 숫자의 근거 조문이 바뀌었다. 새 원문을 보고 web/engine.js 의 그 계산기 숫자와 knowledge/calc_basis.json 의 문구(has)를 고친다.",
                  "확인 전에 화면을 다시 만들면 그 계산기는 '근거 조문 개정 · 계산 멈춤'으로 표시되고 계산하지 않는다.", ""]
        lines += [f"- {v['title']} ({k}): " + ", ".join(f"{x['cite']}({'삭제' if x['change'] == 'removed' else '변경'})" for x in v["cites"]) for k, v in sorted(calcs.items())] + [""]
    if added:
        lines += ["## 새로 생긴 조문·별표", ""] + [f"- {unit_label(n, u)}" + (" (카드 있음)" if (n, u) in cited else " — 카드 없음, 필요하면 새 카드 작성") for n, u in added] + [""]
    lines += ["## 처리 순서", "",
              "1. 위 카드의 답·근거를 새 원문에 맞게 고친다(`python3 scripts/show_rule.py <규정명>`).",
              "2. `python3 scripts/check_knowledge.py` 오류 0건, `python3 scripts/blind_check.py prepare <카드 id…>` 로 다시 검증.",
              "   '다시 확인할 계산기'가 있으면 그 계산기 숫자(web/engine.js)와 근거표(knowledge/calc_basis.json)도 새 원문대로 고친다.",
              "3. 그 규정의 카드를 다 확인했으면 `python3 scripts/check_changes.py --accept <규정명>`.",
              "4. `python3 scripts/build_web.py` 로 다시 묶는다. 확인 전 카드는 화면에 '규정 개정 · 재검수 전'으로 표시된다.", ""]
    report.write_text("\n".join(lines))
    print(f"바뀐 단위 {len(changed)}개, 다시 확인할 카드 {len(stale)}장, 다시 확인할 계산기 {len(calcs)}종, 새 조문 {len(added)}개 → {report}")


if __name__ == "__main__":
    main()
