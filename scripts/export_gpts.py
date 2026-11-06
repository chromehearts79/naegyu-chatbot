"""인터넷망용 AI(ChatGPT GPTs·프로젝트 등)에 넣을 지식 묶음을 만든다.

  python3 scripts/export_gpts.py  → dist/gpts/
    지시문.md                 : GPT '지침(Instructions)' 칸에 붙여 넣을 글
    카드_<분류>.md (11개 안팎)  : 문답 카드(답·근거 조문·인용 문구·관련 카드)
    조문_원문.md               : 내규 전체의 조문·별표 원문(카드에 없는 질문의 근거 찾기용)

GPTs 지식 파일은 20개까지라 분류별로 묶는다. 내규는 공개 대상이지만, 직원이 질문에 개인정보·비공개 정보를
넣지 않도록 지시문과 첫 인사에 안내한다(인공지능전환관리세칙 제29조제2항).
"""
import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_knowledge import ROOT, load_domains  # noqa: E402
from review_workbook import categories, rule_of  # noqa: E402

OUT = ROOT / "dist" / "gpts"

INSTRUCTIONS = """당신은 (재)우체국금융개발원 직원을 돕는 '내규챗봇'입니다. 지식 파일에 있는 문답 카드와 내규 조문 원문만 근거로 답합니다.

[답하는 방법]
1. 먼저 지식 파일의 카드(카드_*.md)에서 질문에 맞는 카드를 찾습니다. 조건이 여러 개인 질문이면 조건마다 맞는 카드를 찾아 각각 답한 뒤 하나로 정리합니다. '여러 규정 종합' 카드가 있으면 우선 씁니다.
2. 답마다 근거를 밝힙니다: 카드 ID와 조문(예: [카드 spouse-birth-leave] 복무세칙 제19조제8항). 카드의 인용 문구를 바꾸지 말고 그대로 옮깁니다.
3. 카드에 없으면 조문_원문.md 에서 조문을 찾아 그 원문을 인용해 답하고, "준비된 카드에는 없어 조문 원문으로 답함"이라고 밝힙니다.
4. 카드와 조문 어디에도 없으면 지어내지 말고 "내규에 직접 정한 내용을 찾지 못했습니다. 담당부서에 확인하세요."라고 답합니다.
5. 카드에 "담당부서 확인"이나 규정 간 충돌, 법령과 다른 점이 적혀 있으면 반드시 함께 알립니다. 카드에 '규정 개정 · 재검수 전' 표시가 있으면 현행 원문을 먼저 확인하라고 알립니다.
6. 날짜·일수·금액은 카드와 조문의 기준대로 계산 과정을 보여 줍니다(예: 출산예정일 기준 시작일). 직원이 준 날짜를 그대로 쓰고, 기준이 애매하면 계산하지 말고 담당부서 확인을 권합니다.
7. 이어 묻는 질문("그럼 ~는?")은 앞 질문의 상황을 이어서 답합니다.

[지켜야 할 것]
- 모든 답 끝에 "AI가 작성한 답변입니다. 중요한 결정 전에는 근거 조문 원문과 담당부서에 확인하세요."를 붙입니다(인공지능전환관리세칙 제30조).
- 직원에게 개인정보(주민번호·연락처·건강정보 등)나 금융원 비공개 정보를 질문에 넣지 말라고 안내하고, 그런 정보가 들어오면 다루지 말고 지우라고 알립니다(같은 세칙 제29조제2항).
- 규정 해석으로 개인의 인사·징계·급여를 결정하지 않습니다. 안내만 합니다.
- 쉬운 우리말로, 짧은 문장으로 답합니다. 핵심 숫자는 굵게 씁니다.

[첫 인사]
"내규챗봇입니다. 내규 {N}개를 근거로 답합니다. 질문에 개인정보나 비공개 정보는 넣지 마세요."
"""


def instructions(n):
    """지시문. 첫 인사의 내규 수는 지금 내규 수로 채운다."""
    return INSTRUCTIONS.replace("{N}", str(n))


def card_md(c, rule):
    lines = [f"### [{c['id']}] {c['title']}", f"- 규정: {rule}", f"- 요약: {c['summary']}"]
    lines += [f"- {a}" for a in c["answer"]]
    lines.append("- 근거:")
    lines += [f"  - {f['label']}: {f['value']} — {f['cite']} 「{f['quote']}」" for f in c["facts"]]
    if c.get("law_refs"):
        lines.append("- 외부 법령: " + "; ".join(f"{l['law']} {l['article']} 「{l['quote']}」" for l in c["law_refs"]))
    if c.get("check"):
        lines.append("- 확인 필요: " + " / ".join(c["check"]))
    if c.get("related"):
        lines.append("- 관련 카드: " + ", ".join(c["related"]))
    lines.append("- 이렇게도 물음: " + " / ".join(c["questions"][:8]))
    return "\n".join(lines)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*.md"):
        f.unlink()
    cat_of, rules = categories()
    _, cards = load_domains()
    groups = {}
    for c in cards:
        rule = c.get("rule") or rule_of(c)
        cat = "상황별 종합" if c["id"].startswith("combo-") else cat_of.get(rule.replace("·", "").replace(" ", ""), "기타")
        groups.setdefault(cat, []).append(card_md(c, rule))
    today = datetime.date.today().isoformat()
    for cat, items in groups.items():
        head = f"# 내규챗봇 문답 카드 — {cat}\n\n기준일 {today}. 카드 ID, 근거 조문, 인용 문구(원문 그대로)를 답에 밝힐 것.\n\n"
        (OUT / f"카드_{cat.replace('·', '_')}.md").write_text(head + "\n\n".join(items) + "\n")
    parts = [f"# 내규 조문 원문 ({len(rules)}개, 기준일 {today})\n"]
    for name, r in rules.items():
        parts.append(f"\n## {name} (시행 {r.get('effective') or '-'})\n")
        parts += [a["text"] for a in r["articles"]]
        parts += [f"\n[{x['title']}]\n{x.get('text', '')}" for x in r.get("annexes") or []]
    (OUT / "조문_원문.md").write_text("\n".join(parts) + "\n")
    (OUT / "지시문.md").write_text(instructions(len(rules)))
    files = sorted(OUT.glob("*.md"))
    size = sum(f.stat().st_size for f in files) / 1e6
    print(f"{len(files)}개 파일, {size:.1f}MB → dist/gpts/ (GPTs 지식 파일은 20개까지)")


if __name__ == "__main__":
    main()
