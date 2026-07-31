#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ระบบสแกน OCR หนังสือกำลังภายใน (เวอร์ชันข้ามแพลตฟอร์ม)

รับไฟล์ PDF หรือรูปภาพจาก work/scan_inbox แล้วผลิต
  - <ชื่อ>.txt        ข้อความที่ทำความสะอาดแล้ว
  - <ชื่อ>.raw.txt    ข้อความดิบจาก OCR (ไว้เทียบเวลาคลีนเนอร์กินเนื้อหา)
  - <ชื่อ>.json       เมทาดาทา (จำนวนหน้า จำนวนอักขระ เวลาที่ใช้)
  - <ชื่อ>.ocr.pdf    PDF ค้นหาข้อความได้ (เมื่อใส่ --pdf)

ใช้งาน:
    python3 scan/scan_books.py                 # ประมวลผลทุกไฟล์ใน inbox รอบเดียว
    python3 scan/scan_books.py --watch         # เฝ้าโฟลเดอร์ตลอด
    python3 scan/scan_books.py --pdf a.pdf     # ระบุไฟล์เอง + สร้าง PDF ค้นหาได้
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

import fitz  # PyMuPDF
from PIL import Image, ImageFilter, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
from thai_clean import cleanse  # noqa: E402

ROOT = Path(os.environ.get("BOOK_SCAN_ROOT", Path(__file__).resolve().parent.parent / "work"))
INBOX = ROOT / "scan_inbox"
PROCESSING = ROOT / "scan_processing"
DONE = ROOT / "scan_done"
FAILED = ROOT / "scan_failed"
TEXT = ROOT / "scan_text"
STATE = ROOT / "scan_state"
LOGS = ROOT / "logs"
ALL_DIRS = [INBOX, PROCESSING, DONE, FAILED, TEXT, STATE, LOGS]

OCR_LANG = os.environ.get("BOOK_SCAN_LANG", "tha+eng")
PDF_DPI = int(os.environ.get("BOOK_SCAN_DPI", "300"))
POLL_SECONDS = int(os.environ.get("BOOK_SCAN_POLL_SECONDS", "10"))
MAX_WORKERS = max(1, min(6, os.cpu_count() or 2))
TESSERACT = os.environ.get("BOOK_SCAN_TESSERACT") or shutil.which("tesseract")

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
PDF_EXTS = {".pdf"}
SUPPORTED_EXTS = IMAGE_EXTS | PDF_EXTS

# ถ้าหน้าไหนมี text layer อยู่แล้วเกินจำนวนนี้ ให้ใช้ของเดิม ไม่ต้อง OCR ซ้ำ
DIRECT_TEXT_MIN_CHARS = 200


def ensure_dirs() -> None:
    global SCRATCH
    for folder in ALL_DIRS:
        folder.mkdir(parents=True, exist_ok=True)
    SCRATCH = scratch_dir()


def log(message: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    print(line, flush=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    with (LOGS / "scanner.log").open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def check_environment() -> list[str]:
    """คืนรายการปัญหาที่พบ ถ้าว่างแปลว่าพร้อมทำงาน"""
    problems: list[str] = []
    if not TESSERACT:
        problems.append("ไม่พบ tesseract — รัน scan/setup.sh ก่อน")
        return problems
    try:
        langs = subprocess.run(
            [TESSERACT, "--list-langs"], capture_output=True, text=True, check=True
        ).stdout.split()
    except Exception as exc:  # pragma: no cover - ขึ้นกับเครื่อง
        problems.append(f"เรียก tesseract ไม่สำเร็จ: {exc}")
        return problems
    for lang in OCR_LANG.split("+"):
        if lang not in langs:
            problems.append(f"ไม่พบชุดภาษา '{lang}' ใน tesseract (มี: {', '.join(langs)})")
    return problems


def preprocess(image: Image.Image) -> Image.Image:
    """ปรับภาพก่อน OCR: เทาขาวดำ ดึงคอนทราสต์ แล้วคมขึ้น"""
    gray = ImageOps.grayscale(image)
    return ImageOps.autocontrast(gray).filter(ImageFilter.SHARPEN)


def scratch_dir() -> Path:
    """ที่พักไฟล์ชั่วคราวตอน OCR — ใช้ /dev/shm (แรม) ถ้ามี จะได้ไม่ต้องเขียนดิสก์

    แต่ละหน้าเขียน PNG ชั่วคราวหนึ่งไฟล์แล้วลบทิ้ง เล่มหนาเป็นพันหน้าจึงเขียน
    ดิสก์ซ้ำๆ โดยไม่จำเป็น เครื่องที่สองมีแรมว่าง 14 GB ใช้แรมทำแทนคุ้มกว่า
    """
    shm = Path("/dev/shm")
    if shm.is_dir() and os.access(shm, os.W_OK):
        target = shm / "book_scan"
        target.mkdir(parents=True, exist_ok=True)
        return target
    STATE.mkdir(parents=True, exist_ok=True)
    return STATE


SCRATCH = None  # ตั้งค่าจริงตอน ensure_dirs()


def run_tesseract(image: Image.Image, psm: str = "6") -> str:
    scratch = SCRATCH or scratch_dir()
    stamp = time.time_ns()
    tmp_in = scratch / f"tmp_{stamp}.png"
    tmp_out = scratch / f"ocr_{stamp}"
    image.save(tmp_in)
    try:
        # Tesseract มัลติเธรดในตัวผ่าน OpenMP อยู่แล้ว (หนึ่งหน้ากิน CPU ~3.9 วิ
        # แต่จบใน 1.4 วิ) ถ้าปล่อยไว้แล้วรันขนาน 4 ตัวบน 4 คอร์ จะได้ 16 เธรด
        # แย่งกันจนช้าลงหลายสิบเท่า จำกัดเป็น 1 เธรดต่อตัวแล้วขนานเองแทน
        env = {**os.environ, "OMP_THREAD_LIMIT": "1"}
        subprocess.run(
            [TESSERACT, str(tmp_in), str(tmp_out), "-l", OCR_LANG,
             "--psm", psm, "--oem", "1", "quiet"],
            check=True, capture_output=True, text=True, env=env,
        )
        return tmp_out.with_suffix(".txt").read_text(encoding="utf-8", errors="ignore")
    finally:
        for path in (tmp_in, tmp_out.with_suffix(".txt")):
            path.unlink(missing_ok=True)


def render_page(page: fitz.Page, dpi: int) -> Image.Image:
    pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72))
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def ocr_pdf(path: Path) -> tuple[str, dict]:
    doc = fitz.open(str(path))
    total = len(doc)
    direct_pages = [(page.get_text() or "").strip() for page in doc]
    direct_chars = sum(len(t) for t in direct_pages)

    # หน้าที่มี text layer อยู่แล้ว ข้าม OCR ไปเลย
    need_ocr = [i for i, t in enumerate(direct_pages) if len(t) < DIRECT_TEXT_MIN_CHARS]
    log(f"  {total} หน้า | มี text layer {total - len(need_ocr)} หน้า | ต้อง OCR {len(need_ocr)} หน้า")

    # เรนเดอร์ทีละชุด ไม่เก็บทุกหน้าไว้ในแรมพร้อมกัน
    # หน้า A4 ที่ 300 DPI กินราว 25 MB ถ้าเล่มหนา 400 หน้าแล้วเรนเดอร์รวดเดียว
    # จะกินเกิน 10 GB จนเครื่องล่ม ชุดละ MAX_WORKERS*2 กินไม่เกินราว 200 MB
    ocr_pages: dict[int, str] = {}
    batch_size = MAX_WORKERS * 2
    completed = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        for start in range(0, len(need_ocr), batch_size):
            batch = need_ocr[start:start + batch_size]
            futures = {
                pool.submit(run_tesseract, preprocess(render_page(doc[i], PDF_DPI))): i
                for i in batch
            }
            for future in as_completed(futures):
                ocr_pages[futures[future]] = future.result().strip()
                completed += 1
            log(f"  OCR {completed}/{len(need_ocr)} หน้า")
    doc.close()

    parts: list[str] = []
    ocr_chars = 0
    for i in range(total):
        text = ocr_pages.get(i, direct_pages[i])
        if i in ocr_pages:
            ocr_chars += len(text)
        parts.append(f"===== หน้า {i + 1}/{total} (OCR) =====")
        parts.append(text)

    meta = {
        "pages": total,
        "pages_ocr": len(need_ocr),
        "pages_text_layer": total - len(need_ocr),
        "ocr_chars": ocr_chars,
        "direct_chars": direct_chars,
        "dpi": PDF_DPI,
        "lang": OCR_LANG,
    }
    return "\n".join(parts), meta


def ocr_image(path: Path) -> tuple[str, dict]:
    text = run_tesseract(preprocess(Image.open(path))).strip()
    body = f"===== หน้า 1/1 (OCR) =====\n{text}"
    return body, {
        "pages": 1, "pages_ocr": 1, "pages_text_layer": 0,
        "ocr_chars": len(text), "direct_chars": 0,
        "dpi": PDF_DPI, "lang": OCR_LANG,
    }


def make_searchable_pdf(source: Path, target: Path) -> bool:
    """สร้าง PDF ที่ค้นหาข้อความได้ด้วย ocrmypdf (ข้ามถ้าไม่มี ocrmypdf)"""
    if source.suffix.lower() not in PDF_EXTS or not shutil.which("ocrmypdf"):
        return False
    try:
        subprocess.run(
            ["ocrmypdf", "-l", OCR_LANG, "--rotate-pages", "--deskew",
             "--skip-text", "--optimize", "1", "--quiet",
             str(source), str(target)],
            check=True, capture_output=True, text=True,
        )
        return True
    except subprocess.CalledProcessError as exc:
        log(f"  สร้าง PDF ค้นหาได้ไม่สำเร็จ: {exc.stderr.strip()[:200]}")
        return False


@dataclass
class ScanResult:
    source_name: str
    text_path: str
    raw_path: str
    meta_path: str
    archive_path: str
    pdf_path: str | None
    seconds: float


def safe_name(path: Path) -> str:
    """เก็บอักษรไทยไว้ แทนที่เฉพาะอักขระที่ทำให้ชื่อไฟล์มีปัญหา

    สระและวรรณยุกต์ไทยเป็น combining mark ซึ่ง str.isalnum() คืน False
    จึงต้องเช็กช่วงยูนิโค้ดไทยเองไม่งั้น "เซียวเฮ้ง" จะกลายเป็น "เซ_ยวเฮ_ง"
    """
    def keep(ch: str) -> bool:
        return ch.isalnum() or ch in "-_" or "฀" <= ch <= "๿"

    cleaned = "".join(ch if keep(ch) else "_" for ch in path.stem)
    return re.sub(r"_{2,}", "_", cleaned).strip("_") or "document"


def write_outputs(source: Path, raw: str, meta: dict, want_pdf: bool, started: float) -> ScanResult:
    base = f"{time.strftime('%Y%m%d-%H%M%S')}_{safe_name(source)}"
    raw_path = TEXT / f"{base}.raw.txt"
    text_path = TEXT / f"{base}.txt"
    meta_path = TEXT / f"{base}.json"
    archive_path = DONE / f"{base}{source.suffix.lower()}"

    cleaned = cleanse(raw, meta.get("pages"))
    raw_path.write_text(raw.strip() + "\n", encoding="utf-8")
    text_path.write_text(cleaned.strip() + "\n", encoding="utf-8")

    pdf_path: Path | None = None
    if want_pdf:
        candidate = TEXT / f"{base}.ocr.pdf"
        if make_searchable_pdf(source, candidate):
            pdf_path = candidate

    elapsed = round(time.time() - started, 1)
    meta_path.write_text(json.dumps({
        "source_file": source.name,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "seconds": elapsed,
        "clean_chars": len(cleaned),
        "raw_chars": len(raw),
        "searchable_pdf": pdf_path.name if pdf_path else None,
        **meta,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    shutil.move(str(source), str(archive_path))
    return ScanResult(
        source.name, str(text_path), str(raw_path), str(meta_path),
        str(archive_path), str(pdf_path) if pdf_path else None, elapsed,
    )


def process_file(path: Path, want_pdf: bool) -> ScanResult:
    started = time.time()
    working = PROCESSING / path.name
    shutil.move(str(path), str(working))
    try:
        suffix = working.suffix.lower()
        if suffix in PDF_EXTS:
            raw, meta = ocr_pdf(working)
        elif suffix in IMAGE_EXTS:
            raw, meta = ocr_image(working)
        else:
            raise ValueError(f"ไม่รองรับนามสกุล {working.suffix}")
        return write_outputs(working, raw, meta, want_pdf, started)
    except Exception as exc:
        if working.exists():
            shutil.move(str(working), str(FAILED / working.name))
        raise RuntimeError(f"{path.name}: {exc}") from exc


def iter_pending() -> Iterable[Path]:
    if not INBOX.exists():
        return
    for path in sorted(INBOX.iterdir(), key=lambda p: p.stat().st_mtime):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTS:
            yield path


def scan_once(want_pdf: bool, explicit: list[Path] | None = None) -> int:
    count = 0
    sources = explicit if explicit else list(iter_pending())
    for path in sources:
        # ไฟล์ที่ระบุเองอาจอยู่นอก inbox — ย้ายเข้ามาก่อน
        if explicit:
            if not path.exists():
                log(f"ไม่พบไฟล์ {path}")
                continue
            staged = INBOX / path.name
            if path.resolve() != staged.resolve():
                shutil.copy2(str(path), str(staged))
            path = staged
        log(f"เริ่มประมวลผล {path.name}")
        try:
            result = process_file(path, want_pdf)
            log(f"เสร็จ {result.source_name} -> {Path(result.text_path).name} ({result.seconds}s)")
            count += 1
        except Exception as exc:
            log(f"ล้มเหลว {exc}")
    return count


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="ระบบสแกน OCR หนังสือกำลังภายใน")
    parser.add_argument("files", nargs="*", type=Path, help="ไฟล์ที่จะสแกน (ไม่ใส่ = อ่านจาก scan_inbox)")
    parser.add_argument("--watch", action="store_true", help="เฝ้าโฟลเดอร์ inbox ตลอดเวลา")
    parser.add_argument("--pdf", action="store_true", help="สร้าง PDF ที่ค้นหาข้อความได้ด้วย")
    parser.add_argument("--check", action="store_true", help="ตรวจความพร้อมของระบบแล้วออก")
    args = parser.parse_args(argv)

    ensure_dirs()
    problems = check_environment()
    if args.check:
        if problems:
            for problem in problems:
                print(f"✗ {problem}")
            return 1
        print(f"✓ tesseract: {TESSERACT}")
        print(f"✓ ภาษา: {OCR_LANG} | DPI: {PDF_DPI} | เธรด: {MAX_WORKERS}")
        print(f"✓ ocrmypdf: {shutil.which('ocrmypdf') or 'ไม่มี (PDF ค้นหาได้จะถูกข้าม)'}")
        print(f"✓ โฟลเดอร์งาน: {ROOT}")
        return 0
    if problems:
        for problem in problems:
            log(f"ตรวจความพร้อมไม่ผ่าน: {problem}")
        return 1

    if not args.watch:
        processed = scan_once(args.pdf, args.files or None)
        log(f"จบรอบ: {processed} ไฟล์")
        return 0

    log(f"เริ่มเฝ้า {INBOX} (ทุก {POLL_SECONDS} วินาที)")
    while True:
        try:
            processed = scan_once(args.pdf)
            if processed:
                log(f"รอบเฝ้าเสร็จ: {processed} ไฟล์")
        except KeyboardInterrupt:
            log("หยุดการเฝ้า")
            return 0
        except Exception as exc:
            log(f"ตัวเฝ้าผิดพลาด: {exc}")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
