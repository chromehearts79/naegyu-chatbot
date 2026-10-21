"""규정 하나를 카드 작성용으로 보여준다.

사용법: python3 scripts/show_rule.py <규정명 또는 코드> [--annex]
  - 조문 전문(장·절 포함), 별표 제목(--annex 이면 별표 본문도), 부칙 시행일
  - 이미 다른 카드가 인용한 조문(건너뛸 것)과 그 카드 id
  - 이 규정의 카드 id 접두어(slug)
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_knowledge import RULES, load_domains  # noqa: E402

ROMAN = {"Ⅰ": "1", "Ⅱ": "2", "Ⅲ": "3", "Ⅳ": "4"}


def slug(code):
    return "r" + ROMAN.get(code[:1], "0") + code[1:]


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    key, show_annex = sys.argv[1], "--annex" in sys.argv
    rules = json.loads(RULES.read_text())["rules"]
    r = next((r for r in rules if r["name"] == key or r["code"] == key), None)
    if not r:
        sys.exit(f"규정을 찾지 못함: {key}")
    _, cards = load_domains(tolerant=True)
    covered = {}
    for c in cards:
        for f in c["facts"]:
            m = re.match(rf"^{re.escape(r['name'])} (제\d+조(?:의\d+)?)", f["cite"])
            if m and c.get("domain") != "all_rules":
                covered.setdefault(m[1], set()).add(c["id"])
    print(f"# {r['name']} (코드 {r['code']}, 카드 id 접두어 {slug(r['code'])}-, 현행 시행 {r['effective']})")
    print(f"조문 {len(r['articles'])}개, 별표 {len(r['annexes'])}개, 별지 서식 {len(r['forms'])}개\n")
    if covered:
        print("## 이미 다른 분야 카드가 다룬 조문 (새 카드를 만들지 말고 related 에 id 만 넣을 것)")
        for no, ids in sorted(covered.items(), key=lambda x: int(re.search(r'\d+', x[0])[0])):
            print(f"- {no}: {', '.join(sorted(ids))}")
        print()
    chapter = None
    for a in r["articles"]:
        if a["chapter"] != chapter:
            chapter = a["chapter"]
            if chapter:
                print(f"\n## {chapter}")
        mark = "  [이미 다룸]" if a["no"] in covered else ""
        print(f"\n### {a['no']}({a['title']}){mark}\n{a['text']}")
    if r["annexes"]:
        print("\n## 별표")
        for x in r["annexes"]:
            print(f"\n### {x['title']} ({len(x['text'])}자)")
            if show_annex:
                print(x["text"])
    if r["forms"]:
        print("\n## 별지 서식(제목만)\n" + "\n".join(f"- {f['title']}" for f in r["forms"]))


if __name__ == "__main__":
    main()
