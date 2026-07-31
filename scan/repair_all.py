#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ซ่อมข้อความทั้งโฟลเดอร์ ทำขนานตามจำนวนคอร์ แล้วสรุปเป็นตารางเดียว

ออกแบบให้ "ตรวจผลได้ถูก" เป็นหลัก ไฟล์ 100 เล่มถ้าต้องเปิดอ่านทีละไฟล์
จะเสียเวลาและเสียค่าใช้จ่ายมาก สคริปต์นี้จึงสรุปทุกอย่างลงตารางเดียว
แล้วค่อยเจาะดูเฉพาะไฟล์ที่ตัวเลขผิดปกติ

ใช้:
    python3 scan/repair_all.py โฟลเดอร์/                 # ซ่อมจริง
    python3 scan/repair_all.py โฟลเดอร์/ --report        # ดูก่อน ไม่เขียนไฟล์
    python3 scan/repair_all.py โฟลเดอร์/ --jobs 4
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def _one(args: tuple[str, bool, bool]) -> dict:
    path_str, report_only, space = args
    from fix_ocr_text import process  # นำเข้าในลูกเพื่อไม่ต้องขนพจนานุกรมข้ามโพรเซส
    try:
        return process(Path(path_str), report_only, True, space)
    except Exception as exc:
        return {"file": Path(path_str).name, "error": str(exc)}


COLUMNS = [
    "file", "sara_am_fixed", "markers_fixed", "words_repaired",
    "words_unsure", "spaces_added", "คำติดกันยาวเกิน40ตัว",
    "lines_in", "lines_out", "error",
]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="ซ่อมข้อความ OCR ไทยทั้งโฟลเดอร์")
    parser.add_argument("folder", type=Path)
    parser.add_argument("--report", action="store_true", help="ไม่เขียนไฟล์ ดูอย่างเดียว")
    parser.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2)))
    parser.add_argument("--space", action="store_true",
                        help="แทรกช่องว่างคืนในช่วงที่คำติดกันเป็นพืด (ปิดไว้เป็นค่าเริ่มต้น)")
    parser.add_argument("--out", type=Path, help="ที่เก็บตารางสรุป (ค่าเริ่มต้น: สรุปการซ่อม.csv ในโฟลเดอร์)")
    args = parser.parse_args(argv)

    if not args.folder.is_dir():
        print(f"ไม่ใช่โฟลเดอร์: {args.folder}", file=sys.stderr)
        return 1

    targets = sorted(
        p for p in args.folder.glob("*.txt")
        if ".repaired" not in p.name and ".changes" not in p.name
    )
    if not targets:
        print("ไม่พบไฟล์ .txt", file=sys.stderr)
        return 1

    print(f"พบ {len(targets)} ไฟล์ ทำขนาน {args.jobs} โพรเซส")
    started = time.time()
    results: list[dict] = []

    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        futures = {
            pool.submit(_one, (str(p), args.report, args.space)): p.name for p in targets
        }
        for done, future in enumerate(as_completed(futures), 1):
            results.append(future.result())
            if done % 5 == 0 or done == len(targets):
                rate = done / (time.time() - started)
                print(f"  {done}/{len(targets)}  ({rate:.1f} ไฟล์/วินาที)")

    results.sort(key=lambda r: r.get("file", ""))
    out_path = args.out or args.folder / "สรุปการซ่อม.csv"
    with out_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)

    ok = [r for r in results if "error" not in r]
    failed = [r for r in results if "error" in r]
    total = lambda k: sum(r.get(k, 0) for r in ok)  # noqa: E731

    print(f"\nเสร็จใน {time.time() - started:.0f} วินาที")
    print(f"  สำเร็จ {len(ok)} ไฟล์  ล้มเหลว {len(failed)} ไฟล์")
    print(f"  แก้สระอำที่เข้ารหัสผิด : {total('sara_am_fixed'):,} จุด")
    print(f"  ซ่อมตัวคั่นหน้า        : {total('markers_fixed'):,} จุด")
    print(f"  ซ่อมคำด้วยพจนานุกรม    : {total('words_repaired'):,} คำ")
    print(f"  ไม่กล้าแก้ ต้องคนดู     : {total('words_unsure'):,} คำ")
    print(f"\nตารางสรุป: {out_path}")

    if failed:
        print("\nไฟล์ที่ล้มเหลว")
        for r in failed:
            print(f"  {r['file']}: {r['error']}")

    # ไฟล์ที่ซ่อมเยอะผิดปกติควรถูกมองด้วยตาก่อนเอาไปใช้จริง
    if ok:
        avg = total("words_repaired") / len(ok)
        odd = [r for r in ok if r.get("words_repaired", 0) > avg * 3]
        if odd:
            print(f"\nซ่อมเยอะผิดปกติ (เกินค่าเฉลี่ย {avg:.0f} คำ สามเท่า) ควรเปิดดู changes.tsv ก่อน")
            for r in sorted(odd, key=lambda r: -r["words_repaired"])[:10]:
                print(f"  {r['words_repaired']:>7,} คำ  {r['file']}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
