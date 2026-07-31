#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""เตรียมหนังสือหนึ่งเล่มให้พร้อมทำเสียงและขึ้นเว็บอ่าน

ทำสามอย่างตามลำดับ

  1. ดึงข้อความ  ถ้าหน้าไหนมี text layer อยู่แล้วใช้เลย ไม่ต้อง OCR
     ได้ข้อความตรงต้นฉบับ 100% ไม่มีความผิดพลาดจากการอ่านภาพ
     หน้าที่เป็นภาพสแกนจริงเท่านั้นที่ต้อง OCR
  2. แบ่งเป็นตอน  หาหัวข้อ "บทที่" หรือ "ตอนที่" ในเนื้อเรื่อง
     ถ้าไม่เจอและเล่มหนา จะแบ่งตามจำนวนหน้าให้
  3. แบ่งเป็นย่อหน้า  แล้วออกรายการงานเสียงทั้งรายย่อหน้าและรวมทั้งตอน

ผลลัพธ์วางในโฟลเดอร์ชื่อเดียวกับหนังสือ

    book.json             โครงสร้างเล่ม ตอน ย่อหน้า
    audio_manifest.json   {ชื่อไฟล์เสียง: ข้อความ} รูปแบบเดียวกับที่ใช้อยู่
    ตอนที่-01.txt          ข้อความทั้งตอน สำหรับทำเสียงยาว
    ...

ใช้:
    python3 scan/make_book.py หนังสือ.pdf
    python3 scan/make_book.py หนังสือ.pdf --out ปลายทาง/ --pages-per-part 40
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

import fitz  # PyMuPDF

sys.path.insert(0, str(Path(__file__).resolve().parent))

# หน้าที่มีข้อความน้อยกว่านี้ถือว่าไม่มี text layer ต้อง OCR
TEXT_LAYER_MIN_CHARS = 120

# หัวข้อตอนที่พบในนิยายกำลังภายใน
CHAPTER_RE = re.compile(
    r"^\s*(?:บทที่|ตอนที่|ภาคที่|บทนำ|ปฐมบท)\s*([๐-๙\d]*)\s*(.{0,60})$"
)

# ถ้าไม่เจอหัวข้อตอนเลย จะหั่นตามจำนวนหน้าเท่านี้
DEFAULT_PAGES_PER_PART = 30

THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")

_THAI_END = re.compile("[฀-๿]$")
_THAI_START = re.compile("^[฀-๿]")


@dataclass
class Paragraph:
    id: str
    text: str
    chars: int


@dataclass
class Chapter:
    no: int
    title: str
    page_from: int
    page_to: int
    paragraphs: list[Paragraph]


def slug(name: str) -> str:
    """ชื่อสั้นสำหรับตั้งชื่อไฟล์เสียง เก็บอักษรไทยไว้"""
    keep = "".join(
        ch if ch.isalnum() or "฀" <= ch <= "๿" else "_" for ch in name
    )
    return re.sub(r"_{2,}", "_", keep).strip("_")[:40] or "book"


# ระยะห่างแนวตั้งเกินกี่เท่าของระยะบรรทัดปกติ จึงถือว่าขึ้นย่อหน้าใหม่
PARAGRAPH_GAP_RATIO = 1.8


def page_text_with_paragraphs(page: fitz.Page) -> str:
    """ดึงข้อความโดยรักษาการแบ่งย่อหน้าไว้ ด้วยการดูระยะห่างแนวตั้ง

    get_text() ธรรมดาคืนบรรทัดต่อกันหมด แยกไม่ออกว่าตรงไหนขึ้นย่อหน้าใหม่
    เพราะ PDF ไม่มี "บรรทัดว่าง" มีแต่ระยะห่าง ต้องดูพิกัดเอง

    วัดจากหน้าจริง ระยะระหว่างบรรทัดในย่อหน้าเดียวกันราว 1.4 หน่วย
    ส่วนระหว่างย่อหน้าราว 17 หน่วย ต่างกันสิบเท่า แยกได้ไม่ยาก
    """
    blocks = [b for b in page.get_text("blocks") if b[4].strip()]
    if not blocks:
        return ""
    blocks.sort(key=lambda b: (round(b[1], 1), b[0]))

    gaps = [
        blocks[i][1] - blocks[i - 1][3]
        for i in range(1, len(blocks))
    ]
    positive = sorted(g for g in gaps if g > 0)
    # ใช้ค่าที่ควอร์ไทล์ล่างเป็นระยะบรรทัดปกติ ไม่ใช่ค่ากลาง
    # เพราะหน้าที่มีย่อหน้าสั้นๆ หลายย่อหน้า จำนวนระยะห่างแบบกว้างจะพอๆ กับ
    # แบบแคบ ค่ากลางเลยไปตกที่ระยะห่างระหว่างย่อหน้า แล้วไม่มีอะไรเกินเกณฑ์เลย
    normal = positive[len(positive) // 4] if positive else 0.0

    out = [blocks[0][4].strip()]
    for index in range(1, len(blocks)):
        gap = blocks[index][1] - blocks[index - 1][3]
        new_para = normal > 0 and gap > normal * PARAGRAPH_GAP_RATIO
        out.append(("\n\n" if new_para else "\n") + blocks[index][4].strip())
    return "".join(out)


def extract_pages(pdf: Path, ocr_lang: str) -> tuple[list[str], dict]:
    """คืน (ข้อความรายหน้า, สถิติ) ใช้ text layer ก่อนเสมอ"""
    doc = fitz.open(str(pdf))
    pages: list[str] = []
    need_ocr: list[int] = []

    for index, page in enumerate(doc):
        text = page_text_with_paragraphs(page).strip()
        pages.append(text)
        if len(text) < TEXT_LAYER_MIN_CHARS:
            need_ocr.append(index)

    stats = {
        "pages": len(pages),
        "pages_text_layer": len(pages) - len(need_ocr),
        "pages_ocr": len(need_ocr),
    }

    if need_ocr:
        # ต้อง OCR เฉพาะหน้าที่เป็นภาพจริง ส่วนที่มีข้อความอยู่แล้วไม่แตะ
        from scan_books import preprocess, render_page, run_tesseract, PDF_DPI
        for index in need_ocr:
            image = preprocess(render_page(doc[index], PDF_DPI))
            pages[index] = run_tesseract(image).strip()

    doc.close()
    return pages, stats


def find_chapters(pages: list[str]) -> list[tuple[int, int, str]]:
    """หาหัวข้อตอน คืน [(หน้าที่เริ่ม, เลขตอน, ชื่อตอน)]"""
    found: list[tuple[int, int, str]] = []
    for page_index, text in enumerate(pages):
        for line in text.split("\n")[:6]:  # หัวข้อตอนมักอยู่ต้นหน้า
            match = CHAPTER_RE.match(line.strip())
            if not match:
                continue
            raw_no = match.group(1).translate(THAI_DIGITS)
            number = int(raw_no) if raw_no.isdigit() else len(found) + 1
            found.append((page_index, number, match.group(2).strip()))
            break
    return found


def split_paragraphs(text: str) -> list[str]:
    """แบ่งย่อหน้า ยุบบรรทัดที่ถูกตัดกลางประโยคให้ต่อกัน

    ข้อความจาก PDF ขึ้นบรรทัดใหม่ทุกบรรทัดของหน้ากระดาษ ซึ่งไม่ใช่ย่อหน้าจริง
    บรรทัดที่จบด้วยอักษรไทยแล้วบรรทัดถัดไปขึ้นต้นด้วยอักษรไทย ถือว่าเป็น
    ประโยคเดียวกันที่ถูกตัด ให้ต่อกัน ย่อหน้าจริงคือตรงที่มีบรรทัดว่างคั่น
    """
    blocks = re.split(r"\n\s*\n", text)
    paragraphs: list[str] = []
    for block in blocks:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if not lines:
            continue
        joined = lines[0]
        for line in lines[1:]:
            # ภาษาไทยตัดบรรทัดกลางคำได้ ถ้าต่อด้วยช่องว่างจะได้ "แผ่น ดิน"
            # แทนที่จะเป็น "แผ่นดิน" ซึ่งตัวอ่านออกเสียงจะอ่านเป็นคนละคำ
            # ต่อตรงๆ เมื่อทั้งสองฝั่งเป็นอักษรไทย ใส่ช่องว่างเฉพาะกรณีอื่น
            thai_join = _THAI_END.search(joined) and _THAI_START.match(line)
            joined += ("" if thai_join else " ") + line
        paragraphs.append(joined)
    return paragraphs


def build_chapters(
    pages: list[str], pages_per_part: int, book_slug: str
) -> list[Chapter]:
    marks = find_chapters(pages)

    if marks:
        bounds = [(m[0], m[1], m[2]) for m in marks]
        if bounds[0][0] > 0:  # เนื้อหาก่อนตอนแรก (ปก คำนำ) นับเป็นตอน 0
            bounds.insert(0, (0, 0, "เปิดเรื่อง"))
    else:
        # ไม่มีหัวข้อตอน หั่นตามจำนวนหน้าแทน
        bounds = [
            (start, i + 1, "")
            for i, start in enumerate(range(0, len(pages), pages_per_part))
        ]

    chapters: list[Chapter] = []
    for order, (start, number, title) in enumerate(bounds):
        end = bounds[order + 1][0] if order + 1 < len(bounds) else len(pages)
        body = "\n\n".join(pages[start:end])
        paragraphs = [
            Paragraph(
                id=f"{book_slug}_c{order + 1:02d}_p{i + 1:03d}",
                text=para,
                chars=len(para),
            )
            for i, para in enumerate(split_paragraphs(body))
        ]
        chapters.append(
            Chapter(
                no=number or order + 1,
                title=title,
                page_from=start + 1,
                page_to=end,
                paragraphs=paragraphs,
            )
        )
    return chapters


def write_outputs(pdf: Path, out_dir: Path, chapters: list[Chapter],
                  stats: dict, book_slug: str) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)

    # รูปแบบเดียวกับ audio_manifest.json ที่ระบบเสียงใช้อยู่แล้ว
    # คีย์คือชื่อไฟล์เสียง ค่าคือข้อความที่ต้องอ่าน
    manifest: dict[str, str] = {}

    for order, chapter in enumerate(chapters, 1):
        for para in chapter.paragraphs:
            manifest[f"{para.id}.mp3"] = para.text

        # เสียงรวมทั้งตอน ไว้ให้คนที่อยากฟังยาวๆ ไม่ต้องกดทีละย่อหน้า
        whole = "\n\n".join(p.text for p in chapter.paragraphs)
        if whole:
            manifest[f"{book_slug}_c{order:02d}_full.mp3"] = whole
            name = f"ตอนที่-{order:02d}" + (f"-{slug(chapter.title)}" if chapter.title else "")
            (out_dir / f"{name}.txt").write_text(whole + "\n", encoding="utf-8")

    book = {
        "title": pdf.stem,
        "slug": book_slug,
        "source": pdf.name,
        **stats,
        "chapters": [
            {
                "no": c.no,
                "title": c.title,
                "page_from": c.page_from,
                "page_to": c.page_to,
                "full_audio": f"{book_slug}_c{i:02d}_full.mp3",
                "paragraphs": [asdict(p) for p in c.paragraphs],
            }
            for i, c in enumerate(chapters, 1)
        ],
    }
    (out_dir / "book.json").write_text(
        json.dumps(book, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "audio_manifest.json").write_text(
        json.dumps({"th": manifest}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return book


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="เตรียมหนังสือให้พร้อมทำเสียงและขึ้นเว็บ")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--out", type=Path, help="โฟลเดอร์ปลายทาง")
    parser.add_argument("--pages-per-part", type=int, default=DEFAULT_PAGES_PER_PART,
                        help="หั่นกี่หน้าต่อตอน เมื่อหาหัวข้อตอนไม่เจอ")
    parser.add_argument("--lang", default="tha+eng", help="ภาษา OCR สำหรับหน้าที่เป็นภาพ")
    parser.add_argument("--no-repair", action="store_true",
                        help="ไม่ต้องซ่อมข้อความ (ใช้เมื่อ text layer สมบูรณ์อยู่แล้ว)")
    args = parser.parse_args(argv)

    if not args.pdf.exists():
        print(f"ไม่พบไฟล์: {args.pdf}", file=sys.stderr)
        return 1

    book_slug = slug(args.pdf.stem)
    print(f"อ่าน {args.pdf.name}")
    pages, stats = extract_pages(args.pdf, args.lang)
    print(f"  {stats['pages']} หน้า | มี text layer {stats['pages_text_layer']} "
          f"| ต้อง OCR {stats['pages_ocr']}")

    # หน้าที่มี text layer ไม่ต้องซ่อม เพราะไม่ได้ผ่าน OCR จึงไม่มีความเสียหาย
    # ซ่อมเฉพาะตอนที่ต้อง OCR จริงเท่านั้น
    if stats["pages_ocr"] and not args.no_repair:
        from fix_ocr_text import repair as safe_repair
        from thai_repair import repair_text
        repaired = 0
        for i, text in enumerate(pages):
            pre, _ = safe_repair(text)
            fixed, fixes, _unsure = repair_text(pre)
            pages[i] = fixed
            repaired += len(fixes)
        stats["words_repaired"] = repaired
        print(f"  ซ่อมคำ {repaired:,} จุด")

    chapters = build_chapters(pages, args.pages_per_part, book_slug)
    out_dir = args.out or args.pdf.parent / book_slug
    book = write_outputs(args.pdf, out_dir, chapters, stats, book_slug)

    total_paras = sum(len(c["paragraphs"]) for c in book["chapters"])
    print(f"  แบ่งได้ {len(chapters)} ตอน | {total_paras:,} ย่อหน้า")
    print(f"  งานเสียง {total_paras + len(chapters):,} ไฟล์ "
          f"({total_paras:,} ย่อหน้า + {len(chapters)} ตอนเต็ม)")
    print(f"\nผลลัพธ์: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
