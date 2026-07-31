#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""รวมผลงานสแกนเป็นชุดพร้อมส่งขึ้น Google Drive

สคริปต์นี้ไม่ได้อัปโหลดเอง — เครื่องที่สองอัปโหลดผ่านเครื่องมือ Google Drive
ของ Claude สคริปต์จึงทำหน้าที่รวบรวมไฟล์และสร้าง manifest.json ให้ Claude
อ่านแล้วอัปโหลดต่อ

ใช้:
    python3 scan/deliver.py                # รวมผลงานทั้งหมดใน scan_text
    python3 scan/deliver.py --since 20260731   # เฉพาะงานตั้งแต่วันที่ระบุ
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(os.environ.get("BOOK_SCAN_ROOT", Path(__file__).resolve().parent.parent / "work"))
TEXT = ROOT / "scan_text"
DELIVERY = Path(__file__).resolve().parent.parent / "delivery"

# ไฟล์ใหญ่กว่านี้ไม่ฝัง base64 ลง manifest (ตัวจัดการอัปโหลดจะรับไม่ไหว)
INLINE_LIMIT = 6 * 1024 * 1024


def collect(since: str | None) -> list[Path]:
    if not TEXT.exists():
        return []
    files = [p for p in sorted(TEXT.iterdir()) if p.is_file()]
    if since:
        files = [p for p in files if p.name >= since]
    return files


def build(since: str | None) -> dict:
    DELIVERY.mkdir(parents=True, exist_ok=True)
    entries: list[dict] = []

    for path in collect(since):
        target = DELIVERY / path.name
        shutil.copy2(path, target)
        size = target.stat().st_size
        entry: dict = {
            "name": path.name,
            "path": str(target),
            "size": size,
            "mime": "text/plain" if path.suffix == ".txt"
            else "application/json" if path.suffix == ".json"
            else "application/pdf" if path.suffix == ".pdf"
            else "application/octet-stream",
            "inline": size <= INLINE_LIMIT,
        }
        if entry["inline"]:
            if path.suffix in {".txt", ".json"}:
                entry["text"] = target.read_text(encoding="utf-8", errors="ignore")
            else:
                entry["base64"] = base64.b64encode(target.read_bytes()).decode()
        entries.append(entry)

    manifest = {"count": len(entries), "files": entries}
    (DELIVERY / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="รวมผลงานสแกนเพื่อส่งขึ้นไดรฟ์")
    parser.add_argument("--since", help="เอาเฉพาะไฟล์ที่ชื่อขึ้นต้นตั้งแต่ค่านี้ เช่น 20260731")
    args = parser.parse_args(argv)

    manifest = build(args.since)
    if not manifest["count"]:
        print("ไม่พบผลงานใน scan_text", file=sys.stderr)
        return 1

    print(f"เตรียมส่ง {manifest['count']} ไฟล์ -> {DELIVERY}")
    for entry in manifest["files"]:
        flag = "" if entry["inline"] else "  (ใหญ่เกิน ต้องอัปแยก)"
        print(f"  {entry['name']}  {entry['size'] / 1024:.0f} KB{flag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
