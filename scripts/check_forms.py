"""떼어 낸 양식 검사: 떼어 낸 한글 파일(data/forms)을 다시 읽어, 원본 전체를 읽은 변환본(data/md)의 그 별지 부분과 맞대어 본다.

- 번호: 떼어 낸 파일의 첫 별지 표시가 그 번호인지, 다른 별지 표시가 섞이지 않았는지
- 글: 원본 별지 부분과 같은지(원본 변환본에 없던 로고 그림 줄·머리말(내규 이름)·굵은 글씨 표시 차이는 괜찮다)

  python3 scripts/check_forms.py      (npx kordoc 으로 떼어 낸 파일을 읽는다, 1~2분) — 틀린 양식이 있으면 끝 코드 1
"""
import collections
import difflib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_forms  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FORMS = ROOT / "data" / "forms"
LABEL = re.compile(r"\[별지\s*제\s*(\d+(?:-\d+)?)\s*호[^\]]*\]")


def flat(text):
    """비교용 글: 그림 줄, 표 태그, 굵게·제목 표시, 띄어쓰기·문장부호를 뺀다"""
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"</?(?:table|thead|tbody|tr|td|th|br|sup|sub|span|b|i|u|p|div)\b[^>]*>", "", text)
    return re.sub(r"[\s|#*:\-_`>~\[\]()（）［］·ㆍ.,]+", "", text.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&"))


def compare(orig, cut, no):
    """원본 별지 부분(orig)과 떼어 낸 파일 글(cut)을 맞댄다. 돌려주는 값: (맞는지, 까닭, 같은 정도 0~1)"""
    labels = LABEL.findall(cut)
    if not labels or labels[0] != no:
        return False, f"첫 별지 표시가 제{labels[0] if labels else '(없음)'}호", 0.0
    if len(labels) > 1:
        return False, "다른 별지 표시가 섞임: " + ", ".join(f"제{x}호" for x in labels[1:]), 0.0
    a, b = flat(orig), flat(cut)
    ratio = difflib.SequenceMatcher(None, a, b, autojunk=False).ratio() if a and b else 0.0
    # 머리말처럼 원본 변환본에 없던 짧은 글이 더 붙은 것은 괜찮다(원본 글은 빠짐없이 들어 있어야 한다).
    # 글자가 모두 같고 한 줄을 읽어 낸 차례만 다른 것도 괜찮다(쪽 그림은 원본과 같다)
    extra_only = a in b and len(b) - len(a) <= 40
    reordered = collections.Counter(a) == collections.Counter(b)
    return ratio >= 0.95 or extra_only or reordered, f"원본과 {ratio:.0%} 같음", ratio


def sections(md):
    i = md.find("\n[별지")
    out = {}
    for part in re.split(r"\n(?=\[별지)", md[i:] if i >= 0 else ""):
        m = LABEL.match(part.strip())
        if m:
            out.setdefault(m.group(1), part)
    return out


def main():
    index = json.loads((FORMS / "index.json").read_text())["forms"]
    rules = {r["name"]: r for r in json.loads(build_forms.RULES.read_text())["rules"]}
    files = [FORMS / v["file"] for v in index.values()]
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["npx", "-y", "kordoc", "--jobs", "4", "-d", tmp, *map(str, files)], stdin=subprocess.DEVNULL, capture_output=True, check=True)
        bad, n = [], 0
        cache = {}
        for key, v in index.items():
            rule, no = key.rsplit("/", 1)
            if rule not in cache:
                cache[rule] = sections(build_forms.rule_md(rules[rule])) if rule in rules else {}
            cut = Path(tmp) / (Path(v["file"]).stem + ".md")
            ok, why, _ = compare(cache[rule].get(no, ""), cut.read_text(encoding="utf-8") if cut.exists() else "", no)
            n += 1
            if not ok:
                bad.append(f"{rule} 별지 제{no}호: {why}")
    print(f"떼어 낸 양식 {n}개 검사: 맞음 {n - len(bad)}개" + (f", 다름 {len(bad)}개" if bad else ""))
    for b in bad:
        print("  " + b)
    if bad:
        print("다른 양식은 서식 대장(knowledge/forms.json)에서 download 를 false 로 바꾸고 cutNote 에 까닭을 적은 뒤 다시 만들어 주세요.")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
