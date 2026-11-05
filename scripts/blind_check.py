"""문답 카드 독립 검증 (검증 2단계).

다른 AI에게 카드의 답은 보여주지 않고, 인용한 조문 원문과 질문, 항목 이름만 주어 값을 다시 찾게 한다.
그 값과 카드의 값을 비교해 다르면 표시한다. AI 호출은 이 스크립트가 하지 않고 파일로 주고받는다.

  blind_check.py prepare <카드 id|분야…>     문제 파일(questions.json)을 쓴다
  blind_check.py first <answers.json> --ai 이름   1차 답을 읽어 판정하고, 필요하면 judge_questions.json 을 쓴다
  blind_check.py finish <judge_answers.json> --ai 이름   2차 답을 읽어 마무리하고 보고서를 쓴다
  blind_check.py remaining                   답을 아직 받지 않은 카드
  blind_check.py sample 20                   분야를 섞어 카드 id 를 고른다

작업 파일은 reports/blind_work/ 에 쌓이고, finish 가 끝나면 지워진다.
결과는 reports/blind_check.md 와 reports/blind_check.json 에 쓴다.
"""
import argparse
import json
import random
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_knowledge import RULES, RE_ART, Rules, load_domains, norm  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT_MD = ROOT / "reports" / "blind_check.md"
OUT_JSON = ROOT / "reports" / "blind_check.json"
WORK = ROOT / "reports" / "blind_work"


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


def _read(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def _scope(rules, fct):
    return around(scope_of(rules, fct["cite"])[1], fct["quote"])


def prepare(card_ids):
    """카드 값과 인용 문구는 빼고, 조문·질문·항목 이름만 담은 문제 파일을 쓴다."""
    rules = Rules(RULES)
    by_id = {c["id"]: c for c in load_domains()[1]}
    unknown = [i for i in card_ids if i not in by_id]
    if unknown:
        raise ValueError("없는 카드: " + ", ".join(unknown))
    path = WORK / "questions.json"
    items = {q["card"]: q for q in _read(path, [])}
    for cid in card_ids:
        c = by_id[cid]
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
        items[cid] = {"card": cid, "question": c["questions"][0], "labels": labels, "context": context, "prompt": prompt}
    return _write(path, list(items.values()))


def remaining():
    """답을 아직 받지 않은 카드."""
    done = {r["card"] for r in _read(WORK / "rows.json", [])}
    return [q["card"] for q in _read(WORK / "questions.json", []) if q["card"] not in done]


def _judge_questions(rows, by_id, rules):
    out = []
    for r in rows:
        if r["step1"] != "판정 필요":
            continue
        fct = by_id[r["card"]]["facts"][r["idx"]]
        scope = _scope(rules, fct)
        prompt = ("아래 [조문]에 비추어, 항목 설명이 조문 내용과 맞는지 판정하라. 표현이 달라도 뜻이 같으면 '예'.\n"
                  "조문과 어긋나거나 조문에서 확인할 수 없으면 '아니오'.\n"
                  f"항목: {r['label']}\n설명: {r['mine']}\n"
                  '형식: {"판정": "예" 또는 "아니오", "이유": "한 문장"}\n\n[조문]\n' + scope)
        out.append({"key": f"{r['card']}|{r['idx']}", "label": r["label"], "value": r["mine"], "context": scope, "prompt": prompt})
    return out


def first_pass(answers, ai_name):
    """받은 카드만 1차 비교해 작업 파일에 쌓는다. 2차가 필요한 행이 있으면 judge_questions.json 경로를 돌려준다."""
    cards = {c["id"]: c for c in load_domains()[1]}
    asked = {q["card"] for q in _read(WORK / "questions.json", [])}
    rows_all = _read(WORK / "rows.json", [])
    new = []
    for cid, vals in answers.items():
        if cid not in asked:
            raise ValueError("문제 파일에 없는 카드: " + cid)
        rows_all = [r for r in rows_all if r["card"] != cid]
        for i, fct in enumerate(cards[cid]["facts"]):
            theirs = vals[i] if i < len(vals) else ""
            verdict, why = compare(fct["value"], theirs)
            row = {"card": cid, "label": fct["label"], "mine": fct["value"], "theirs": theirs,
                   "cite": fct["cite"], "step1": verdict, "step1_note": why,
                   "verdict": "일치" if verdict == "일치" else "", "ai": ai_name, "idx": i}
            new.append(row)
    rows_all += new
    _write(WORK / "rows.json", rows_all)
    jpath = WORK / "judge_questions.json"
    jq = _judge_questions(rows_all, cards, Rules(RULES))
    if jq:
        return new, _write(jpath, jq)
    jpath.unlink(missing_ok=True)
    return new, None


def finish(judge_answers, ai_name):
    """2차 답으로 판정을 마무리하고 보고서를 쓴다. 판정별 개수를 돌려준다."""
    left = remaining()
    if left:
        raise ValueError("답을 받지 않은 카드가 있다: " + ", ".join(left))
    rows = _read(WORK / "rows.json", [])
    need = [r for r in rows if r["step1"] == "판정 필요"]
    missing = [f"{r['card']}|{r['idx']}" for r in need if f"{r['card']}|{r['idx']}" not in judge_answers]
    if missing:
        raise ValueError("2차 답이 빠진 항목: " + ", ".join(missing))
    for r in need:
        a = judge_answers[f"{r['card']}|{r['idx']}"]
        r["judge"], r["judge_reason"] = a.get("판정", ""), a.get("이유", "")
        r["verdict"] = "판정 통과" if r["judge"] == "예" else "확인 필요"
    for r in rows:
        r.pop("idx", None)
        r.setdefault("ai", ai_name)
    cards = load_domains()[1]
    ids_now, redo = {c["id"] for c in cards}, {r["card"] for r in rows}
    kept = [r for r in _read(OUT_JSON, []) if r["card"] in ids_now and r["card"] not in redo]
    order = {c["id"]: i for i, c in enumerate(cards)}
    results = sorted(kept + rows, key=lambda r: order[r["card"]])
    count = {v: sum(1 for r in results if r["verdict"] == v) for v in ("일치", "판정 통과", "확인 필요")}
    names = sorted({r["ai"] for r in rows})
    lines = [f"# 독립 검증 결과 (답한 AI: {', '.join(names)})\n",
             "1차: 카드 값을 숨기고 인용 위치의 조문만 주어 값을 다시 찾게 한 뒤 숫자를 비교.",
             "2차: 1차에서 어긋나거나 숫자가 없는 항목은 카드 값과 조문을 함께 주고 맞는지 판정.\n",
             f"- 항목 {len(results)}개: 1차 일치 {count['일치']}, 2차 판정 통과 {count['판정 통과']}, "
             f"확인 필요 {count['확인 필요']}\n",
             "## 확인 필요\n", "| 카드 | 항목 | 카드 값 | 검증 AI 1차 값 | 판정 이유 |", "|---|---|---|---|---|"]
    cell = lambda s: str(s).replace("|", "/").replace("\n", " ")[:140]
    for r in results:
        if r["verdict"] == "확인 필요":
            lines.append(f"| {r['card']} | {r['label']} | {cell(r['mine'])} | {cell(r['theirs'])} | {cell(r.get('judge_reason'))} |")
    lines += ["\n## 2차 판정으로 통과한 항목\n", "| 카드 | 항목 | 1차 사유 | 판정 이유 |", "|---|---|---|---|"]
    for r in results:
        if r["verdict"] == "판정 통과":
            lines.append(f"| {r['card']} | {r['label']} | {cell(r['step1_note'])} | {cell(r.get('judge_reason'))} |")
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    OUT_JSON.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    shutil.rmtree(WORK, ignore_errors=True)
    return count


def sample_cards(n, seed=20261105):
    """분야를 돌아가며 n개를 고른다. 같은 시드면 같은 결과."""
    rnd = random.Random(seed)
    groups = {}
    for c in load_domains()[1]:
        groups.setdefault(c["domain"], []).append(c["id"])
    for g in groups.values():
        rnd.shuffle(g)
    names = sorted(groups)
    rnd.shuffle(names)
    out = []
    while len(out) < n and any(groups.values()):
        for d in names:
            if groups[d] and len(out) < n:
                out.append(groups[d].pop())
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="문답 카드 독립 검증")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("ids", nargs="+", help="카드 id 나 분야 이름")
    p = sub.add_parser("first")
    p.add_argument("answers")
    p.add_argument("--ai", required=True)
    p = sub.add_parser("finish")
    p.add_argument("judge_answers", nargs="?")
    p.add_argument("--ai", required=True)
    p = sub.add_parser("sample")
    p.add_argument("n", type=int)
    sub.add_parser("remaining")
    a = ap.parse_args(argv)
    if a.cmd == "prepare":
        cards = load_domains()[1]
        ids = [c["id"] for c in cards if c["id"] in a.ids or c["domain"] in a.ids]
        print(prepare(ids))
    elif a.cmd == "first":
        rows, jq = first_pass(json.loads(Path(a.answers).read_text(encoding="utf-8")), a.ai)
        print(f"이번 항목 {len(rows)}개, 남은 카드 {len(remaining())}개" + (f", 2차 문제 {jq}" if jq else ""))
    elif a.cmd == "finish":
        ja = json.loads(Path(a.judge_answers).read_text(encoding="utf-8")) if a.judge_answers else {}
        print(finish(ja, a.ai), "→", OUT_MD)
    elif a.cmd == "sample":
        print(" ".join(sample_cards(a.n)))
    else:
        print(" ".join(remaining()))


if __name__ == "__main__":
    main()
