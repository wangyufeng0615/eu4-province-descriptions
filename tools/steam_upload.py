"""把已构建好的版本上传到本模组已有的工坊条目，经由已登录的 Windows Steam 客户端。

python -B tools/steam_upload.py 1.0.1 --output dist/upload-1.0.1-check.json      # 只做本地核对，不连 Steam（SSH 里也能跑）
python -B tools/steam_upload.py 1.0.1 --upload --notes-file workshop/changenotes.en.txt --output dist/upload-1.0.1.json
                                                                                 # 在登录了 Steam 的桌面会话里运行

只用于更新已有条目（project.json 的 publishedfileid）；第一次建条目由作者在游戏的上传工具里做。
上传前后比对标题、描述、可见性、封面和截图，有任何变化就报错。记录文件不覆盖。改自 EU5 地块发布工程的同名工具。
"""
from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path
import re
import traceback

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def check_release(root: Path, version: str):
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ValueError("Version must be x.y.z")
    project = json.loads((root / "project.json").read_text(encoding="utf-8"))
    if project["version"] != version:
        raise ValueError("Requested version differs from project.json")
    output = root / "dist" / f"release-{version}"
    receipt = build.verify(root, output)
    name = build.mod_folder_name(build.load_config(root))
    folder = (output / name).resolve()
    if output.is_symlink() or (output / name).is_symlink():
        raise ValueError("Release directories must not be symlinks")
    return folder, receipt


def perform_upload(steam, folder, notes, record, save):
    # Import bindings only on the explicitly requested upload path.
    from steam_page import APP, ITEM, U64, U32, S, B
    record["before"] = {lang: steam.query(lang) for lang in ("english", "schinese")}
    # query() validates the item, game and signed-in owner before any write.
    save()
    handle = steam.ug("StartItemUpdate", U64, [U32, U64], APP, ITEM)
    if not handle or not steam.ug("SetItemContent", B, [U64, S], handle, str(folder).encode()):
        raise RuntimeError("Steam did not accept the content folder")
    record["submission_started"] = True
    save()
    record["result"] = steam.submit(handle, notes)
    record["after"] = {lang: steam.query(lang) for lang in ("english", "schinese")}
    for lang in record["before"]:
        for key in ("title", "description", "visibility", "cover", "previews"):
            if record["before"][lang][key] != record["after"][lang][key]:
                raise RuntimeError(f"Unexpected page change: {lang}/{key}")
    record["metadata_unchanged"] = True
    record["completed_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    save()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version")
    parser.add_argument("--upload", action="store_true")
    parser.add_argument("--notes-file", type=Path)
    parser.add_argument("--output", type=Path, required=True, help="New JSON evidence file; never overwritten")
    args = parser.parse_args()
    if args.upload and not args.notes_file:
        parser.error("--upload requires --notes-file")
    if args.output.exists():
        raise FileExistsError(args.output)
    folder, receipt = check_release(ROOT, args.version)
    notes = args.notes_file.read_text(encoding="utf-8-sig").strip() if args.notes_file else ""
    if args.upload and (not notes or notes.splitlines()[0].strip() != args.version):
        raise ValueError("Change notes must start with the requested version")
    record = {"version": args.version, "folder": str(folder), "local_checks_passed": True,
              "files": receipt["files"], "archive_sha256": receipt["archive_sha256"],
              "bytes": sum((folder / name).stat().st_size for name in receipt["files"]),
              "upload_requested": args.upload, "submission_started": False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation also prevents accidental reuse after an uncertain upload.
    with args.output.open("x", encoding="utf-8") as out:
        json.dump(record, out, ensure_ascii=False, indent=2)
    def save():
        args.output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.upload:
        from steam_page import Steam
        steam = None
        try:
            steam = Steam()
            perform_upload(steam, folder, notes, record, save)
        except BaseException:
            record["error"] = traceback.format_exc()
            save()
            raise
        finally:
            if steam is not None:
                steam.bind("SteamAPI_Shutdown", None)()
    print(json.dumps({key: value for key, value in record.items() if key not in ("files", "before", "after")}, indent=2))


if __name__ == "__main__":
    main()
