"""문답 카드 독립 검증 (검증 2단계).

다른 모델(로컬 qwen3.5:35b)에게 카드의 답은 보여주지 않고, 인용한 조문 원문과 질문, 항목 이름만 준다.
그 모델이 조문에서 찾아 적은 값과 카드의 값을 비교해 다르면 표시한다.
결과는 reports/blind_check.md 와 reports/blind_check.json 에 쓴다.
"""
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_knowledge import RULES, RE_ART, Rules, load_domains, norm  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT_MD = ROOT / "reports" / "blind_check.md"
OUT_JSON = ROOT / "reports" / "blind_check.json"
MODEL = "qwen3.5:35b"


def ask(prompt):
    body = {"model": MODEL, "stream": False, "think": False, "format": "json",
            "messages": [{"role": "user", "content": prompt}],
            "options": {"num_ctx": 32768, "temperature": 0}}
    req = urllib.request.Request("http://localhost:11434/api/chat", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    return json.loads(json.load(urllib.request.urlopen(req, timeout=600))["message"]["content"])


def bigrams(s):
    s = re.sub(r"\s+", "", norm(s))
    return {s[i:i + 2] for i in range(len(s) - 1)}


def key_numbers(s):
    """단위가 붙은 숫자만 뽑는다. '제15-2호' 같은 서식·조문 번호나 '1명당'은 뺀다."""
    s = norm(str(s)).replace(",", "")
    return {m.group(1) for m in re.finditer(r"(?<![제\d.-])(\d+)\s*(?=일|주|시간|분|회|년|개월|세|포인트|원|학년|%)", s)}


def compare(mine, theirs):
    """1차 비교. '일치', '부분'(검증 모델이 일부만 적음), '판정 필요' 중 하나."""
    theirs = str(theirs or "").strip()
    if not theirs or theirs in ("없음", "-", "null", "해당 없음"):
        return "판정 필요", "검증 모델이 찾지 못함"
    km, kt = key_numbers(mine), key_numbers(theirs)
    if km and km <= kt:
        return "일치", ""
    if km and kt and kt < km:
        return "판정 필요", f"검증 모델이 일부만 적음 {sorted(kt)} / 카드 {sorted(km)}"
    if km:
        return "판정 필요", f"숫자 다름 카드 {sorted(km)} / 검증 {sorted(kt)}"
    bm, bt = bigrams(mine), bigrams(theirs)
    if len(bm & bt) / max(1, len(bm)) >= 0.5:
        return "일치", ""
    return "판정 필요", "표현이 다름"


def judge(scope, label, value):
    """카드 값을 보여주고 조문에 비추어 맞는지만 묻는다(2차 판정)."""
    prompt = ("아래 [조문]에 비추어, 항목 설명이 조문 내용과 맞는지 판정하라. 표현이 달라도 뜻이 같으면 '예'.\n"
              "조문과 어긋나거나 조문에서 확인할 수 없으면 '아니오'.\n"
              f"항목: {label}\n설명: {value}\n"
              '형식: {"판정": "예" 또는 "아니오", "이유": "한 문장"}\n\n[조문]\n' + scope)
    # 빈 응답(JSON 해석 실패)이 가끔 나와 한 번 더 묻는다
    for attempt in range(2):
        try:
            r = ask(prompt)
            return r.get("판정", ""), r.get("이유", "")
        except Exception as e:
            err = str(e)
    return "오류", err


def scope_of(rules, cite):
    """인용 위치의 원문. 호·목 인용이면 앞뒤 맥락을 위해 항 전체를 넘긴다."""
    m = RE_ART.match(cite)
    if m and (m["item"] or m["mok"]):
        cite = f"{m['rule']} {m['art']}" + (f"제{m['para']}항" if m["para"] else "")
    scope, _, _ = rules.resolve(cite)
    return cite, scope


def around(scope, quote, width=1500):
    """긴 원문(별표 표 등)은 인용 문구 앞뒤만 잘라 넘긴다. 검증 모델의 입력 한도를 넘지 않게."""
    if len(scope) <= 6000:
        return scope
    i = norm(scope).find(norm(quote)[:40])
    i = max(0, i if i >= 0 else 0)
    return norm(scope)[max(0, i - width): i + width]


def main():
    rules = Rules(RULES)
    cards = load_domains()[1]
    # 인자로 카드 id 나 분야 이름을 주면 그것만 다시 검증하고, 나머지 카드는 지난 결과를 그대로 둔다.
    only = set(sys.argv[1:])
    chosen = [c for c in cards if not only or c["id"] in only or c["domain"] in only]
    ids_now, redo = {c["id"] for c in cards}, {c["id"] for c in chosen}
    kept = []
    if only and OUT_JSON.exists():
        kept = [r for r in json.loads(OUT_JSON.read_text()) if r["card"] in ids_now and r["card"] not in redo]
    results, t0 = [], time.time()
    for c in chosen:
        scopes = {}
        for fct in c["facts"]:
            k, t = scope_of(rules, fct["cite"])
            t = around(t, fct["quote"])
            scopes[k] = t if k not in scopes or len(scopes[k]) > 6000 else scopes[k] + ("\n…\n" + t if t not in scopes[k] else "")
        context = "\n\n".join(f"[{k}]\n{t}" for k, t in scopes.items())
        labels = [f["label"] for f in c["facts"]]
        prompt = (
            "너는 회사 내규 검토자다. 아래 [조문]만 근거로, 직원 질문에 답할 때 필요한 각 항목의 값을 조문에서 찾아 짧게 적어라.\n"
            "조문 표현을 살려 숫자·기간·조건을 정확히 적고, 조문에 없으면 \"없음\"이라고 적어라. 추측하지 마라.\n"
            f"직원 질문: {c['questions'][0]}\n"
            "항목(순서대로):\n" + "\n".join(f"{i + 1}. {l}" for i, l in enumerate(labels)) + "\n"
            '형식: {"values": ["1번 항목 값", "2번 항목 값", ...]}  (항목 수와 같은 개수)\n\n[조문]\n' + context)
        try:
            vals = ask(prompt).get("values", [])
        except Exception as e:  # 모델 오류는 그 카드만 표시하고 계속한다
            vals = []
            print("  오류", e)
        for i, fct in enumerate(c["facts"]):
            theirs = vals[i] if i < len(vals) else ""
            verdict, why = compare(fct["value"], theirs)
            row = {"card": c["id"], "label": fct["label"], "mine": fct["value"], "theirs": theirs,
                   "cite": fct["cite"], "step1": verdict, "step1_note": why}
            if verdict == "판정 필요":
                _, scope = scope_of(rules, fct["cite"])
                scope = around(scope, fct["quote"])
                row["judge"], row["judge_reason"] = judge(scope, fct["label"], fct["value"])
                row["verdict"] = "판정 통과" if row["judge"] == "예" else "확인 필요"
            else:
                row["verdict"] = "일치"
            results.append(row)
        bad = sum(1 for r in results if r["card"] == c["id"] and r["verdict"] == "확인 필요")
        print(f"{c['id']:<32} 항목 {len(labels):>2}  확인 필요 {bad}", flush=True)

    order = {c["id"]: i for i, c in enumerate(cards)}
    results = sorted(kept + results, key=lambda r: order[r["card"]])
    count = {v: sum(1 for r in results if r["verdict"] == v) for v in ("일치", "판정 통과", "확인 필요")}
    lines = ["# 독립 검증 결과 (로컬 qwen3.5:35b)\n",
             "1차: 카드 값을 숨기고 인용 위치의 조문만 주어 값을 다시 찾게 한 뒤 숫자를 비교.",
             "2차: 1차에서 어긋나거나 숫자가 없는 항목은 카드 값과 조문을 함께 주고 맞는지 판정.\n",
             f"- 항목 {len(results)}개: 1차 일치 {count['일치']}, 2차 판정 통과 {count['판정 통과']}, "
             f"확인 필요 {count['확인 필요']} ({time.time() - t0:.0f}초)\n",
             "## 확인 필요\n", "| 카드 | 항목 | 카드 값 | 검증 모델 1차 값 | 판정 이유 |", "|---|---|---|---|---|"]
    cell = lambda s: str(s).replace("|", "/").replace("\n", " ")[:140]
    for r in results:
        if r["verdict"] == "확인 필요":
            lines.append(f"| {r['card']} | {r['label']} | {cell(r['mine'])} | {cell(r['theirs'])} | {cell(r.get('judge_reason'))} |")
    lines += ["\n## 2차 판정으로 통과한 항목\n", "| 카드 | 항목 | 1차 사유 | 판정 이유 |", "|---|---|---|---|"]
    for r in results:
        if r["verdict"] == "판정 통과":
            lines.append(f"| {r['card']} | {r['label']} | {cell(r['step1_note'])} | {cell(r.get('judge_reason'))} |")
    OUT_MD.write_text("\n".join(lines) + "\n")
    OUT_JSON.write_text(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"\n{count} → {OUT_MD}")


if __name__ == "__main__":
    main()
