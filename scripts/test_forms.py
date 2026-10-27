"""서식 받기 점검: 서식 대장이나 떼어 낸 파일이 지금 원문과 어긋나면 받기 단추를 싣지 않는다.

  python3 scripts/test_forms.py
"""
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_forms  # noqa: E402
import build_web  # noqa: E402

FAIL = []


def ok(cond, msg):
    print(("✓ " if cond else "✗ ") + msg)
    if not cond:
        FAIL.append(msg)


rules = {r["name"]: r for r in json.loads(build_forms.RULES.read_text())["rules"]}
led = build_forms.load()
index = json.loads((build_web.FORMS / "index.json").read_text())["forms"]
names = lambda forms: [(f["rule"], f["no"]) for f in forms]  # noqa: E731

on = [(e["rule"], f["no"]) for e in led["rules"] for f in e["forms"] if f["download"]]
of = lambda forms, rule: [f for f in forms if f["rule"] == rule]  # noqa: E731
forms, warn = build_web.form_payload(rules, led, index)
ok(not build_forms.check(rules, led) and ("인사관리세칙", "8") in names(forms) and len(forms) >= 200 and not warn,
   f"지금 원문과 맞으면 받기를 켠 양식을 모두 싣는다({len(forms)}개 · 받기 켬 {len(on)}개 중 조문이 부르거나 이름이 하나뿐인 것)")

r2 = copy.deepcopy(rules)
r2["인사관리세칙"]["effective"] = "2099.01.01"
forms, warn = build_web.form_payload(r2, led, index)
ok(not of(forms, "인사관리세칙") and of(forms, "상벌세칙") and any("개정" in w for w in warn) and "인사관리세칙" in build_forms.check(r2, led),
   "내규가 개정되면(시행일이 바뀌면) 그 내규 양식만 서식 대장을 다시 맞출 때까지 싣지 않는다")

r3 = copy.deepcopy(rules)
a = next(x for x in r3["인사관리세칙"]["articles"] if x["no"] == "제31조")
a["paras"][0]["text"] = a["paras"][0]["text"].replace("별지 제8호 서식의 사직서", "별지 제9호 서식의 사직서")
forms, warn = build_web.form_payload(r3, led, index)
ok(not of(forms, "인사관리세칙") and any("문구" in w for w in warn), "조문이 부르는 문구('별지 제8호 서식의 사직서')가 원문에서 사라지면 그 내규 양식을 싣지 않는다")

i2 = copy.deepcopy(index)
i2["인사관리세칙/8"]["effective"] = "2025.01.01"
forms, warn = build_web.form_payload(rules, led, i2)
ok(("인사관리세칙", "8") not in names(forms) and ("인사관리세칙", "7") in names(forms) and any("떼어 낸" in w for w in warn),
   "떼어 낸 파일이 옛 원문에서 나온 것이면 그 양식만 싣지 않는다(node scripts/cut_forms.cjs 로 다시 떼기)")

forms, warn = build_web.form_payload(rules, led, {})
ok(not forms and any("떼어 낸" in w for w in warn), "떼어 낸 파일이 없으면 싣지 않는다")

# 조문이 부르는 이름과 서식 제목이 다르면(원문의 번호가 틀렸을 수 있음) 그 조문에는 양식 칸을 달지 않는다
forms, _ = build_web.form_payload(rules, led, index)
f4 = next((f for f in forms if f["rule"] == "정보공개운영세칙" and f["no"] == "4"), None)
c19 = [c for e in led["rules"] if e["rule"] == "정보공개운영세칙" for f in e["forms"] if f["no"] == "4" for c in f["calls"] if c["art"] == "제19조"]
ok(c19 and c19[0].get("mismatch") == "정보공개처리대장" and f4 and all(c["art"] != "제19조" for c in f4["calls"]),
   "정보공개운영세칙 제19조는 '별지 제4호 서식의 정보공개처리대장'이라 부르는데 별지 제4호는 '공개여부 결정기간 연장통지서'라 그 조문에는 달지 않음")
f8 = next(f for f in forms if f["rule"] == "인사관리세칙" and f["no"] == "8")
ok([c["art"] for c in f8["calls"]] == ["제31조"], "이름이 맞는 조문(인사관리세칙 제31조 '별지 제8호 서식의 사직서')에는 그대로 단다")

# 어느 조문도 부르지 않는 양식은 이름이 하나뿐일 때만 싣는다(이름으로 찾았을 때 띄우려고)
f12 = next((f for f in forms if f["rule"] == "인사관리세칙" and f["no"] == "12"), None)
ok(f12 and f12["calls"] == [] and f12["byName"] is True, "인사관리세칙 별지 제12호(신입직원 수습기간 평가표)처럼 부르는 조문이 없어도 이름이 하나뿐이면 싣는다")
l3 = copy.deepcopy(led)
g = next(f for e in l3["rules"] if e["rule"] == "인사관리세칙" for f in e["forms"] if f["no"] == "12")
g["title"] = "서약서"
forms3, _ = build_web.form_payload(rules, l3, index)
ok(("인사관리세칙", "12") not in names(forms3), "부르는 조문도 없고 이름도 겹치면(서약서) 싣지 않는다")

# 이름으로 띄우기: 물은 말·찾은 말에 양식 이름이 들어 있을 때 띄우는 것은 서식 대장 전체에서 이름이 하나뿐인 양식만
forms, _ = build_web.form_payload(rules, led, index)
l2 = copy.deepcopy(led)
l2["rules"].append({"rule": "가상규정", "code": "X", "basis": "", "forms": [{"no": "1", "label": "별지 제1호 서식", "seen": "사 직 서", "title": "사 직 서",
                                                                           "calls": [], "writer": "확인 전", "submit": "확인 전", "download": False}]})
r4 = dict(rules, 가상규정={"name": "가상규정", "code": "X", "effective": "", "articles": []})
forms2, _ = build_web.form_payload(r4, l2, index)
quit8 = lambda fs: next(f for f in fs if f["rule"] == "인사관리세칙" and f["no"] == "8")  # noqa: E731
ok(quit8(forms)["byName"] is True and quit8(forms2)["byName"] is False,
   "이름이 하나뿐인 양식(사직서)만 이름으로 띄우고, 다른 내규에 같은 이름(띄어쓰기 달라도)이 있으면 이름으로는 띄우지 않는다")

sys.exit(1 if FAIL else 0)
