# 규정 개정 감지 결과

카드 확인 기준(지문) 2026-10-21 · 비교한 규정 원본 rules.json

- 바뀌거나 없어진 조문·별표·부칙: 0개
- 다시 확인해야 할 카드: **0장** (인용한 조·항이 바뀜)
- 참고할 카드: 0장 (같은 조의 다른 항만 바뀜)
- 새로 생긴 조문·별표(카드가 없을 수 있음): 0개
- 새 부칙(개정 이력): 0개

## 처리 순서

1. 위 카드의 답·근거를 새 원문에 맞게 고친다(`python3 scripts/show_rule.py <규정명>`).
2. `python3 scripts/check_knowledge.py` 오류 0건, `python3 scripts/blind_check.py <카드 id…>` 로 다시 검증.
3. 그 규정의 카드를 다 확인했으면 `python3 scripts/check_changes.py --accept <규정명>`.
4. `python3 scripts/build_web.py` 로 다시 묶는다. 확인 전 카드는 화면에 '규정 개정 · 재검수 전'으로 표시된다.
