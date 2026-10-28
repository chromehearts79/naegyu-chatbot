"""서식 대장(knowledge/forms.json)을 만들고 원문과 맞는지 점검한다.

서식 대장에는 내규마다 별지 번호, 서식 제목, 그 서식을 부르는 조문(문구까지)을 적는다.
조문 아래 '양식' 칸은 조문이 "별지 제8호 서식의 사직서"처럼 직접 부른 자리에만 붙인다. 부르는 이름이 서식 제목과 다르면
(원문 번호가 틀렸을 수 있음) 그 조문에는 붙이지 않는다(mismatch). 사람이 적는 칸(제목 고친 것, 쓰는 사람, 내는 방법,
받기 켜기, cutNote)은 다시 만들어도 그대로 둔다. 새로 생긴 별지는 받기를 켠 채로 넣는다(떼지 못하면 빌드가 빼고 알린다).

  python3 scripts/build_forms.py 인사관리세칙 [--prune]  그 내규의 서식을 원문에서 다시 읽어 대장에 넣는다(바뀐 곳을 보여 줌).
                                                       --prune: 없어진 내규를 대장에서 뺀다
  python3 scripts/build_forms.py --check                대장이 지금 원문과 맞는지만 본다(안 맞으면 끝 코드 1)
"""
import difflib
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "knowledge" / "forms.json"
RULES = ROOT / "data" / "rules.json"
MD = ROOT / "data" / "md"
NOTE = ("서식 대장. 내규마다 별지 번호·서식 제목·부르는 조문을 적는다. 만들기·점검: python3 scripts/build_forms.py. "
        "basis 는 대장을 원문과 맞춰 본 내규의 시행일, seen 은 원문에서 읽은 제목(바뀌었는지 보려고 둠), title 은 화면에 보일 제목(사람이 고칠 수 있음). "
        "writer(쓰는 사람)·submit(내는 방법)은 담당부서 확인 전이면 '확인 전'. download 가 true 인 서식만 한글 파일을 받게 한다"
        "(파일은 node scripts/cut_forms.cjs 로 원본에서 떼어 data/forms 에 둔다).")
PENDING = "확인 전"
NUM = r"\d+(?:-\d+)?"
# 법령·다른 규정의 별지를 부르는 말: "규칙 별지 제30호", "「…시행규칙」 제9조에 의하여 별지 제16호".
# 내규 끝에 그 번호 별지가 있으면 내규 별지로 본다(own_forms)
OUTSIDE = re.compile(r"(?:규칙|법률|시행령|[」｣])[^.。]{0,25}$")
# 서식 이름 뒤에 붙는 조사(가·이는 '출산휴가'처럼 이름 끝 글자와 겹쳐 떼지 않는다)
JOSA = re.compile(r"(?:와|과|를|을|에게|에서|에|으로|로|는|은|도)$")
# 서식 이름으로 끝나는 낱말: 사직서·평가표·휴직원·대장·명부·기록부·증명서 …
FORM_END = re.compile(r"(?:서|표|원|부|장|록|증|철)$")


def rule_md(rule):
    hits = [p for p in MD.glob("*.md") if re.sub(r"^\S+\.\s*", "", p.stem) == rule["name"]]
    return hits[0].read_text(encoding="utf-8") if hits else ""


def tidy_title(line):
    """서식 머리 제목을 다듬는다: '**사 직 서**' → '사직서', '근 로 계 약 서(일반직)' → '근로계약서(일반직)',
    '개인영상정보(□ 존재확인 □ 열람 ) 청구서' → '개인영상정보 청구서'(고르는 칸은 뺀다)."""
    line = re.sub(r"^#+\s*", "", line).replace("**", "").strip()
    line = re.sub(r"^[<〈《](.+)[>〉》]$", r"\1", line).strip()
    line = re.sub(r"\s*\([^()]*□[^()]*\)\s*", " ", line).strip()
    line = re.sub(r"\s+", " ", re.sub(r"[［\[]\s*[］\]]", "", line))           # '(［ ］등록 ［ ］변경등록)' → '(등록 변경등록)'
    line = re.sub(r"\(\s+", "(", re.sub(r"\s+\)", ")", line))
    line = re.sub(r"\s+양식$", "", line).strip()                                # '위촉장 양식' → '위촉장'
    toks = line.split()
    if len(toks) > 1 and all(re.fullmatch(r"[가-힣]", t) for t in toks[:-1]) and re.match(r"[가-힣]", toks[-1]):
        line = "".join(toks)
    return line


# 제목 자리에 먼저 나오지만 제목이 아닌 줄: 쪽 표시 '(앞쪽)·(전면표지)', 번호 칸 '(제 호)·접수번호·연번', 표 칸막이, 긴 설명 문장
NOT_TITLE = re.compile(r"\(?\s*(?:앞|뒤|전면|후면)\s*(?:쪽|표지)\s*\)?|\(\s*제\s*호\s*\)|제\s*호|접수\s*번호|연\s*번|번호|-+|[#\s]*|우체국금융개발원")
# 변환본의 표 태그만 지운다('<수입결의서>'처럼 꺾쇠로 감싼 제목은 남긴다)
TAG = re.compile(r"</?(?:table|thead|tbody|tr|td|th|br|sup|sub|span|b|i|u|p|div)\b[^>]*>")


def form_titles(md):
    """원문 끝의 별지에서 번호와 머리 제목을 읽는다. {번호: 제목}"""
    i = md.find("\n[별지")
    out = {}
    for part in re.split(r"\n(?=\[별지)", md[i:] if i >= 0 else ""):
        m = re.match(r"\s*\[별지\s*제\s*(" + NUM + r")\s*호[^\]]*\]", part)
        if not m:
            continue
        body = html.unescape(TAG.sub("\n", part[m.end():]))
        lines = [tidy_title(l.strip(" |")) for l in body.split("\n")]
        lines = [l for l in lines if l and not NOT_TITLE.fullmatch(l) and len(l) <= 45]
        out.setdefault(m.group(1), lines[0] if lines else "")
    return out


def form_calls(rule):
    """조문이 별지를 부르는 곳. {번호: [{art, para, phrase}]}. 범위(별지 제1호에서 별지 제5-3호까지)는 따로 표시한다."""
    calls, order = {}, []
    for a in rule["articles"]:
        paras = a.get("paras") or [{"no": 0, "text": a["text"]}]
        for p in paras:
            t = p["text"]
            for m in re.finditer(r"별지\s*제\s*(" + NUM + r")\s*호(?:\s*에서\s*별지\s*제\s*(" + NUM + r")\s*호\s*까지)?(?:\s*서식)?(?:의|에\s*의한|에\s*따른|에\s*따라|에\s*의하여)?(?:\s*서식(?:의|에\s*의한|에\s*따른)?)?", t):
                outside = bool(OUTSIDE.search(t[max(0, m.start() - 40):m.start()]))
                ref = t[m.start():m.end()].strip()
                # 부르는 문구: "별지 제8호 서식의 사직서"처럼 '…의' 뒤에 서식 이름이 오면 그 이름까지(네 낱말 안에서 서식 이름으로 끝나는 데까지,
                # 조사는 뗀다). "별지 제6호 서식에 따라"처럼 이름이 없으면 별지 번호까지만
                phrase = ref
                if re.search(r"의$", ref):
                    words, end = re.findall(r"\s*[^\s,.「」｢｣()]+", t[m.end():])[:4], m.end()
                    for wd in words:
                        end += len(wd)
                        bare = JOSA.sub("", wd.strip())
                        if FORM_END.search(bare):
                            phrase = t[m.start():end - (len(wd.strip()) - len(bare))].strip()
                            break
                item = {"art": a["no"], "para": p["no"], "phrase": phrase}
                if outside:
                    item["outside"] = True
                if m.group(2):
                    item["range"] = [m.group(1), m.group(2)]
                calls.setdefault(m.group(1), []).append(item)
                order.append(item)
    return calls


def expand_ranges(calls, nos):
    """'별지 제1호에서 별지 제5-3호까지'를 그 사이 별지마다 붙인다(원문 끝 별지 차례대로)."""
    for item in [x for v in list(calls.values()) for x in v if "range" in x]:
        a, b = item["range"]
        if a in nos and b in nos:
            for n in nos[nos.index(a) + 1:nos.index(b) + 1]:
                if item not in calls.setdefault(n, []):
                    calls[n].append(item)
    return calls


def name_mismatch(phrase, titles):
    """'별지 제4호 서식의 정보공개처리대장'처럼 조문이 부른 이름이 서식 제목들과 다르면 그 이름을, 맞거나 이름이 없으면 None."""
    m = re.search(r"(?:서식|호)의\s+(?:서식의\s+)?(.+)$", phrase)
    if not m or m.group(1).strip() == "서식":
        return None
    flat = lambda s: re.sub(r"[\s·ㆍ()（）\[\]［］]+", "", s)  # noqa: E731
    noun = flat(m.group(1))
    for t in map(flat, titles):
        if noun in t or t in noun or difflib.SequenceMatcher(None, noun, t).ratio() >= 0.6:
            return None
    return m.group(1).strip()


def own_forms(calls, nos):
    """법령 이름 뒤에 나온 별지라도 이 내규 끝에 그 번호 별지가 있으면 내규 별지로 본다(내규가 법령 서식을 제 별지로 옮겨 싣고,
    '법률자문 의뢰서'의 '법률'처럼 법령 이름이 아닌 말도 있다). 바깥 별지(outside)는 내규 끝에 그 번호가 없을 때만 남긴다.
    돌려주는 값: 내규 별지로 바꾼 부름 [(번호, 부름)] (개정 반영 때 원문을 확인하라고 보여 준다)"""
    moved = []
    for no in [n for n in nos if n in calls]:
        for c in calls[no]:
            if c.pop("outside", None):
                moved.append((no, c))
    return moved


def read_rule(rule):
    titles = form_titles(rule_md(rule))
    nos = list(titles)
    calls = expand_ranges(form_calls(rule), nos)
    return titles, calls, own_forms(calls, nos)


def load():
    return json.loads(LEDGER.read_text()) if LEDGER.exists() else {"_note": NOTE, "rules": []}


def update(names, prune=False):
    rules = {r["name"]: r for r in json.loads(RULES.read_text())["rules"]}
    led = load()
    led["_note"] = NOTE
    for name in names:
        r = rules.get(name) or sys.exit(f"내규를 못 찾음: {name}")
        titles, calls, near_law = read_rule(r)
        if not titles:
            sys.exit(f"{name}: 원문 끝에서 별지를 못 찾음(data/md 변환본 확인)")
        for no in sorted(set(calls) - set(titles)):
            arts = [c["art"] for c in calls[no] if not c.get("outside")]
            if arts:
                print(f"  {name}: {', '.join(arts)}이 별지 제{no}호를 부르는데 원문 끝에 그 번호 별지가 없음(번호가 다른지 확인)")
        for no, c in near_law:
            print(f"  {name} {c['art']}: 법령 이름 뒤에 나오지만 원문 끝에 별지 제{no}호('{titles[no]}')가 있어 이 내규 별지로 보고 양식 칸을 닮(원문 확인)")
        old = next((x for x in led["rules"] if x["rule"] == name), None)
        prev = {f["no"]: f for f in (old or {}).get("forms", [])}
        forms = []
        for no, seen in titles.items():
            p = prev.get(no, {})
            # 조문이 '별지 제N호 서식의 ○○'라고 부른 이름이 서식 제목과 다르면 표시해 둔다(원문의 번호가 틀렸을 수 있어 그 조문에는 양식 칸을 달지 않는다)
            for c in calls.get(no, []):
                miss = name_mismatch(c["phrase"], [seen, p.get("title") or seen])
                if miss:
                    c["mismatch"] = miss
                    print(f"  {name} {c['art']}: 조문은 '{miss}'(별지 제{no}호)라 부르는데 별지 제{no}호 제목은 '{seen}' → 그 조문에는 양식 칸을 달지 않음(원문 확인)")
            # 화면 제목: 사람이 고친 제목(읽은 제목과 다름)은 그대로, 아니면 새로 읽은 제목
            title = p["title"] if p.get("title") and p.get("title") != p.get("seen") else seen
            f = {"no": no, "label": f"별지 제{no}호 서식", "seen": seen, "title": title,
                 "calls": calls.get(no, []), "writer": p.get("writer", PENDING), "submit": p.get("submit", PENDING),
                 "download": p.get("download", True)}
            if p.get("cutNote"):
                f["cutNote"] = p["cutNote"]
            if p and p.get("seen") != seen:
                print(f"  {name} 별지 제{no}호: 원문 제목이 바뀜 '{p.get('seen')}' → '{seen}' (화면 제목 '{f['title']}' 확인)")
            if p and p.get("calls") != f["calls"]:
                print(f"  {name} 별지 제{no}호: 부르는 조문이 바뀜 → {', '.join(c['art'] for c in f['calls']) or '없음'}")
            forms.append(f)
        for no in set(prev) - set(titles):
            print(f"  {name} 별지 제{no}호: 원문에서 없어짐(대장에서 뺌)")
        entry = {"rule": name, "code": r["code"], "basis": r["effective"], "forms": forms}
        if old:
            led["rules"][led["rules"].index(old)] = entry
        else:
            led["rules"].append(entry)
        n_call = sum(1 for f in forms if f["calls"])
        print(f"{name}: 별지 {len(forms)}개 (조문에서 부르는 것 {n_call}개, 안 불리는 것 {len(forms) - n_call}개), 기준 시행일 {r['effective']}")
    if prune:
        gone = [e["rule"] for e in led["rules"] if e["rule"] not in rules]
        led["rules"] = [e for e in led["rules"] if e["rule"] in rules]
        for g in gone:
            print(f"{g}: 내규가 없어져 서식 대장에서 뺌")
    LEDGER.write_text(json.dumps(led, ensure_ascii=False, indent=1) + "\n")


def check(rules=None, led=None):
    """대장이 지금 원문과 맞는지. 돌려주는 값: {내규: [안 맞는 까닭]} (빈 사전이면 다 맞음)"""
    rules = rules or {r["name"]: r for r in json.loads(RULES.read_text())["rules"]}
    led = led or load()
    bad = {}
    for e in led["rules"]:
        why = bad.setdefault(e["rule"], [])
        r = rules.get(e["rule"])
        if not r:
            why.append("내규가 없어짐")
            continue
        if r["effective"] != e["basis"]:
            why.append(f"내규가 개정됨({e['basis']} → {r['effective']})")
        arts = {a["no"]: a for a in r["articles"]}
        for f in e["forms"]:
            for c in f["calls"]:
                a = arts.get(c["art"])
                # 같은 항 번호가 두 번 나오는 원문도 있어(스토킹예방지침 제5조 ③) 그 번호의 항을 모두 본다
                texts = a and ([p["text"] for p in a.get("paras", []) if p["no"] == c["para"]] or [a["text"]])
                if not texts or not any(c["phrase"] in t for t in texts):
                    why.append(f"별지 제{f['no']}호를 부르는 {c['art']} 문구 '{c['phrase']}'가 원문에 없음")
        if not why:
            del bad[e["rule"]]
    return bad


def main():
    args = sys.argv[1:]
    if args == ["--check"]:
        bad = check()
        for k, v in bad.items():
            print(f"{k}: " + " / ".join(v))
        print("서식 대장: 원문과 맞음" if not bad else "서식 대장을 다시 만들어 주세요: python3 scripts/build_forms.py " + " ".join(bad))
        sys.exit(1 if bad else 0)
    names = [a for a in args if a != "--prune"]
    if not names and "--prune" not in args:
        sys.exit(__doc__)
    update(names, prune="--prune" in args)


if __name__ == "__main__":
    main()
