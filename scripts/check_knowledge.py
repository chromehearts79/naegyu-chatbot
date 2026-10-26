"""문답 카드를 규정 DB와 대조하는 프로그램 검사 (검증 1단계).

- 인용한 조문·항·호·목이 실제로 있는지
- 인용 문구(quote)가 그 위치의 원문에 글자 그대로 있는지
- 사실(value)에 나온 숫자가 인용 위치의 원문에 있는지
- 답변 문단의 숫자가 카드가 인용한 조문들 안에 있는지
- 관련 카드·주제 id, 중복 질문
- 계산기 숫자 근거표(knowledge/calc_basis.json)의 문구가 그 조문 원문에 있는지
- 카드·계산기의 '○○에 확인하세요' 안내에 확인 안 된 부서 이름이 없는지('관련 부서에 문의하세요'로 쓴다)

결과는 reports/check_report.md 에 쓴다. 실패가 있으면 종료 코드 1.
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE = ROOT / "knowledge"
RULES = ROOT / "data" / "rules.json"
REPORT = ROOT / "reports" / "check_report.md"
ENGINE = ROOT / "web" / "engine.js"
# 문의처 안내 문장(직원에게 누구에게 확인·문의하라고 권하는 말)과 AI가 짐작해 적은 부서 이름.
# '정보보안담당관'처럼 내규가 정한 역할 이름은 뒤에 '관'이 붙어 걸리지 않는다
ASK_VERB = re.compile(r"확인하세요|확인해\s?보세요|확인하시기|확인이 필요|확인 필요|확인\)|문의|물어보세요|상의하세요|상담하세요|얘기하세요|말씀하세요|연락하세요|안내를 따르세요")
GUESSED_DEPT = re.compile(r"인사팀|[가-힣]{2,}팀(?=에|이나|과|와)|(?:인사|회계|복무|총무|보수|급여|복리후생|정보보안|노무|재무|예산|자산|교육)(?:·[가-힣]+)?\s?담당(?!관)(?:\s?부서|자)?"
                          r"|(?:담당|관련)\s?부서?\([^)]*\)|\((?:경영지원실|전략기획실|감사실|AX금융기획실)\)"
                          # 부서를 정하지 않은 안내도 한 가지 말('관련 부서에 문의하세요')로 쓴다. '회계업무담당부서'처럼 앞에 글자가 붙은 내규 용어는 뺀다
                          r"|(?<![가-힣])담당\s?부서")


def domain_dirs():
    """분야 폴더 목록. 폴더마다 _topics.json(분야 이름·주제), 카드 *.json, _devset.json(시험 질문)이 있다."""
    return sorted(p for p in KNOWLEDGE.iterdir() if p.is_dir() and (p / "_topics.json").exists())


def load_domains(tolerant=False):
    """(분야 정보 목록, 전체 카드). 카드마다 어느 분야인지 domain 에 적는다.
    tolerant 이면 아직 쓰는 중이라 읽히지 않는 카드 파일은 건너뛴다(여럿이 동시에 작업할 때)."""
    domains, cards = [], []
    for d in domain_dirs():
        meta = json.loads((d / "_topics.json").read_text())
        meta["id"] = d.name
        domains.append(meta)
        for f in sorted(d.glob("*.json")):
            if f.name.startswith("_"):
                continue
            try:
                loaded = json.loads(f.read_text())
            except json.JSONDecodeError:
                if tolerant:
                    continue
                raise
            for c in loaded:
                c["domain"] = d.name
                c["_file"] = f"{d.name}/{f.name}"
                cards.append(c)
    return domains, cards

RE_ART = re.compile(r"^(?P<rule>.+?) (?P<art>제\d+조(?:의\d+)?)(?:제(?P<para>\d+)항)?(?:제(?P<item>\d+)호)?(?:(?P<mok>[가-힣])목)?$")
RE_ANNEX = re.compile(r"^(?P<rule>.+?) (?P<annex>별표.*)$")
RE_BUCHIK = re.compile(r"^(?P<rule>.+?) 부칙\((?P<date>[\d.]+)\)$")


def norm(s):
    s = unicodedata.normalize("NFC", s)
    for a in "‧ㆍ･・∙":
        s = s.replace(a, "·")
    s = s.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    s = s.replace("｢", "「").replace("｣", "」").replace("<br>", " ").replace("|", " ")
    return re.sub(r"\s+", " ", s).strip()


def digits(s):
    return {d.replace(",", "") for d in re.findall(r"\d[\d,]*", s)}


def sub_block(text, marker_re, next_re):
    """text 에서 marker_re 로 시작하는 줄부터 next_re 줄 직전까지 잘라낸다."""
    lines = text.split("\n")
    out, on = [], False
    for line in lines:
        if on and next_re.match(line):
            break
        if not on and marker_re.match(line):
            on = True
        if on:
            out.append(line)
    return "\n".join(out) if out else None


class Rules:
    def __init__(self, path):
        self.by_name = {r["name"]: r for r in json.loads(path.read_text())["rules"]}

    def resolve(self, cite):
        """인용 문자열을 (원문 범위, 조문 전체, 오류) 로 바꾼다."""
        m = RE_BUCHIK.match(cite)
        if m:
            r = self.by_name.get(m["rule"])
            if not r:
                return None, None, f"규정 없음: {m['rule']}"
            b = next((b for b in r["buchik"] if b.get("effective") == m["date"]), None)
            return (b["text"], b["text"], None) if b else (None, None, f"부칙 없음: {m['date']}")
        m = RE_ANNEX.match(cite)
        if m and "조" not in m["annex"]:
            r = self.by_name.get(m["rule"])
            if not r:
                return None, None, f"규정 없음: {m['rule']}"
            a = next((a for a in r["annexes"] if a["title"].replace(" ", "").startswith(m["annex"].replace(" ", ""))), None)
            return (a["text"], a["text"], None) if a else (None, None, f"별표 없음: {m['annex']}")
        m = RE_ART.match(cite)
        if not m:
            return None, None, f"인용 형식 오류: {cite}"
        r = self.by_name.get(m["rule"])
        if not r:
            return None, None, f"규정 없음: {m['rule']}"
        art = next((a for a in r["articles"] if a["no"] == m["art"]), None)
        if not art:
            return None, None, f"조문 없음: {m['rule']} {m['art']}"
        scope = art["text"]
        if m["para"]:
            n = int(m["para"])
            p = next((p for p in art["paras"] if p["no"] == n), None)
            if not p:
                return None, art["text"], f"항 없음: 제{n}항"
            scope = p["text"]
        if m["item"]:
            blk = sub_block(scope, re.compile(rf"^\s*{m['item']}\.\s"), re.compile(r"^\s*\d+\.\s"))
            if not blk:
                return None, art["text"], f"호 없음: 제{m['item']}호"
            scope = blk
        if m["mok"]:
            blk = sub_block(scope, re.compile(rf"^\s*{m['mok']}\.\s"), re.compile(r"^\s*[가-힣]\.\s"))
            if not blk:
                return None, art["text"], f"목 없음: {m['mok']}목"
            scope = blk
        return scope, art["text"], None


def main():
    # 인자로 카드 파일 경로를 주면 그 파일들만 검사한다(보고서 파일은 쓰지 않음). 여럿이 동시에 작업할 때 쓴다.
    only = {str(Path(a).resolve()) for a in sys.argv[1:]}
    rules = Rules(RULES)
    domains, cards = load_domains(tolerant=bool(only))
    all_cards = cards
    if only:
        cards = [c for c in cards if str((KNOWLEDGE / c["_file"]).resolve()) in only]
    topics = {t["id"] for d in domains for t in d["topics"]}
    laws = json.loads((KNOWLEDGE / "external_laws.json").read_text())["laws"]
    ids = [c["id"] for c in all_cards]
    errors, warns, lines = [], [], []

    def err(c, msg):
        errors.append(f"[{c['id']}] {msg}")

    def warn(c, msg):
        warns.append(f"[{c['id']}] {msg}")

    mine = {c["id"] for c in cards}
    for dup in {i for i in ids if ids.count(i) > 1 and i in mine}:
        errors.append(f"[{dup}] id 중복")
    seen_q = {norm(q): c["id"] for c in all_cards if c["id"] not in mine for q in c["questions"]}
    n_facts = n_quotes_ok = 0
    for c in cards:
        for t in c["topics"]:
            if t not in topics:
                err(c, f"없는 주제: {t}")
        for r in c.get("related", []):
            if r not in ids:
                err(c, f"없는 관련 카드: {r}")
        if len(c["questions"]) < 4:
            warn(c, f"예상 질문이 {len(c['questions'])}개뿐")
        for q in c["questions"]:
            k = norm(q)
            if k in seen_q and seen_q[k] != c["id"]:
                warn(c, f"다른 카드({seen_q[k]})와 같은 질문: {q}")
            seen_q[k] = c["id"]
        article_texts = []
        for fct in c["facts"]:
            n_facts += 1
            scope, art_text, e = rules.resolve(fct["cite"])
            if e:
                err(c, f"{fct['label']}: {e}")
                continue
            article_texts.append(art_text)
            q = norm(fct["quote"])
            if q in norm(scope):
                n_quotes_ok += 1
            elif q in norm(art_text):
                warn(c, f"{fct['label']}: 인용 문구가 {fct['cite']} 범위 밖(같은 조문 안)에 있음")
            else:
                err(c, f"{fct['label']}: 인용 문구가 원문에 없음 → \"{fct['quote']}\"")
            missing = digits(fct["value"]) - digits(norm(scope).replace(",", ""))
            if missing:
                err(c, f"{fct['label']}: 값의 숫자 {sorted(missing)} 가 {fct['cite']} 원문에 없음")
        for ref in c.get("law_refs", []):
            law = next((l for l in laws if norm(l["law"]) == norm(ref["law"]) and l["article"] == ref["article"]), None)
            if not law:
                err(c, f"외부 법령 사본 없음: {ref['law']} {ref['article']}")
            elif norm(ref["quote"]) not in norm(law["text"]):
                err(c, f"외부 법령 인용이 사본에 없음 → \"{ref['quote']}\"")
            else:
                article_texts.append(law["text"])
        pool = digits(" ".join(norm(t) for t in article_texts).replace(",", ""))
        for i, para in enumerate(c["answer"], 1):
            missing = digits(para) - pool
            if missing:
                warn(c, f"답변 {i}문단의 숫자 {sorted(missing)} 가 인용 조문에 없음")

    # 계산기 숫자 근거: 계산기가 쓰는 숫자의 출처 문구가 지금 원문에 그대로 있는지(개정되면 여기서 걸린다)
    basis = json.loads((KNOWLEDGE / "calc_basis.json").read_text())
    basis.pop("_note", None)
    n_has = n_has_ok = 0
    for c in cards:
        if c.get("calc") and c["calc"] not in basis:
            err(c, f"계산기 숫자 근거표(calc_basis.json)에 없는 계산기: {c['calc']}")
        if c.get("calc_link") and c["calc_link"] not in basis:
            err(c, f"계산기 숫자 근거표(calc_basis.json)에 없는 계산기: {c['calc_link']}")
    for kind, b in basis.items():
        for x in b["basis"]:
            scope, _, e = rules.resolve(x["cite"])
            if e:
                errors.append(f"[계산기 {kind}] {x['cite']}: {e}")
                continue
            for has in x["has"]:
                n_has += 1
                if norm(has) in norm(scope):
                    n_has_ok += 1
                else:
                    errors.append(f"[계산기 {kind}] {x['cite']} 원문에 \"{has}\" 가 없음 → 계산기 숫자(web/engine.js)를 새 원문대로 고치고 근거표도 고칠 것")

    # 문의처 안내: 담당 부서를 확인하기 전까지 '○○에 확인하세요'에 부서 이름을 쓰지 않고 '관련 부서에 문의하세요'로 쓴다.
    # AI가 고른 부서가 틀린 경우가 많았다(예: 국내 출장인데 '인사·회계 담당', 내규에 없는 '인사팀').
    # 내규가 정한 역할 이름(행동강령책임관·카드관리담당자·관리부서 등)과 외부 기관(고용센터 등)은 괜찮다.
    for c in cards:
        texts = [c.get("summary", "")] + list(c["answer"]) + list(c.get("notes", [])) + [f["value"] for f in c["facts"]]
        for t in texts:
            for s in re.split(r"(?<=[.?!])\s+", t.replace("**", "")):  # 굵게(**)가 '확인**이 필요'처럼 말을 끊어 뺀다
                m = ASK_VERB.search(s) and GUESSED_DEPT.search(s)
                if m:
                    err(c, f"문의처 안내에 '{m.group(0)}' → '관련 부서에 문의하세요'로: {s.strip()}")
    for i, line in enumerate(ENGINE.read_text().splitlines(), 1):
        m = ASK_VERB.search(line) and GUESSED_DEPT.search(line)
        if m:
            errors.append(f"[계산기 안내] web/engine.js {i}행: '{m.group(0)}' → '관련 부서에 문의하세요'로")

    # 첫 화면 '자주 찾는 분야'(site.json featured)가 있는 주제·카드를 가리키는지
    site = json.loads((KNOWLEDGE / "site.json").read_text())
    by_id = {c["id"] for c in all_cards}
    topic_refs = {f"{d['id']}:{t['id']}" for d in domains for t in d["topics"]}
    for f in site.get("featured", []):
        for r in f["topics"]:
            if r not in topic_refs:
                errors.append(f"[site.json 자주 찾는 분야 '{f['name']}'] 없는 주제: {r}")
        for cid in f.get("cards", []):
            if cid not in by_id:
                errors.append(f"[site.json 자주 찾는 분야 '{f['name']}'] 없는 카드: {cid}")

    lines.append("# 문답 카드 프로그램 검사 결과\n")
    lines.append(f"- 카드 {len(cards)}개, 예상 질문 {sum(len(c['questions']) for c in cards)}개, 사실 {n_facts}개")
    lines.append(f"- 인용 문구 일치: {n_quotes_ok}/{n_facts}")
    lines.append(f"- 계산기 숫자 근거: 계산기 {len(basis)}종, 근거 문구 일치 {n_has_ok}/{n_has}")
    lines.append(f"- 오류 {len(errors)}건, 경고 {len(warns)}건\n")
    if errors:
        lines.append("## 오류\n" + "\n".join(f"- {e}" for e in errors) + "\n")
    if warns:
        lines.append("## 경고\n" + "\n".join(f"- {w}" for w in warns) + "\n")
    if not only:
        REPORT.parent.mkdir(exist_ok=True)
        REPORT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
