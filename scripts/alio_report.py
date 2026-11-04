"""ALIO 확인 결과를 화면·기록·알림으로 남긴다. 표준 라이브러리와 alio_types만 쓴다."""
import csv
import dataclasses
import datetime
import html
import json
import os
import platform
import re
import subprocess
import webbrowser
from pathlib import Path

from alio_types import ATTENTION, V_DONE, V_NEW, V_SAME_TEXT, V_SUSPECT, Finding

LATE_DAYS = 14  # 이 날수가 지나도 해소되지 않으면 빨간 표시
HISTORY_HEAD = ["내규", "idx", "판정", "처음 잡힌 날", "해소된 날"]


def safe_name(s: str, limit: int = 80) -> str:
    """윈도우 경로에 못 쓰는 글자를 _ 로 바꾸고 길이를 줄인다."""
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", s)
    return s[:limit].rstrip(". ")


def save_bundle(wait_dir: Path, finding: Finding) -> str:
    """받은 현행 묶음을 대기\\<내규명>_<파일 날짜>\\ 에 저장하고 그 폴더 경로를 돌려준다."""
    digits = re.sub(r"\D", "", finding.file_date)
    folder = Path(wait_dir) / safe_name(f"{finding.name}_{digits}" if digits else finding.name, 60)
    folder.mkdir(parents=True, exist_ok=True)
    used = set()
    for fname, data in finding.files:
        base = re.split(r"[\\/]", fname)[-1]  # ZIP 안 경로는 파일 이름만 쓴다
        stem, dot, ext = base.rpartition(".")
        if not dot:
            stem, ext = base, ""
        ext = safe_name(ext, 8)
        stem = safe_name(stem, 60)
        if not stem:  # 폴더 이름만 있는 ZIP 항목 등
            continue
        suffix = "." + ext if ext else ""
        target, n = folder / (stem + suffix), 1
        while target in used:  # 같은 이름이 겹치면 (2), (3) 을 붙여 덮어쓰지 않는다
            n += 1
            target = folder / f"{stem} ({n}){suffix}"
        used.add(target)
        target.write_bytes(data)
    return str(folder)


def _ymd(s):
    """'2026.10.20'·'2026-11-09' 같은 글자에서 날짜를 읽는다. 못 읽으면 None."""
    m = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", s or "")
    if not m:
        return None
    try:
        return datetime.date(*(int(x) for x in m.groups()))
    except ValueError:
        return None


def elapsed_days(mod: str, first_seen: str | None, today: str) -> int:
    """게시일과 처음 잡은 날 중 이른 날부터 오늘까지 며칠인지."""
    days = [d for d in (_ymd(mod), _ymd(first_seen)) if d]
    now = _ymd(today)
    if not days or not now:
        return 0
    return max((now - min(days)).days, 0)


def update_history(csv_path: Path, findings: list, today: str):
    """기록.csv 에 처음 잡힌 날·해소된 날을 적는다. 쓸 수 없으면 (빈 값, 사유)로 끝낸다."""
    try:
        rows = []
        if Path(csv_path).exists():
            with open(csv_path, encoding="utf-8-sig", newline="") as f:
                rows = [r for r in csv.DictReader(f)]
        now = {f.idx: f for f in findings if f.verdict in ATTENTION}
        for r in rows:
            if r["해소된 날"]:
                continue
            f = now.pop(r["idx"], None)
            if f is None:
                r["해소된 날"] = today
            else:
                r["판정"] = f.verdict
        for idx, f in now.items():
            rows.append({"내규": f.name, "idx": idx, "판정": f.verdict, "처음 잡힌 날": today, "해소된 날": ""})
        first = {r["idx"]: r["처음 잡힌 날"] for r in rows if not r["해소된 날"]}
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=HISTORY_HEAD)
            w.writeheader()
            w.writerows(rows)
        return first, None
    except Exception as e:  # 엑셀로 열어 둔 경우 등. 결과 화면은 그대로 낸다
        return {}, f"기록.csv를 쓰지 못했습니다({type(e).__name__}). 엑셀을 닫고 다시 돌려 주세요."


STYLE = """
body{font-family:'Malgun Gothic','Apple SD Gothic Neo',sans-serif;margin:24px;color:#222}
h1{font-size:22px} .top{color:#555} .warn{background:#fff3cd;padding:8px 12px;margin:8px 0}
.fail{background:#fde2e2;padding:12px;margin:12px 0;font-weight:bold}
table{border-collapse:collapse;width:100%;margin:12px 0} th,td{border:1px solid #ccc;padding:6px 8px;vertical-align:top;text-align:left;font-size:14px}
th{background:#f2f2f2} tr.late td{background:#fde2e2} .red{color:#c00;font-weight:bold} small{color:#666}
"""


def _e(x):
    return html.escape(str(x))


def _compare_html(f, mode):
    c = f.compare
    out = []
    if mode != "full" and f.verdict in (V_SUSPECT, V_NEW) and c is None:
        out.append("정 담당 PC에서 비교")
    if c is not None:
        if f.verdict == V_NEW:
            n = sum(1 for u in c.added_units if str(u).startswith("제"))
            out.append(f"조문 {n}개")
        if c.changed_units:
            out.append("바뀐 곳: " + ", ".join(_e(u) for u in c.changed_units))
        if c.stale_cards:
            out.append(f"다시 확인할 문답 {len(c.stale_cards)}장")
        if c.related_cards:
            out.append(f"참고 문답 {len(c.related_cards)}장")
        if c.calcs:
            out.append("계산기: " + ", ".join(_e(x) for x in c.calcs))
        for u, a, b in c.before_after[:5]:
            out.append(f"<small>{_e(u)}<br>이전: {_e(str(a)[:300])}<br>이후: {_e(str(b)[:300])}</small>")
        if c.outside_diff:
            out.append("조문 밖 달라진 글자: " + "; ".join(_e(str(x)[:200]) for x in c.outside_diff[:5]))
        if c.error:
            out.append(f"<small>비교하지 못했습니다: {_e(c.error)}</small>")
    out += [f"<small>{_e(n)}</small>" for n in f.notes]
    return "<br>".join(out)


def render_html(findings: list, meta: dict) -> str:
    """쉬운 말로 된 한 장짜리 결과 화면(외부 자원 없음)."""
    today, last = meta.get("today", ""), meta.get("last_success")
    if last and _ymd(last) and _ymd(today):
        ago = f"마지막 확인: {(_ymd(today) - _ymd(last)).days}일 전({_e(last)})"
    else:
        ago = "처음 확인"
    parts = [f"<!doctype html><html lang='ko'><head><meta charset='utf-8'><title>내규챗봇 ALIO 확인</title><style>{STYLE}</style></head><body>",
             f"<h1>내규챗봇 ALIO 확인 {_e(today)}</h1>",
             f"<p class='top'>{ago} · 배포판 제{_e(meta.get('release_no', '?'))}판({_e(meta.get('release_built', ''))})</p>"]
    for key in ("source_note", "history_error"):
        if meta.get(key):
            parts.append(f"<div class='warn'>{_e(meta[key])}</div>")
    if meta.get("failure"):
        parts.append(f"<div class='fail'>확인 실패: {_e(meta['failure'])}<br>이번에는 변동 여부를 알 수 없습니다. 다음 실행 때 다시 확인합니다.</div>")
    attn = [f for f in findings if f.verdict in ATTENTION]
    if not attn and not meta.get("failure"):
        parts.append("<h2>이번 주 변동 없음</h2>")
    if attn:
        parts.append("<h2>확인할 내규</h2><table><tr><th>내규</th><th>목록 날짜</th><th>게시일</th><th>경과일</th><th>판정</th><th>비교 결과</th><th>받은 파일 위치</th><th>원본 폴더에 넣을 이름</th></tr>")
        for f in attn:
            late = f.days is not None and f.days >= LATE_DAYS
            days = "-" if f.days is None else f"{f.days}일"
            if late:
                days = f"<span class='red'>{days}</span><br>정 담당 확인, 부재면 게시판에 미반영 공지"
            tr = '<tr class="late">' if late else "<tr>"
            parts.append(f"{tr}<td>{_e(f.name)}<br><small>{_e(f.code)}</small></td><td>{_e(f.st_date)}</td><td>{_e(f.mod)}</td>"
                         f"<td>{days}</td><td>{_e(f.verdict)}</td><td>{_compare_html(f, meta.get('mode'))}</td><td>{_e(f.saved_dir)}</td><td>{_e(f.target_name)}</td></tr>")
        parts.append("</table>")
    counts = [(v, sum(1 for f in findings if f.verdict == v)) for v in (V_DONE, V_SAME_TEXT)]
    counts = [f"{v} {n}건" for v, n in counts if n]
    if counts:
        parts.append("<p>" + " · ".join(counts) + " (알릴 일 없음)</p>")
    parts.append("</body></html>")
    return "".join(parts)


def write_outputs(out_dir: Path, html_text: str, findings: list, today: str) -> None:
    """이번 주 결과, 기록\\날짜.html 보관본, 최근 결과.json 을 쓴다."""
    out_dir = Path(out_dir)
    (out_dir / "기록").mkdir(parents=True, exist_ok=True)
    (out_dir / "이번 주 결과.html").write_text(html_text, encoding="utf-8")
    (out_dir / "기록" / f"{today}.html").write_text(html_text, encoding="utf-8")
    rows = []
    for f in findings:
        d = dataclasses.asdict(f)
        d.pop("files", None)  # 받은 파일 내용은 넣지 않는다
        rows.append(d)
    (out_dir / "최근 결과.json").write_text(json.dumps({"today": today, "findings": rows}, ensure_ascii=False, indent=1), encoding="utf-8")


# 글자는 환경 변수로 받아 명령줄 따옴표 문제를 피한다
TOAST_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$t = [System.Security.SecurityElement]::Escape($env:NAEGYU_TOAST_TITLE)
$b = [System.Security.SecurityElement]::Escape($env:NAEGYU_TOAST_BODY)
$x = New-Object Windows.Data.Xml.Dom.XmlDocument
$x.LoadXml("<toast><visual><binding template='ToastGeneric'><text>$t</text><text>$b</text></binding></visual></toast>")
$n = New-Object Windows.UI.Notifications.ToastNotification $x
$id = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($id).Show($n)
"""


def notify(title: str, body: str, run=subprocess.run, system: str | None = None) -> bool:
    """윈도우 기본 알림을 띄운다. 윈도우가 아니거나 실패하면 False(예외 없음)."""
    if (system or platform.system()) != "Windows":
        return False
    try:
        run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", TOAST_SCRIPT],
            env={**os.environ, "NAEGYU_TOAST_TITLE": title, "NAEGYU_TOAST_BODY": body},
            check=True, timeout=30, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return True
    except Exception:
        return False


def open_page(path: Path) -> None:
    webbrowser.open(Path(path).resolve().as_uri())
