#!/usr/bin/env python3
"""내규나침반 낱말 경계: 형태소 분석기(Kiwi)로 조문·별표를 낱말 단위로 나눠 knowledge/word_bounds.json 에 적는다.

화면(web/engine.js)은 이 표시로 찾은 곳을 가른다.
- 본 결과: 낱말 경계에 맞게 걸린 곳(‘직원’ → 임직원, ‘평가결과’ → 성과평가 결과)
- 접힌 곳: 다른 낱말 속(‘인정’ → 개인정보), 반대말 머리 뒤(‘공개’ → 비공개), 엉뚱하게 띄어 걸린 곳(‘여비’ → 위하여 비상임)
분석은 유지보수 PC에서 한 번만 하고, 폐쇄망 화면에는 결과 표시만 들어간다.
내규 원문이 바뀌면 다시 돌린다. build_web.py 가 원문과 표시가 맞는지 확인하고, 다르면 묶지 않는다.

필요: pip install -r scripts/requirements-bounds.txt (분석기 버전을 고정한다. 버전이 바뀌면 낱말 나누기가 달라질 수 있다)
쓰기: python3 scripts/build_bounds.py [--rules data/rules.json]
"""
import argparse
import datetime
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "knowledge" / "word_bounds.json"
SPLITS = ROOT / "knowledge" / "word_splits.json"
KIWI_VERSION = "0.24.1"

DOTS = re.compile("[·‧ㆍ∙･・]")
WS = re.compile(r"[\s﻿]+")  # 화면(JS)의 \s 와 같게: 파이썬 \s 는 BOM 을 빼므로 더한다
TAG = re.compile(r"<[^>]+>")
H = re.compile(r"[가-힣A-Za-z0-9]")
NOUN = re.compile(r"^NN[GP]$")
NEG = set("비불미무부반")  # 반대말 머리: 낱말 첫머리에서 한 글자로 붙으면(비공개, 불이익) 그 뒤에 걸린 곳은 접는다
TAIL = set("법표장금비료자회실권서원부과팀처관인율액제")  # 접힌 곳 다시 보기에서 낱말 끝에 붙어도 되는 한 글자

# 화면에 보내는 낱말 종류. 낱말 하나 = 종류와 길이(1~9)를 담은 글자 하나, 더 길면 '이어짐'(C) 글자를 덧붙인다
N_, O_, B_, S_, P_, Q_, R_, K_, M_, C_ = range(10)  # 명사류, 기타, 조사·어미, 접미사, 접두사, 반대말 접두사, 반대말 한 글자, 한 글자 의존명사, 한 글자 관형사, 이어짐
ALPHA = "".join(chr(c) for c in range(35, 127) if c != 92)  # 큰따옴표·역슬래시를 뺀 글자 91개


def spaced(text):
    """분석기에 넣는 원문: 표 태그는 띄어쓰기로, 띄어쓰기는 한 칸으로. 띄어쓰기를 빼면 화면의 flatText 와 같다."""
    t = DOTS.sub("·", unicodedata.normalize("NFC", text or ""))
    return WS.sub(" ", TAG.sub(" ", t))


def flat_text(text):
    """web/engine.js 의 flatText 와 같은 결과"""
    return DOTS.sub("·", WS.sub("", TAG.sub("", unicodedata.normalize("NFC", text or ""))))


def u16(ch):
    return 2 if ord(ch) > 0xFFFF else 1


def fnv(s):
    """원문이 바뀌었는지 보는 지문(FNV-1a, UTF-16 단위). engine.js 의 fnv 와 같은 값"""
    h = 0x811C9DC5
    b = s.encode("utf-16-le")
    for i in range(0, len(b), 2):
        h = ((h ^ (b[i] | (b[i + 1] << 8))) * 0x01000193) & 0xFFFFFFFF
    return format(h, "08x")


def docs_of(rules):
    """(키, 원문) 목록. 키는 화면 Compass 의 조문 단위와 같다: 규정명|조번호, 별표는 규정명|별표 제목.
    내규 이름도 넣는다(@이름|규정명): '이름에 들어간 내규' 칸도 같은 기준으로(‘인정’ → 개인정보보호세칙은 아님)"""
    out = [("@이름|" + r["name"], r["name"]) for r in rules]
    for r in rules:
        for a in r["articles"]:
            out.append((r["name"] + "|" + a["no"], a["text"]))
        for x in r.get("annexes", []):
            out.append((r["name"] + "|" + x["title"], x["title"] + " " + (x.get("text") or "")))
    return out


def stale(rules, bounds=None):
    """표시가 없거나 원문과 맞지 않는 조문 키 목록(build_web.py 가 묶기 전에 확인)"""
    if bounds is None:
        if not OUT.exists():
            return [k for k, _ in docs_of(rules)]
        bounds = json.loads(OUT.read_text())["docs"]
    return [k for k, t in docs_of(rules) if k not in bounds or bounds[k][0] != fnv(flat_text(t))]


def run(rules_path):
    try:
        import kiwipiepy
        from kiwipiepy import Kiwi
    except ImportError:
        sys.exit("형태소 분석기가 없습니다: pip install -r scripts/requirements-bounds.txt")
    if kiwipiepy.__version__ != KIWI_VERSION:
        sys.exit(f"분석기 버전이 다릅니다({kiwipiepy.__version__}). 낱말 나누기가 달라질 수 있어 {KIWI_VERSION} 으로 맞춰 주세요: "
                 "pip install -r scripts/requirements-bounds.txt")
    sys.path.insert(0, str(ROOT / "scripts"))
    from check_knowledge import load_domains

    rules = json.loads(Path(rules_path).read_text())["rules"]
    lists = json.loads(SPLITS.read_text())
    headed, whole = set(lists["split"]), lists["whole"]
    docs = docs_of(rules)
    texts = [spaced(t) for _, t in docs]
    kiwi = Kiwi()
    toks = [[[t.start, t.len, t.tag, t.form] for t in ts] for ts in kiwi.tokenize(texts)]

    # 원문에 드문 말(‘반일’)은 답 카드에서 쓰인 명사로 보탠다. 쪼갤 때 조각은 2번 넘게 나온 명사여야 한다
    freq = {}
    for ts in toks:
        for _, _, tag, f in ts:
            if NOUN.match(tag) and len(f) >= 2:
                freq[f] = freq.get(f, 0) + 1
    _, cards = load_domains(tolerant=True)
    card_texts = ["\n".join([c.get("title", ""), c.get("summary", "")] + list(c.get("answer", [])) + list(c.get("questions", [])) + list(c.get("keywords", []))) for c in cards]
    for ts in kiwi.tokenize(card_texts):
        for t in ts:
            if t.tag in ("NNG", "NNP") and len(t.form) >= 2:
                freq[t.form] = freq.get(t.form, 0) + 1

    def known(w):
        return freq.get(w, 0) >= 2

    memo = {}

    def splits(w):
        if len(w) < 2:
            return []
        out = [[w]] if known(w) else []
        for i in range(2, len(w) - 1):
            if known(w[:i]):
                out += [[w[:i]] + rest for rest in splits(w[i:])]
        return out

    def split(form):
        """분석기가 한 덩어리로 둔 긴 명사를 원문 낱말로 쪼갠다. 쪼개는 길이 하나뿐이고 [정보원][장]처럼 달리 읽히지 않을 때만"""
        if not re.fullmatch(r"[가-힣]+", form):
            return None
        if form in headed:
            return [form[0], form[1:]]
        if len(form) < 4:
            return None
        cand = [p for p in splits(form) if len(p) >= 2]
        if len(cand) != 1:
            return None
        if any(known(form[:i]) and len(form) - i == 1 for i in range(2, len(form))):
            return None
        return [y for x in cand[0] for y in ([x[0], x[1:]] if x in headed else [x])]

    def refine(ts, text):
        out = []
        for s, l, tag, form in ts:
            if "·" in form and l == len(form):  # 가운뎃점으로 이은 말("제·개정")은 점 앞뒤를 낱말 경계로
                at = s
                for x in [p for p in re.split(r"(·)", form) if p]:
                    out.append([at, len(x), "SP" if x == "·" else tag, x])
                    at += len(x)
                continue
            if NOUN.match(tag) and l == len(form):
                if form not in memo:
                    memo[form] = split(form)
                if memo[form]:
                    at = s
                    for x in memo[form]:
                        out.append([at, len(x), tag, x])
                        at += len(x)
                    continue
            out.append([s, l, tag, form])
        for nm in whole:  # 고유 이름은 한 덩어리로. 이름 끝을 넘는 낱말("우정사업본부장"의 '본부장')은 이름 끝에서 끊는다
            p = text.find(nm)
            while p >= 0:
                e = p + len(nm)
                cut_out = []
                for t in out:
                    s0, l0, tag0, f0 = t
                    pieces = [t]
                    if l0 == len(f0):
                        for c in (p, e):
                            last = pieces[-1]
                            if last[0] < c < last[0] + last[1]:
                                k = c - last[0]
                                pieces[-1:] = [[last[0], k, last[2], last[3][:k]], [c, last[1] - k, last[2], last[3][k:]]]
                    cut_out += pieces
                out = cut_out
                inside = [t for t in out if t[0] >= p and t[0] + t[1] <= e]
                if inside and inside[0][0] == p and inside[-1][0] + inside[-1][1] == e and len(inside) > 1:
                    k = out.index(inside[0])
                    out[k:k + len(inside)] = [[p, len(nm), "NNP", nm]]
                p = text.find(nm, e)
        return out

    # 원문이 "(이하 …라 한다)"로 정의한 이름은 쪼개 보지 않는다(우체국금융개발원의 '개발')
    names = set()
    for text in texts:
        names.update(m[1] for m in re.finditer(r"([가-힣A-Za-z0-9·]{4,})\s*\(이하\s*[“\"‘']", text))

    dmemo = {}

    def cuts_of(form):
        """접힌 곳 다시 보기: 낱말이 원문 낱말들(+끝 한 글자)로 나뉠 때, 나누는 모든 길에서 공통인 자리(공직자|윤리|법)"""
        if form in dmemo:
            return dmemo[form]
        ds = []

        def go(rest, acc):
            if not rest:
                if len(acc) >= 2:
                    ds.append(acc)
                return
            if len(rest) == 1 and rest in TAIL and acc:
                ds.append(acc + [rest])
                return
            for k in range(2, len(rest) + 1):
                if known(rest[:k]):
                    go(rest[k:], acc + [rest[:k]])
        if not any(form in nm for nm in names):
            go(form, [])
        common = None
        for p in ds:
            cs, n = set(), 0
            for x in p:
                n += len(x)
                cs.add(n)
            common = cs if common is None else common & cs
        dmemo[form] = sorted(c for c in (common or set()) if 0 < c < len(form))
        return dmemo[form]

    def kind(tag, form, L, glued):
        if len(form) == 1 and form in NEG and L == 1 and not glued:
            return Q_ if tag == "XPN" else R_
        if tag == "XPN":
            return P_
        if tag == "NNB" and L == 1:
            return K_
        if tag == "MM" and L == 1:
            return M_
        if tag.startswith("XS"):  # 띄어쓰기 바로 뒤의 접미사는 분석기가 잘못 본 것(표 칸 "중징계 경징계"의 '경')이라 명사류로
            if not glued:
                return N_
            return S_ if tag == "XSN" else B_  # 명사 접미사(근로'자')만 낱말 덩어리에 넣고, 동사·형용사 접미사(인정'되')는 넣지 않는다
        if tag.startswith(("J", "E", "VC")):
            return B_
        if tag.startswith("NN") or tag in ("NR", "NP", "SN", "SL", "SH", "XR"):
            return N_
        return O_

    result, nb = {}, 0
    for (key, raw), text, ts in zip(docs, texts, toks):
        ts = refine(ts, text)
        # 원문 글자 → 화면 글자 위치(띄어쓰기를 뺀 UTF-16 위치)
        pos, n = [], 0
        for ch in text:
            pos.append(n)
            if ch != " ":
                n += u16(ch)
        pos.append(n)
        flat = flat_text(raw)
        assert n == len(flat.encode("utf-16-le")) // 2, key
        # 원문을 빈칸 없는 조각(낱말)으로 덮고, 조각 사이에 띄어쓰기가 있으면 " " 를 적는다
        segs, cut, end = [], [], 0
        for s, l, tag, form in ts:
            if s < end:  # 겹치는 형태소(했 → 하+었)는 앞의 것만
                continue
            for m in re.finditer(r"[^ ]+", text[end:s]):  # 분석기가 낱말로 잡지 않은 글자는 기타로
                segs.append((end + m.start(), end + m.end(), O_))
            c = kind(tag, form, pos[s + l] - pos[s], s > 0 and bool(H.match(text[s - 1])))
            # 띄어쓰기가 든 낱말(드물게 "소프트웨어 개발 보안")은 띄어쓰기마다 나눈다
            for j, m in enumerate(re.finditer(r"[^ ]+", text[s:s + l])):
                segs.append((s + m.start(), s + m.end(), c if j == 0 else (N_ if c in (N_, R_, K_) else c)))
            if NOUN.match(tag) and l == len(form):
                cut += [pos[s + k] for k in cuts_of(form)]
            end = s + l
        for m in re.finditer(r"[^ ]+", text[end:]):
            segs.append((end + m.start(), end + m.end(), O_))
        stream, prev = [], None
        for a0, b0, c in segs:
            if prev is not None and " " in text[prev:a0]:
                stream.append(" ")
            L = pos[b0] - pos[a0]
            stream.append(ALPHA[c * 9 + min(L, 9) - 1])
            L -= 9
            while L > 0:
                stream.append(ALPHA[C_ * 9 + min(L, 9) - 1])
                L -= 9
            prev = b0
        result[key] = [fnv(flat), "".join(stream), ",".join(format(x, "x") for x in sorted(set(cut)))]
        nb += len(stream)

    OUT.write_text(json.dumps({
        "_설명": "내규나침반 낱말 경계(scripts/build_bounds.py 가 만듦, 손으로 고치지 않음). 조문마다 [원문 지문, 낱말 표시, 다시 보기 자리]",
        "kiwipiepy": KIWI_VERSION, "built": datetime.date.today().isoformat(), "docs": result,
    }, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"낱말 경계: 조문·별표·내규 이름 {len(result)}개, 표시 {nb:,}글자 → {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1e6:.2f}MB)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rules", default=str(ROOT / "data" / "rules.json"))
    run(ap.parse_args().rules)
