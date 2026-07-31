#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""สำรวจว่า PDF เล่มไหนมีข้อความอยู่แล้ว เล่มไหนต้อง OCR

ตอบคำถามเดียวแต่สำคัญที่สุดก่อนเริ่มงาน คือเล่มไหน "ได้ของฟรี"

หนังสือที่เป็น PDF ข้อความอยู่แล้ว ดึงข้อความออกมาได้ตรงต้นฉบับ ไม่ต้อง OCR
ไม่ต้องซ่อม ไม่มีความผิดพลาดสักตัว ส่วนเล่มที่เป็นภาพสแกนถึงต้องเข้าสายยาว
รู้ก่อนว่าเล่มไหนเป็นแบบไหน จะได้ไม่เสียเวลาทำงานที่ไม่ต้องทำ

อ่านแค่โครงสร้าง PDF ไม่ได้เรนเดอร์ภาพ จึงเร็วมากแม้เล่มหนา

ใช้:
    python3 scan/survey_pdfs.py โฟลเดอร์/
    python3 scan/survey_pdfs.py โฟลเดอร์/ --recursive
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import fitz  # PyMuPDF

# หน้าที่มีข้อความน้อยกว่านี้ถือว่าไม่มี text layer
TEXT_LAYER_MIN_CHARS = 120

# มี text layer เกินสัดส่วนนี้ถือว่าทั้งเล่มใช้ได้เลย
MOSTLY_TEXT = 0.90
# ต่ำกว่านี้ถือว่าเป็นภาพสแกนล้วน
MOSTLY_SCAN = 0.10


def survey(pdf: Path) -> dict:
    try:
        doc = fitz.open(str(pdf))
    except Exception as exc:
        return {"file": pdf.name, "error": str(exc)[:120]}

    pages = len(doc)
    with_text = 0
    sample = ""
    for page in doc:
        text = (page.get_text() or "").strip()
        if len(text) >= TEXT_LAYER_MIN_CHARS:
            with_text += 1
            if not sample:
                sample = " ".join(text.split())[:80]
    doc.close()

    ratio = with_text / pages if pages else 0.0
    if ratio >= MOSTLY_TEXT:
        verdict = "ใช้ได้เลย ไม่ต้อง OCR"
    elif ratio <= MOSTLY_SCAN:
        verdict = "ภาพสแกน ต้อง OCR"
    else:
        verdict = "ผสม"

    return {
        "file": pdf.name,
        "pages": pages,
        "text_layer": with_text,
        "need_ocr": pages - with_text,
        "verdict": verdict,
        "mb": round(pdf.stat().st_size / 1048576, 1),
        "sample": sample,
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="สำรวจว่า PDF เล่มไหนมีข้อความอยู่แล้ว")
    parser.add_argument("folder", type=Path)
    parser.add_argument("--recursive", action="store_true", help="ไล่โฟลเดอร์ย่อยด้วย")
    parser.add_argument("--out", type=Path, help="ที่เก็บตาราง (ค่าเริ่มต้น: สำรวจPDF.csv)")
    args = parser.parse_args(argv)

    if not args.folder.is_dir():
        print(f"ไม่ใช่โฟลเดอร์: {args.folder}", file=sys.stderr)
        return 1

    pattern = "**/*.pdf" if args.recursive else "*.pdf"
    pdfs = sorted(args.folder.glob(pattern))
    if not pdfs:
        print("ไม่พบไฟล์ PDF", file=sys.stderr)
        return 1

    print(f"สำรวจ {len(pdfs)} เล่ม\n")
    rows = []
    for pdf in pdfs:
        row = survey(pdf)
        rows.append(row)
        if "error" in row:
            print(f"  [เปิดไม่ได้] {row['file']}: {row['error']}")
        else:
            print(f"  {row['verdict']:<22} {row['pages']:>4} หน้า  "
                  f"text {row['text_layer']:>4}  {row['file'][:50]}")

    out = args.out or args.folder / "สำรวจPDF.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["file", "pages", "text_layer", "need_ocr", "verdict", "mb", "sample", "error"],
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)

    ok = [r for r in rows if "error" not in r]
    ready = [r for r in ok if r["verdict"].startswith("ใช้ได้")]
    scan = [r for r in ok if r["verdict"].startswith("ภาพสแกน")]
    mixed = [r for r in ok if r["verdict"] == "ผสม"]

    print(f"\nสรุป {len(ok)} เล่ม")
    print(f"  ใช้ได้เลย ไม่ต้อง OCR : {len(ready):>4} เล่ม  "
          f"({sum(r['pages'] for r in ready):,} หน้า)")
    print(f"  ต้อง OCR             : {len(scan):>4} เล่ม  "
          f"({sum(r['pages'] for r in scan):,} หน้า)")
    print(f"  ผสม                  : {len(mixed):>4} เล่ม")

    ocr_pages = sum(r["need_ocr"] for r in ok)
    if ocr_pages:
        # วัดจากเครื่องที่สองได้ราว 0.5 วินาทีต่อหน้า
        print(f"\n  หน้าที่ต้อง OCR รวม {ocr_pages:,} หน้า "
              f"ใช้เวลาราว {ocr_pages * 0.5 / 3600:.1f} ชั่วโมง")
    print(f"\nตาราง: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
