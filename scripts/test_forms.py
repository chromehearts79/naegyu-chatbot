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
import check_forms  # noqa: E402

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
# 이름이 겹쳐도 그 양식들이 모두 같은 종이(원문 별지 글이 같음)면 어느 쪽을 받아도 같아 이름으로 띄운다
at = lambda rule, no: next((f for f in forms if f["rule"] == rule and f["no"] == no), None)  # noqa: E731
sg = [at("평가세칙", "3"), at("전임전문직원관리세칙", "1")]
ok(all(f and f["byName"] is True and f["calls"] == [] for f in sg),
   "부르는 조문이 없고 이름이 겹쳐도 같은 종이면(연봉등급 승급 평가표: 평가세칙 별지 제3호·전임전문직원관리세칙 별지 제1호) 둘 다 싣고 이름으로 띄운다")

# 법령 이름 뒤에 나온 별지라도 이 내규 끝에 그 번호 별지가 있으면 내규 별지로 보고 그 조문에 양식 칸을 단다
seven = [("채용업무관리세칙", "4", "제6조"), ("개인정보보호세칙", "1", "제47조"), ("정보공개운영세칙", "10", "제18조"), ("정보공개운영세칙", "16", "제28조"),
         ("법무업무처리지침", "1", "제13조"), ("법무업무처리지침", "2", "제14조"), ("공익신고 처리 및 신고자 보호 운영지침", "9", "제19조")]
miss = [f"{r} {art}" for r, no, art in seven if not (at(r, no) and any(c["art"] == art for c in at(r, no)["calls"]))]
ok(not miss and not any(c.get("outside") for e in led["rules"] for f in e["forms"] for c in f["calls"]),
   "법령 이름 뒤에 나오지만 내규 끝에 그 번호 별지가 있는 7곳(법무업무처리지침 제13조 '별지 제1호 서식의 의뢰서' 등)에도 양식 칸을 단다"
   + (": 빠짐 " + ", ".join(miss) if miss else ""))

# 떼어 낸 양식 검사(check_forms): 떼어 낸 파일을 다시 읽은 글을 원본 변환본의 그 별지 부분과 맞댄다
orig = "[별지 제8호 서식]\n\n사 직 서\n소 속 :\n직 위 :\n성 명 :\n위 본인은 아래와 같이 사직서를 제출합니다.\n□ 사직일자 : 20 년 월 일\n□ 사 유 :\n신청인 인\n우체국금융개발원장 귀하"
ok(check_forms.compare(orig, orig, "8")[0], "검사: 원본 별지 부분과 같으면 통과")
ok(check_forms.compare(orig, "인사관리세칙\n\n![image](images/x/image_001.png)\n\n" + orig.replace("사 직 서", "**사 직 서**"), "8")[0],
   "검사: 원본에 없던 로고 그림 줄·머리말(내규 이름)·굵은 글씨 표시만 다르면 통과")
moved = orig.replace("\n신청인 인", "") .replace("소 속 :", "신청인 인\n소 속 :")
ok(check_forms.compare(orig, moved, "8")[0], "검사: 글자는 같고 한 줄을 읽어 낸 차례만 다르면 통과(동호회운영지침 별지 제6호의 '※ 붙임서류' 줄)")
ok(not check_forms.compare(orig, orig.replace("제8호", "제9호"), "8")[0], "검사: 첫 별지 표시가 다른 번호면 실패")
ok(not check_forms.compare(orig, orig + "\n\n[별지 제9호 서식]\n\n인사기록 변경신청서\n소 속 :", "8")[0], "검사: 다음 양식의 별지 표시가 섞이면 실패")
ok(not check_forms.compare(orig, orig[:60], "8")[0], "검사: 양식 글이 절반쯤 빠지면 실패")

# 바깥 별지(법령·다른 규정의 별지)는 내규 끝에 그 번호 별지가 없을 때만. '법률자문'의 '법률'처럼 법령 이름이 아닌 말 뒤도 내규 별지
law = {"articles": [
    {"no": "제28조", "text": "", "paras": [{"no": 0, "text": "원장은 「공공기관의 정보공개에 관한 법률 시행규칙」 제9조에 의하여 별지 제16호 서식의 정보공개 운영실태를 작성하여"}]},
    {"no": "제14조", "text": "", "paras": [{"no": 2, "text": "② 법률자문 평가는 별지 제2호 서식에 따라 실시한다."}]},
    {"no": "제58조", "text": "", "paras": [{"no": 1, "text": "「산업안전보건법 시행규칙」 별지 제30호에 따른 서류를 낸다."}]}]}
lc = build_forms.form_calls(law)
moved = build_forms.own_forms(lc, ["2", "16"])
ok(not lc["16"][0].get("outside") and not lc["2"][0].get("outside") and lc["30"][0].get("outside") and sorted(n for n, _ in moved) == ["16", "2"],
   "법령 이름 뒤 별지라도 내규 끝에 그 번호가 있으면 내규 별지(별지 제16호·제2호), 없으면 바깥 별지(별지 제30호)")

sys.exit(1 if FAIL else 0)
