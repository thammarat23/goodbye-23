# -*- coding: utf-8 -*-
"""ทำความสะอาดข้อความ OCR ภาษาไทย

รวมตรรกะจาก clean_ocr_thai_v2.py และ ocr_pdf.py ของระบบเดิมไว้ที่เดียว
ใช้ได้ทั้งเป็นโมดูล (`from thai_clean import cleanse`) และสั่งจากบรรทัดคำสั่ง
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

THAI = r"฀-๿"
TONE_MARKS = "่้๊๋"

PAGE_MARKER_RE = re.compile(rf"=====\s*หน้า\s*(\d+)\s*/?\s*(\d*)\s*\(OCR\)\s*=====")

# โทเคนขยะที่ Tesseract มักหลุดมากับหนังสือกำลังภายในที่พิมพ์เก่า
GARBAGE_PATTERNS = [
    r"P=", r"p=", r"\bpr\b", r"Qs", r"QQ", r"Qa", r"Q/", r"rr", r"Y\]",
    r"สสม", r"สสจ", r"มบขส", r"มบข", r"มซรเฆ", r"ขชซส",
    r"ซข", r"ซซ", r"ฆซ", r"ฆม", r"ฆส", r"ฮซ", r"ชซ", r"ซ่ง",
    r"ซัน", r"ซัว", r"ซัง", r"ซส", r"ซม", r"ซง",
    r"มมม", r"มง(?=\s|$)", r"มืน(?=\s|$)", r"มืง(?=\s|$)", r"มีม", r"ม่มี", r"มีม่",
    r"มช", r"มข", r"มท", r"มร", r"มษ",
    r"[«»]", r"[─━│♦♣♠♥]",
]
GARBAGE_RE = re.compile("|".join(GARBAGE_PATTERNS))

SYMBOL_CLASS = r"=+|/\\#*@&%$^~`<>\[\]{}"


def fix_stacked_marks(text: str) -> str:
    """ยุบวรรณยุกต์ที่ OCR อ่านซ้อนกันหลายตัวให้เหลือตัวเดียว"""
    for mark in TONE_MARKS:
        text = re.sub(mark + "+", mark, text)
    return re.sub(rf"([{TONE_MARKS}])[{TONE_MARKS}]", r"\1", text)


def clean_line(line: str) -> str:
    s = line.strip()
    if not s:
        return ""
    # อักษรละตินโดดๆ ที่ลอยอยู่กลางข้อความไทย
    s = re.sub(rf"(?<=[^{THAI}])[a-zA-Z](?=[^{THAI}]|$)", "", s)
    s = re.sub(rf"^[a-zA-Z](?=[^{THAI}])", "", s)
    s = GARBAGE_RE.sub("", s)
    # สัญลักษณ์เดี่ยวที่มีช่องว่างขนาบ
    s = re.sub(rf"\s[{SYMBOL_CLASS}]\s", " ", s)
    s = re.sub(rf"^[{SYMBOL_CLASS}]+", "", s)
    s = re.sub(rf"[{SYMBOL_CLASS}]+$", "", s)
    # ขยะที่คั่นระหว่างอักษรไทยสองตัว
    # ไม่รวม " และ ' เพราะบทสนทนาในนิยายกำลังภายในใช้เครื่องหมายคำพูดตลอด
    s = re.sub(rf"([{THAI}])\s*[{SYMBOL_CLASS}0-9]+\s*([{THAI}])", r"\1 \2", s)
    s = re.sub(r" {2,}", " ", s)
    return s.strip()


def has_any_text(s: str) -> bool:
    """เก็บเฉพาะบรรทัดที่มีคำจริง ไม่ใช่ตัวอักษรโดดๆ"""
    if not s:
        return False
    return bool(re.search(rf"[{THAI}]{{3,}}", s)) or bool(re.search(r"[a-zA-Z]{3,}", s))


def cleanse(raw_text: str, total_pages: int | None = None) -> str:
    raw_text = fix_stacked_marks(raw_text)
    out: list[str] = []
    blank_pending = False

    for raw in raw_text.split("\n"):
        raw = raw.rstrip("\r")
        marker = PAGE_MARKER_RE.search(raw)
        if marker:
            pages = marker.group(2) or (str(total_pages) if total_pages else "")
            cleaned = f"===== หน้า {marker.group(1)}/{pages} (OCR) =====" if pages \
                else f"===== หน้า {marker.group(1)} (OCR) ====="
        elif "= OCR" in raw and "=====" in raw:
            continue  # ตัวคั่นหน้าที่พัง
        else:
            cleaned = clean_line(raw)
            if not has_any_text(cleaned):
                continue

        if cleaned == "":
            if blank_pending:
                continue
            blank_pending = True
        else:
            blank_pending = False
        out.append(cleaned)

    # เว้นบรรทัดรอบตัวคั่นหน้าให้อ่านง่าย
    result: list[str] = []
    for i, line in enumerate(out):
        if PAGE_MARKER_RE.search(line):
            if result and result[-1] != "":
                result.append("")
            result.append(line)
            if i + 1 < len(out) and out[i + 1] != "":
                result.append("")
        else:
            result.append(line)
    return "\n".join(result)


def clean_file(path: Path, in_place: bool = False) -> tuple[int, int]:
    raw = path.read_text(encoding="utf-8-sig", errors="ignore")
    cleaned = cleanse(raw)
    target = path if in_place else path.with_suffix(".clean.txt")
    target.write_text(cleaned + "\n", encoding="utf-8")
    return len(raw.splitlines()), len(cleaned.splitlines())


def main(argv: list[str]) -> int:
    if not argv:
        print("ใช้: python3 thai_clean.py <ไฟล์.txt> [...] [--in-place]", file=sys.stderr)
        return 1
    in_place = "--in-place" in argv
    files = [Path(a) for a in argv if not a.startswith("--")]
    for path in files:
        if not path.exists():
            print(f"ไม่พบไฟล์: {path}", file=sys.stderr)
            continue
        before, after = clean_file(path, in_place)
        print(f"{path.name}: {before} -> {after} บรรทัด")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
