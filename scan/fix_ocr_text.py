#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ซ่อมไฟล์ข้อความ OCR ภาษาไทยที่เสียหาย (โฟลเดอร์ "หนังสือรอแก้")

สคริปต์นี้แก้เฉพาะความเสียหาย **ที่ตัดสินได้แน่นอนด้วยกฎ** เท่านั้น
ความเสียหายที่ต้องใช้พจนานุกรมหรือบริบทช่วยตัดสิน จะถูก "รายงาน" ไว้
ไม่ถูกแก้เอง เพราะแก้ผิดแล้วกู้คืนไม่ได้

ใช้:
    python3 scan/fix_ocr_text.py ไฟล์.txt [...]        # เขียนเป็น .repaired.txt
    python3 scan/fix_ocr_text.py โฟลเดอร์/ --report    # ตรวจอย่างเดียว ไม่แก้
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from thai_repair import repair_text  # noqa: E402

# ── ความเสียหายที่แก้ได้แน่นอน ────────────────────────────────────────────

# นิคหิต + สระอา (U+0E4D U+0E32) ต้องเป็นสระอำ (U+0E33)
# เกิดตอนดึงข้อความจาก PDF ตัวอักษรดูเหมือนเดิมแต่โค้ดพอยต์ผิด
# ทำให้ค้นหาไม่เจอและตัวอ่านออกเสียงผิด
SARA_AM_BROKEN = "ํา"
SARA_AM = "ำ"

# ตัวคั่นหน้าที่หัวท้ายหลุด: "หน้า 12/302 (OCR" -> "===== หน้า 12/302 (OCR) ====="
BROKEN_MARKER = re.compile(r"^\s*=*\s*หน้า\s*(\d+)\s*/\s*(\d+)\s*\(?\s*OCR\s*\)?\s*=*\s*$")

# ── ความเสียหายที่ "แก้เองไม่ได้" ต้องมีพจนานุกรมหรือคนตัดสิน ──────────────
#
# ตัวอย่างจากไฟล์จริง (กระบี่เหนือกระบี่ 1BW.fixed.final.txt)
#
#   เป็นั้นักเขียนั้นามโรจน์   ควรเป็น  เป็นนักเขียนนามโรจน์
#   ถนั้นพระรามสี่            ควรเป็น  ถนนพระรามสี่
#
# คือมี ั้ แทรกกลาง นน กลายเป็น นั้น  แต่ "นั้น" เป็นคำไทยที่ใช้จริงและพบบ่อยมาก
# รูปแบบตัวอักษรจึงเหมือนกันเป๊ะ แยกด้วยกฎไม่ได้ ต้องดูบริบทหรือเทียบพจนานุกรม
#
#   เสียังกระเดื่อง          ควรเป็น  เสียงกระเดื่อง
#   เพียังไหน               ควรเป็น  เพียงไหน
#
# เช่นเดียวกัน ยง กลายเป็น ยัง ซึ่ง "ยัง" ก็เป็นคำไทยที่ใช้จริง
#
# สคริปต์นี้จึงแค่ "นับ" ให้ ไม่แตะต้อง
SUSPECT_PATTERNS = {
    "นั้น_อาจมาจาก_นน": re.compile(r"นั้น"),
    "ยัง_อาจมาจาก_ยง": re.compile(r"ยัง"),
}

THAI = r"฀-๿"
# คำไทยยาวผิดปกติ = ช่องว่างระหว่างคำหายไป
RUNON = re.compile(rf"[{THAI}]{{40,}}")


def repair(text: str) -> tuple[str, dict]:
    stats = {
        "sara_am_fixed": text.count(SARA_AM_BROKEN),
        "markers_fixed": 0,
        "lines_in": len(text.splitlines()),
    }

    text = text.replace(SARA_AM_BROKEN, SARA_AM)
    text = unicodedata.normalize("NFC", text)

    out = []
    for line in text.split("\n"):
        match = BROKEN_MARKER.match(line)
        if match:
            out.append(f"===== หน้า {match.group(1)}/{match.group(2)} (OCR) =====")
            stats["markers_fixed"] += 1
        else:
            out.append(line.rstrip())
    text = "\n".join(out)

    stats["lines_out"] = len(text.splitlines())
    return text, stats


def inspect(text: str) -> dict:
    found = {name: len(pat.findall(text)) for name, pat in SUSPECT_PATTERNS.items()}
    runons = RUNON.findall(text)
    found["คำติดกันยาวเกิน40ตัว"] = len(runons)
    found["ตัวอย่างคำติดกัน"] = runons[0][:60] if runons else ""
    return found


def process(path: Path, report_only: bool, use_dict: bool = True,
            space: bool = False) -> dict:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    fixed, stats = repair(text)

    if use_dict:
        fixed, fixes, unsure = repair_text(fixed)
        stats["words_repaired"] = len(fixes)
        stats["words_unsure"] = len(unsure)
        stats["fix_samples"] = [f"{a} -> {b}" for a, b in fixes[:8]]
        stats["unsure_samples"] = unsure[:8]
    else:
        fixes, unsure = [], []
        stats["words_repaired"] = 0
        stats["words_unsure"] = 0
        stats["fix_samples"] = []
        stats["unsure_samples"] = []

    if space:
        from thai_space import add_spaces
        fixed, added = add_spaces(fixed)
        stats["spaces_added"] = added
    else:
        stats["spaces_added"] = 0

    stats.update(inspect(fixed))
    stats["file"] = path.name
    if not report_only:
        target = path.with_suffix(".repaired.txt")
        target.write_text(fixed, encoding="utf-8")
        stats["written"] = target.name

        # บันทึกทุกจุดที่แก้ ไว้ตรวจย้อนหลังและกลับคืนได้ถ้าแก้ผิด
        # ตัวซ่อมตัดสินจากพจนานุกรม ไม่ได้เข้าใจเนื้อเรื่อง จึงต้องตรวจได้เสมอ
        log = path.with_suffix(".changes.tsv")
        lines = ["ชนิด\tก่อน\tหลัง"]
        lines += [f"แก้\t{a}\t{b}" for a, b in fixes]
        lines += [f"ไม่แก้ รอคนตัดสิน\t{w}\t" for w in unsure]
        log.write_text("\n".join(lines) + "\n", encoding="utf-8")
        stats["change_log"] = log.name
    return stats


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="ซ่อมไฟล์ข้อความ OCR ไทยที่เสียหาย")
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--report", action="store_true", help="ตรวจอย่างเดียว ไม่เขียนไฟล์")
    parser.add_argument("--json", action="store_true", help="ผลลัพธ์เป็น JSON")
    parser.add_argument("--no-dict", action="store_true",
                        help="ข้ามการซ่อมด้วยพจนานุกรม ทำเฉพาะที่แก้ได้แน่นอน")
    parser.add_argument("--space", action="store_true",
                        help="แทรกช่องว่างคืนในช่วงที่คำติดกันเป็นพืด (ปิดไว้เป็นค่าเริ่มต้น)")
    args = parser.parse_args(argv)

    targets: list[Path] = []
    for path in args.paths:
        if path.is_dir():
            targets.extend(sorted(p for p in path.glob("*.txt") if ".repaired" not in p.name))
        elif path.exists():
            targets.append(path)
        else:
            print(f"ไม่พบ: {path}", file=sys.stderr)

    if not targets:
        print("ไม่มีไฟล์ให้ทำงาน", file=sys.stderr)
        return 1

    results = [process(p, args.report, not args.no_dict, args.space) for p in targets]

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0

    for r in results:
        print(f"\n── {r['file']}")
        print(f"   แก้สระอำที่เข้ารหัสผิด : {r['sara_am_fixed']:,} จุด")
        print(f"   ซ่อมตัวคั่นหน้า        : {r['markers_fixed']:,} จุด")
        print(f"   ซ่อมคำด้วยพจนานุกรม    : {r['words_repaired']:,} คำ")
        for sample in r["fix_samples"]:
            print(f"      {sample}")
        print(f"   ไม่กล้าแก้ ต้องคนดู     : {r['words_unsure']:,} คำ")
        if r["unsure_samples"]:
            print(f"      {', '.join(r['unsure_samples'])}")
        if r.get("spaces_added"):
            print(f"   แทรกช่องว่างคืน        : {r['spaces_added']:,} จุด")
        print(f"   คำติดกันยาวเกิน 40 ตัว : {r['คำติดกันยาวเกิน40ตัว']:,}")
        if r["ตัวอย่างคำติดกัน"]:
            print(f"      {r['ตัวอย่างคำติดกัน']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
