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


def pick_sample_pages(total: int, count: int) -> list[int]:
    """เลือกหน้าตัวอย่างให้กระจายทั้งเล่ม ไม่ใช่กระจุกอยู่ต้นเล่ม

    หน้าแรกๆ มักเป็นปกหรือสารบัญซึ่งไม่ได้บอกอะไรเกี่ยวกับเนื้อเรื่อง
    ต้องสุ่มดูตรงกลางเล่มด้วยจึงจะรู้ว่าเนื้อในเป็นข้อความหรือภาพ
    """
    if total <= count:
        return list(range(total))
    step = total / count
    return sorted({min(total - 1, int(i * step)) for i in range(count)})


def survey(pdf: Path, sample_pages: int = 0) -> dict:
    try:
        doc = fitz.open(str(pdf))
    except Exception as exc:
        return {"file": pdf.name, "error": str(exc)[:120]}

    pages = len(doc)
    indexes = pick_sample_pages(pages, sample_pages) if sample_pages else range(pages)
    checked = 0
    with_text = 0
    sample = ""
    for index in indexes:
        checked += 1
        text = (doc[index].get_text() or "").strip()
        if len(text) >= TEXT_LAYER_MIN_CHARS:
            with_text += 1
            if not sample:
                sample = " ".join(text.split())[:80]
    doc.close()

    ratio = with_text / checked if checked else 0.0
    if sample_pages:
        # ดูแค่ตัวอย่าง จึงประมาณจำนวนหน้าทั้งเล่มจากสัดส่วนที่วัดได้
        with_text = round(ratio * pages)
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
    parser.add_argument("--quick", type=int, metavar="N", default=0,
                        help="ดูแค่ N หน้าต่อเล่มแบบกระจายทั้งเล่ม เร็วกว่ามากเมื่อไฟล์อยู่บนไดรฟ์สตรีม")
    args = parser.parse_args(argv)

    if not args.folder.is_dir():
        print(f"ไม่ใช่โฟลเดอร์: {args.folder}", file=sys.stderr)
        return 1

    pattern = "**/*.pdf" if args.recursive else "*.pdf"
    pdfs = sorted(args.folder.glob(pattern))
    if not pdfs:
        print("ไม่พบไฟล์ PDF", file=sys.stderr)
        return 1

    out = args.out or args.folder / "สำรวจPDF.csv"
    fields = ["file", "pages", "text_layer", "need_ocr", "verdict", "mb", "sample", "error"]

    # อ่านผลเดิมกลับมา แล้วข้ามเล่มที่สำรวจไปแล้ว
    #
    # คลังมีหลายพันเล่มและไฟล์อยู่บนไดรฟ์แบบสตรีม การอ่านแต่ละเล่มต้องโหลด
    # ไฟล์ลงมาก่อน ถ้าหยุดกลางคันแล้วต้องเริ่มใหม่ทั้งหมดจะเสียเวลามาก
    rows: list[dict] = []
    done: set[str] = set()
    if out.exists():
        with out.open(encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh))
        for row in rows:
            for key in ("pages", "text_layer", "need_ocr"):
                if row.get(key):
                    row[key] = int(row[key])
            done.add(row["file"])
        print(f"มีผลเดิมอยู่แล้ว {len(done)} เล่ม จะสำรวจต่อจากตรงนั้น")

    todo = [p for p in pdfs if p.name not in done]
    print(f"สำรวจ {len(todo)} เล่ม (ทั้งหมด {len(pdfs)})\n")

    # เขียนทีละเล่ม ไม่รอจบ จะได้ไม่เสียของถ้าหยุดกลางทาง
    def flush() -> None:
        with out.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

    try:
        for number, pdf in enumerate(todo, 1):
            row = survey(pdf, args.quick)
            rows.append(row)
            if "error" in row:
                print(f"  [เปิดไม่ได้] {row['file'][:50]}: {row['error'][:60]}")
            else:
                print(f"  {row['verdict']:<22} {row['pages']:>4} หน้า  "
                      f"text {row['text_layer']:>4}  {row['file'][:50]}")
            if number % 20 == 0:
                flush()
    except KeyboardInterrupt:
        print("\n\nหยุดกลางคัน ผลที่สำรวจไปแล้วถูกบันทึกไว้")
        print(f"รันคำสั่งเดิมซ้ำเพื่อทำต่อ  ({len(rows)} เล่ม)")
    finally:
        flush()

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
