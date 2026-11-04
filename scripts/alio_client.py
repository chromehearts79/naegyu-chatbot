"""ALIO 공개 사이트에서 내규 목록·첨부 목록·첨부 파일을 받는다. 표준 라이브러리만 쓴다.

실패는 모두 AlioError 로 올린다. 읽기 요청만 보내며 개인 정보는 싣지 않는다.
"""
import html as htmllib
import http.client
import json
import re
import time
import urllib.parse
from urllib.request import Request, urlopen

BASE = "https://www.alio.go.kr"
APBA_ID = "C0352"
REPORT_FORM = "21110"
TIMEOUT = 15
TRIES = 3
RETRY_SLEEP = 0.5  # 다시 시도 사이 쉬는 시간(초)
DELAY = 0.06  # 요청 사이 쉬는 시간(초). 사이트에 부담을 주지 않으려는 것
MAX_PAGES = 50

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Referer": f"{BASE}/item/itemOrganList.do?reportFormRootNo={REPORT_FORM}",
    "Origin": BASE,
}

LINK_RE = re.compile(r'<a\b[^>]*href="[^"]*rulefiledown\.json\?fileNo=(\d+)"[^>]*>([^<]*)</a>')
PREVIEW_RE = re.compile(r"previewAjax\(\s*'(\d+)'\s*,\s*'([^']*)'")
TRACE_RE = re.compile(r"fileNo=\d+|downRuleFile\(")


class AlioError(Exception):
    pass


def default_http(path, body):
    """(응답 내용, Content-Type). body 가 있으면 JSON POST, 없으면 GET. 15초 제한, 3번 시도."""
    headers = dict(HEADERS)
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=UTF-8"
    last = None
    for i in range(TRIES):
        if i:
            time.sleep(RETRY_SLEEP)
        try:
            req = Request(BASE + path, data=data, headers=headers, method="POST" if data is not None else "GET")
            with urlopen(req, timeout=TIMEOUT) as r:
                return r.read(), r.headers.get("Content-Type", "") or ""
        except (OSError, http.client.HTTPException) as e:  # URLError·HTTPError·시간 초과 포함
            last = e
    raise AlioError(f"ALIO 접속 실패({path}): {last}")


def fetch_list(http=default_http):
    rows, total, page, total_page = [], None, 1, 1
    while page <= total_page:
        if page > 1:
            time.sleep(DELAY)
        body = {"pageNo": page, "apbaId": APBA_ID, "apbaType": "A2004", "reportFormRootNo": REPORT_FORM,
                "search_word": "", "search_flag": "title", "bid_type": "", "enfc_istt": ""}
        raw, _ = http("/item/itemReportListSusi.json", body)
        try:
            data = json.loads(raw.decode("utf-8"))["data"]
            result = data["result"]
            meta = data.get("page") or {}
            total_page = int(meta.get("totalPage") or 1)
            total = int(meta["totalCount"]) if meta.get("totalCount") is not None else None
        except (ValueError, KeyError, TypeError, AttributeError) as e:
            raise AlioError(f"목록 응답을 읽지 못했다: {e}") from e
        if not isinstance(result, list):
            raise AlioError("목록 응답의 data.result 가 목록이 아니다")
        for r in result:
            rows.append({
                "idx": str(r.get("idx", "")),
                "title": (r.get("title") or "").strip(),
                "st_date": r.get("stDate") or "",
                "mod": r.get("idate") or "",
                "category": r.get("bidType") or "",
                "table_name": r.get("tableName") or "",
                "idx_name": r.get("idxName") or "",
            })
        if total_page > MAX_PAGES:
            raise AlioError(f"목록 쪽 수가 너무 많다({total_page})")
        page += 1
    if total is not None and len(rows) < total:
        raise AlioError(f"목록을 다 받지 못했다({len(rows)}/{total})")
    return rows


def fetch_attachments(row, http=default_http):
    q = urllib.parse.urlencode({
        "disclosureNo": "null", "apbaId": APBA_ID, "nowcode": REPORT_FORM, "reportFormNo": REPORT_FORM,
        "table_name": row.get("table_name") or "COMM_RULE", "idx_name": row.get("idx_name") or "RULE_NO",
        "idx": row["idx"], "reportGbn": "N", "bid_type": row.get("category") or "",
    })
    raw, _ = http("/item/itemBoard21110.do?" + q, None)
    text = raw.decode("utf-8", "replace")
    found, seen = [], set()
    for m in list(LINK_RE.finditer(text)) + list(PREVIEW_RE.finditer(text)):
        no, name = m.group(1), htmllib.unescape(m.group(2)).strip()
        if no not in seen:
            seen.add(no)
            found.append({"file_no": no, "name": name})
    if not found and TRACE_RE.search(text):
        raise AlioError(f"첨부 흔적은 있으나 목록을 읽지 못했다(idx {row['idx']}). 사이트가 바뀌었을 수 있다")
    return found


def fetch_file(file_no, http=default_http):
    time.sleep(DELAY)
    raw, ctype = http("/download/rulefiledown.json?fileNo=" + urllib.parse.quote(str(file_no)), None)
    low = ctype.lower()
    if "text/html" in low or "application/json" in low:
        raise AlioError(f"파일 대신 웹 페이지가 왔다(fileNo {file_no})")
    return raw
