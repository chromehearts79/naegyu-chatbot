"""ALIO 내규 확인 루틴 설치 (윈도우 작업 스케줄러 등록).

  python -X utf8 scripts/install_watch.py --mode full --repo C:\\내규챗봇          (정 담당 PC)
  python -X utf8 install_watch.py --mode alert --url https://.../release.json      (부 담당 PC)
  python -X utf8 scripts/install_watch.py --pack 부담당.zip                        (부 담당용 묶음 만들기)

--dry-run 이면 파일만 쓰고 작업 스케줄러에는 등록하지 않는다. 표준 라이브러리만 쓴다.
"""
import argparse
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

TASK_NAME = "내규챗봇 ALIO 확인"
HERE = Path(__file__).resolve().parent
PACK_MODULES = ("alio_types", "alio_client", "alio_pick", "alio_release", "alio_report", "watch_alio", "install_watch")
NS = "http://schemas.microsoft.com/windows/2004/02/mit/task"


def python_exe():
    """창 없이 도는 pythonw.exe 가 같은 폴더에 있으면 그것을 쓴다."""
    w = Path(sys.executable).with_name("pythonw.exe")
    return str(w) if w.exists() else sys.executable


def task_xml(python_exe: str, script: str, config: str, start: str = "2026-01-05T09:00:00", user: str = "") -> str:
    """매주 월요일 9시와 로그인 때 도는 작업. 로그인해 있을 때만 돈다(알림과 화면을 띄우므로)."""
    who = f"<UserId>{escape(user)}</UserId>" if user else ""
    args = f'-X utf8 "{script}" --config "{config}"'
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="{NS}">
  <RegistrationInfo><Description>ALIO 내규 확인 (매주 월요일 9시, 로그인할 때)</Description></RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>{escape(start)}</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByWeek><WeeksInterval>1</WeeksInterval><DaysOfWeek><Monday /></DaysOfWeek></ScheduleByWeek>
    </CalendarTrigger>
    <LogonTrigger>
      <Enabled>true</Enabled>
      {who}
    </LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      {who}
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <AllowHardTerminate>true</AllowHardTerminate>
    <Enabled>true</Enabled>
    <ExecutionTimeLimit>PT1H</ExecutionTimeLimit>
    <RestartOnFailure><Interval>PT1H</Interval><Count>3</Count></RestartOnFailure>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{escape(python_exe)}</Command>
      <Arguments>{escape(args)}</Arguments>
    </Exec>
  </Actions>
</Task>
"""


def confirm_bat(python_exe: str, script: str, config: str) -> str:
    """담당자가 더블클릭으로 '확인함'을 돌리는 파일. 한글 경로를 위해 코드 페이지와 utf8을 맞춘다."""
    return f'@echo off\r\nchcp 65001 > nul\r\n"{python_exe}" -X utf8 "{script}" --config "{config}"\r\npause\r\n'


def pack(out: Path) -> list[str]:
    """부 담당 PC용 ZIP. 저장소 없이 돌아가는 파일만 담는다."""
    names = [f"{m}.py" for m in PACK_MODULES]
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for n in names:
            z.write(HERE / n, n)
    return names


def _utf16(path: Path, text: str):
    path.write_bytes(b"\xff\xfe" + text.encode("utf-16-le"))


def install(mode, repo, url, path, docs_dir, dry_run=False) -> dict:
    if sys.version_info < (3, 11):
        raise SystemExit("파이썬 3.11 이상이 필요합니다.")
    docs = Path(docs_dir) if docs_dir else Path.home() / "Documents" / "내규챗봇 ALIO 확인"
    repo = str(repo or "")
    path = str(path or "")
    url = url or ""
    if mode == "full":  # 설치해 놓고 매번 실패하지 않도록 아무것도 쓰기 전에 막는다
        if not repo:
            raise SystemExit("정 담당 PC 설치에는 --repo 가 필요합니다.")
        path = path or str(Path(repo) / "dist" / "release.json")
        if not Path(path).is_file():
            raise SystemExit(f"배포판 목록({path})이 없습니다. 먼저 python -X utf8 scripts/alio_release.py refresh 를 돌리세요.")
    elif not url and not path:
        raise SystemExit("부 담당 PC 설치에는 --url(배포판 목록 주소) 또는 --path(목록 파일)가 필요합니다.")
    docs.mkdir(parents=True, exist_ok=True)
    cfg = {"mode": mode, "repo": repo, "release_url": url, "release_path": path, "docs_dir": str(docs)}
    cfg_file = docs / "config.json"
    cfg_file.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    exe = python_exe()
    watch = str(HERE / "watch_alio.py")
    user = os.environ.get("USERNAME", "")
    if user and os.environ.get("USERDOMAIN"):
        user = os.environ["USERDOMAIN"] + "\\" + user
    xml_file = docs / f"{TASK_NAME}.xml"
    _utf16(xml_file, task_xml(exe, watch, str(cfg_file), user=user))
    out = {"config": str(cfg_file), "xml": str(xml_file), "registered": False}
    if mode == "full":
        bat = docs / "확인함.bat"
        console = str(Path(sys.executable).with_name("python.exe")) if os.name == "nt" else sys.executable  # 글을 묻는 창이므로 pythonw 는 안 된다
        bat.write_bytes(confirm_bat(console, str(HERE / "alio_confirm.py"), str(cfg_file)).encode("utf-8"))
        out["bat"] = str(bat)
    if not dry_run and os.name == "nt":
        r = subprocess.run(["schtasks", "/create", "/tn", TASK_NAME, "/xml", str(xml_file), "/f"], capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit("작업 스케줄러 등록 실패: " + (r.stderr or r.stdout).strip())
        out["registered"] = True
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="ALIO 내규 확인 설치")
    ap.add_argument("--mode", choices=("full", "alert"))
    ap.add_argument("--repo", default="")
    ap.add_argument("--url", default="")
    ap.add_argument("--path", default="", help="배포판 목록 파일(기본: <repo>/dist/release.json)")
    ap.add_argument("--docs", default="")
    ap.add_argument("--dry-run", action="store_true", help="파일만 쓰고 등록하지 않음")
    ap.add_argument("--pack", metavar="ZIP", help="부 담당 PC용 묶음 만들기")
    a = ap.parse_args(argv)
    if a.pack:
        names = pack(Path(a.pack))
        print(f"{a.pack}: {len(names)}개 파일")
        return 0
    if not a.mode:
        ap.error("--mode 또는 --pack 이 필요합니다")
    r = install(a.mode, a.repo, a.url, a.path, a.docs, a.dry_run)
    print("설정:", r["config"])
    print("작업 파일:", r["xml"])
    print("작업 스케줄러에 등록함" if r["registered"] else "등록은 하지 않았습니다(미리 보기이거나 윈도우가 아님)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
