"""ALIO 내규 확인 루틴의 판정. 표준 라이브러리와 alio_* 모듈만 쓴다(부 담당 PC에는 저장소가 없다)."""
import argparse
import datetime
import json
import os
import sys
import time
import traceback
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alio_report as RP  # noqa: E402
import alio_types as T  # noqa: E402
from alio_client import AlioError, default_http, fetch_attachments, fetch_file, fetch_list  # noqa: E402
from alio_pick import HANGUL, format_date, pick_bundle  # noqa: E402
from alio_release import attachment_files, bundle_digests, norm_title, same_as, values_of  # noqa: E402

KEYS = ("mod", "st_date", "file_no")


def _index(release):
    rules = release["rules"]
    by_idx = {r["idx"]: i for i, r in enumerate(rules) if r.get("idx")}
    by_name = {norm_title(r["name"]): i for i, r in enumerate(rules)}
    return rules, by_idx, by_name


def _find(row, rules, by_idx, by_name):
    i = by_idx.get(row["idx"])
    if i is None:
        i = by_name.get(norm_title(row["title"]))
    return i, (rules[i] if i is not None else None)


def _same_values(entry, values):
    return all(entry.get(k, "") == values[k] for k in KEYS)


def judge(rows, attachments, release, local_release, fetch_file, compare, mode):
    rules, by_idx, by_name = _index(release)
    local = _index(local_release) if local_release else None
    used, out = set(), []
    for row in rows:
        i, entry = _find(row, rules, by_idx, by_name)
        if i is not None:
            used.add(i)
        atts = attachments.get(row["idx"], [])
        values = values_of(row, atts)
        name = entry["name"] if entry else row["title"]
        f = T.Finding(name=name, code=entry["code"] if entry else "", idx=row["idx"], verdict=T.V_NONE,
                      title=row["title"], st_date=row["st_date"], mod=row["mod"], values=values)
        out.append(f)
        if entry and _same_values(entry, values):
            continue  # 파일을 받지 않는다
        bundle = pick_bundle(attachment_files(atts, fetch_file), row["st_date"])
        f.files = bundle.files
        if bundle.date:
            f.file_date = format_date(bundle.date)
        hangul = next((n for n, _ in bundle.files if n.lower().endswith(HANGUL)), "")
        f.ext = ("." + hangul.lower().rsplit(".", 1)[-1]) if hangul else (entry["ext"] if entry else "")
        if bundle.problems or bundle.date is None:
            f.verdict = T.V_CHECK
            f.notes = list(bundle.problems) or ["현행 묶음을 고르지 못했습니다"]
            continue
        if entry is None:
            f.verdict = T.V_NEW
            f.target_name = f"{name}{f.ext}"
            if mode == "full":
                f.compare = compare(name, "", bundle.files)
            continue
        f.target_name = f"{entry['code']}. {name}{f.ext}" if entry["code"] else f"{name}{f.ext}"
        if same_as(bundle_digests(bundle.files), entry["files"]):
            f.verdict = T.V_DONE
            continue
        if mode == "full" and local:
            _, lby_idx, lby_name = local
            _, lentry = _find(row, local[0], lby_idx, lby_name)
            if lentry and (same_as(bundle_digests(bundle.files), lentry["files"]) or _same_values(lentry, values)):
                f.verdict = T.V_PENDING
                f.notes = ["새 판을 올리면 끝남"]
                continue
        f.verdict = T.V_SUSPECT
        if entry.get("file_date") and entry["file_date"] == f.file_date:
            f.notes.append("날짜가 그대로라 재게시일 수 있음")
        if entry["ext"] and f.ext and f.ext != entry["ext"]:
            f.notes.append("형식이 달라 차이가 과장될 수 있음")
        if mode != "full":
            f.notes.append("정 담당 PC에서 비교")
            continue
        f.compare = compare(name, entry["code"], bundle.files)
        if f.compare.error:
            f.notes.append(f"비교하지 못함: {f.compare.error}")
        elif f.compare.whole_same:
            f.verdict = T.V_SAME_TEXT
        elif not f.compare.changed_units and not f.compare.added_units:
            f.verdict = T.V_OUTSIDE
    for i, entry in enumerate(rules):
        if i not in used and not (entry.get("confirmed") or {}).get("gone"):
            out.append(T.Finding(name=entry["name"], code=entry["code"], idx=entry["idx"], verdict=T.V_GONE,
                                 title=entry["name"], st_date=entry["st_date"], mod=entry["mod"]))
    return out


def check_sanity(rows, release):
    """받은 목록이 배포판의 절반 미만이면 중간에 끊긴 것으로 본다."""
    if len(rows) * 2 < len(release["rules"]):
        raise T.WatchFailure(f"받은 ALIO 목록이 {len(rows)}건뿐입니다(배포판 {len(release['rules'])}건)")


LOCK_SECONDS = 2 * 3600  # 이보다 오래된 잠금은 강제 종료로 남은 것으로 보고 무시한다
FALLBACK_NOTE = "배포판을 읽지 못해 이 PC의 마지막 빌드와 비교함"
CONFIG_KEYS = {"mode": "alert", "repo": "", "release_url": "", "release_path": "",
               "docs_dir": str(Path.home() / "Documents" / "내규챗봇 ALIO 확인")}


def monday_nine(now):
    """가장 최근 월요일 9시(지금이 월요일 9시 전이면 지난주 월요일)."""
    start = (now - datetime.timedelta(days=now.weekday())).replace(hour=9, minute=0, second=0, microsecond=0)
    return start if start <= now else start - datetime.timedelta(days=7)


def is_due(now, last_success):
    """가장 최근 월요일 9시 뒤에 성공한 기록이 없으면 돌 차례. 기록이 없거나 깨졌어도 돈다."""
    try:
        return datetime.datetime.fromisoformat(last_success) < monday_nine(now)
    except (TypeError, ValueError):
        return True


def acquire_lock(path, now=None):
    """잠금 파일을 만든다. 이미 있으면 False. 2시간 넘은 잠금은 지우고 다시 잡는다. 권한 오류 등은 OSError 로 나간다."""
    path = Path(path)
    now = time.time() if now is None else now
    for _ in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                if now - path.stat().st_mtime <= LOCK_SECONDS:
                    return False
                path.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                return False
            continue
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    return False


def release_lock(path):
    try:
        Path(path).unlink()
    except OSError:
        pass


def load_config(path):
    cfg = dict(CONFIG_KEYS)
    cfg.update(json.loads(Path(path).read_text(encoding="utf-8-sig")))
    if cfg["mode"] not in ("alert", "full"):
        raise ValueError(f"설정의 mode 는 alert 또는 full 이어야 합니다: {cfg['mode']}")
    return cfg


def _get_url(url):
    req = urllib.request.Request(url, headers={"User-Agent": "naegyu-alio-watch"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read()


def _parse_release(raw):
    data = json.loads(raw if isinstance(raw, str) else raw.decode("utf-8-sig"))
    if not isinstance(data, dict) or data.get("schema") != 1 or not isinstance(data.get("rules"), list) or not data["rules"]:
        raise ValueError("배포판 목록 형식이 맞지 않습니다")
    return data


def load_release(cfg, get_url=None):
    """(배포판 목록, 기준 안내). 주소를 먼저 읽고, 안 되면 설정의 파일을 읽는다. 둘 다 안 되면 WatchFailure."""
    get_url = get_url or _get_url
    url, path = cfg.get("release_url") or "", cfg.get("release_path") or ""
    errors = []
    if url:
        try:
            if not url.startswith("https://"):
                raise ValueError("release_url 은 https 주소여야 합니다")
            sep = "&" if "?" in url else "?"
            return _parse_release(get_url(f"{url}{sep}t={int(time.time())}")), ""
        except Exception as e:  # 못 읽으면 다음 곳으로
            errors.append(f"주소: {type(e).__name__}")
    if path:
        try:
            return _parse_release(Path(path).read_text(encoding="utf-8-sig")), (FALLBACK_NOTE if url else "")
        except Exception as e:
            errors.append(f"파일: {type(e).__name__}")
    raise T.WatchFailure("배포판 지문 목록을 읽지 못했습니다(" + ", ".join(errors or ["설정 없음"]) + ")")


def _read(path):
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _write(path, text):
    try:
        Path(path).write_text(text, encoding="utf-8")
    except OSError:
        pass


def _log(out_dir, now, text):
    try:
        with open(Path(out_dir) / "실행기록.log", "a", encoding="utf-8") as f:
            f.write(f"[{now.isoformat(timespec='seconds')}] {text}\n")
    except OSError:
        pass


def _ordered(findings):
    """알릴 판정을 위로, 같은 판정은 붙여서."""
    first = {}
    for f in findings:
        first.setdefault(f.verdict, len(first))
    return sorted(findings, key=lambda f: (f.verdict not in T.ATTENTION, first[f.verdict]))


def _default_compare(cfg):
    sys.path.insert(0, str(Path(cfg["repo"]) / "scripts"))
    from alio_compare import compare_rule  # 정 담당 PC에서만 있다
    return compare_rule


def _local_release(cfg):
    p = Path(cfg["repo"]) / "dist" / "release.json"
    try:
        return _parse_release(p.read_text(encoding="utf-8-sig")) if p.exists() else None
    except (OSError, ValueError):
        return None


def _collect(cfg, now, http, get_url, compare, today, last, out_dir):
    """ALIO 를 읽어 판정하고 대기 폴더·기록까지 남긴 뒤 (판정 목록, 결과 화면 설명)을 돌려준다."""
    http = http or default_http
    release, note = load_release(cfg, get_url)
    rows = fetch_list(http)
    check_sanity(rows, release)
    atts = {row["idx"]: fetch_attachments(row, http) for row in rows}  # 하나라도 실패하면 AlioError 로 전체 실패
    full = cfg["mode"] == "full"
    if full and compare is None:
        compare = _default_compare(cfg)
    findings = judge(rows, atts, release, _local_release(cfg) if full else None,
                     lambda n: fetch_file(n, http), compare, cfg["mode"])
    for f in findings:
        if f.files and f.verdict in T.ATTENTION:
            try:
                f.saved_dir = RP.save_bundle(out_dir / "대기", f)
            except OSError as e:
                f.notes.append(f"파일을 저장하지 못함({type(e).__name__}). 대기 폴더를 확인해 주세요.")
    first, history_error = RP.update_history(out_dir / "기록.csv", findings, today)
    for f in findings:
        if f.verdict in T.ATTENTION:
            f.days = RP.elapsed_days(f.mod, first.get(f.idx), today)
    meta = {"today": today, "last_success": last, "mode": cfg["mode"], "source_note": note, "history_error": history_error,
            "release_no": release.get("release_no", "?"), "release_built": release.get("built", "")}
    return _ordered(findings), meta


def run_watch(cfg, now, http=None, get_url=None, notify=None, open_page=None, compare=None, force=False):
    """한 번 돈다. 0 이면 정상(변동 없음·조용히 끝남 포함), 1 이면 확인 실패."""
    notify = notify or RP.notify
    open_page = open_page or RP.open_page
    out_dir = Path(cfg["docs_dir"])
    today = now.strftime("%Y-%m-%d")
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        notify("내규챗봇 ALIO 확인", "결과를 둘 폴더를 만들지 못했습니다")
        return 1
    lock = out_dir / ".lock"
    try:
        got_lock = acquire_lock(lock)
    except OSError as e:  # 잠금 파일을 만들 권한이 없으면 확인하지 못한 것이다
        _log(out_dir, now, f"잠금을 만들지 못함\n{traceback.format_exc()}")
        if _read(out_dir / ".last_fail_notice") != today:
            _write(out_dir / ".last_fail_notice", today)
            _safe(notify, "내규챗봇 ALIO 확인", f"확인 실패: 잠금 파일을 만들지 못했습니다({type(e).__name__})")
        return 1
    if not got_lock:
        return 0
    try:
        last = _read(out_dir / ".last_success")
        if not force and not is_due(now, last):
            return 0
        page = out_dir / "이번 주 결과.html"
        try:
            findings, meta = _collect(cfg, now, http, get_url, compare, today, last, out_dir)
            RP.write_outputs(out_dir, RP.render_html(findings, meta), findings, today)  # 못 쓰면 지난주 화면이 남으므로 실패로 본다
        except Exception as e:  # 접속 실패·형식 변화·그 밖의 모든 오류는 '확인 실패'
            _log(out_dir, now, "확인 실패\n" + traceback.format_exc())
            reason = str(e) or type(e).__name__
            try:
                RP.write_outputs(out_dir, RP.render_html([], {"today": today, "last_success": last, "mode": cfg.get("mode"), "failure": reason}), None, today)
            except OSError:
                pass
            if _read(out_dir / ".last_fail_notice") != today:  # 알림과 화면 열기는 하루 한 번(재시도는 막지 않음)
                _write(out_dir / ".last_fail_notice", today)
                _safe(notify, "내규챗봇 ALIO 확인", "확인 실패: " + reason)
                _safe(open_page, page)
            return 1
        _write(out_dir / ".last_success", now.isoformat(timespec="seconds"))
        attn = [f for f in findings if f.verdict in T.ATTENTION]
        if attn:
            names = ", ".join(dict.fromkeys(f.name for f in attn[:3]))
            more = f" 외 {len(attn) - 3}건" if len(attn) > 3 else ""
            _safe(notify, "내규챗봇 ALIO 확인", f"확인할 내규 {len(attn)}건: {names}{more}")
            _safe(open_page, page)
        else:
            _safe(notify, "내규챗봇 ALIO 확인", "이번 주 변동 없음")
        _log(out_dir, now, f"정상 종료(확인할 내규 {len(attn)}건)")
        return 0
    finally:
        release_lock(lock)


def _safe(fn, *args):
    """알림·화면 열기가 실패해도 실행은 계속한다."""
    try:
        fn(*args)
    except Exception:
        pass


def main(argv=None):
    ap = argparse.ArgumentParser(description="ALIO 내규 확인 (한 번 돌기)")
    ap.add_argument("--config", required=True)
    ap.add_argument("--force", action="store_true", help="이번 주에 이미 성공했어도 다시 확인")
    args = ap.parse_args(argv)
    now = datetime.datetime.now()
    try:
        cfg = load_config(args.config)
    except Exception as e:
        _log(Path(args.config).resolve().parent, now, "설정을 읽지 못함\n" + traceback.format_exc())
        _safe(RP.notify, "내규챗봇 ALIO 확인", f"설정 파일을 읽지 못했습니다: {type(e).__name__}")
        return 1
    return run_watch(cfg, now, force=args.force)


if __name__ == "__main__":
    sys.exit(main())
