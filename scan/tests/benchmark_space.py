#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""วัดความแม่นยำของการแทรกช่องว่างคืน

ข้อความทดสอบสร้างจากการต่อคำเข้าด้วยกันเอง จึงรู้ตำแหน่งรอยต่อที่ถูกต้อง
ทุกจุดอยู่แล้ว ใช้เป็นเฉลยได้ตรงๆ ไม่ต้องเดา

วัดสามอย่าง
  แทรกถูกที่   ช่องว่างที่แทรกไป ตรงรอยต่อคำจริงกี่ %
  ผ่ากลางชื่อ  ชื่อทับศัพท์ถูกแทรกช่องว่างกลางชื่อกี่ %   <- ต้องเป็น 0
  คลุมได้      รอยต่อจริงทั้งหมด ถูกแทรกไปกี่ %

"แทรกถูกที่" กับ "ผ่ากลางชื่อ" สำคัญกว่า "คลุมได้" มาก เพราะเว้นวรรคน้อยไป
แค่อ่านยากเท่าเดิม แต่เว้นผิดที่ทำให้อ่านออกเสียงเพี้ยนไปเลย

ใช้:
    python3 scan/tests/benchmark_space.py --lines 3000
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from thai_space import add_spaces  # noqa: E402
from benchmark import build_sentences_with_spans  # noqa: E402


def measure(spaced: str, boundaries: set[int], name_spans: list[tuple[int, int]]):

    # ตำแหน่งช่องว่างที่แทรก แปลงกลับเป็นดัชนีบนข้อความต้นฉบับ
    inserted: list[int] = []
    original_index = 0
    for ch in spaced:
        if ch == " ":
            inserted.append(original_index)
        else:
            original_index += 1

    correct = sum(1 for p in inserted if p in boundaries)
    split_names = sum(
        1 for start, end in name_spans
        if any(start < p < end for p in inserted)
    )
    return len(inserted), correct, split_names, len(boundaries)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="วัดการแทรกช่องว่างคืน")
    parser.add_argument("--lines", type=int, default=3000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)

    print(f"สร้างข้อความทดสอบ {args.lines:,} บรรทัด...")
    samples = build_sentences_with_spans(args.lines, args.seed)

    total_inserted = total_correct = total_names = total_split = 0
    total_boundaries = 0
    started = time.time()

    # ต้องส่งทั้งเล่มทีเดียว เพราะตัวแทรกใช้สถิติจากทั้งเล่มหาชื่อตัวละคร
    document = "\n".join(text for text, _b, _n in samples)
    spaced_doc, _added = add_spaces(document)
    spaced_lines = spaced_doc.split("\n")

    for i, ((_text, boundaries, name_spans), spaced) in enumerate(
        zip(samples, spaced_lines), 1
    ):
        ins, cor, split, bounds = measure(spaced, boundaries, name_spans)
        total_inserted += ins
        total_correct += cor
        total_split += split
        total_names += len(name_spans)
        total_boundaries += bounds
        if i % 500 == 0:
            print(f"  {i:,}/{args.lines:,}")

    print(f"\nใช้เวลา {time.time() - started:.0f} วินาที\n")

    def pct(a: int, b: int) -> str:
        return f"{a / b * 100:5.1f}%  ({a:,}/{b:,})" if b else "     -"

    print(f"แทรกถูกที่   {pct(total_correct, total_inserted)}")
    print(f"ผ่ากลางชื่อ  {pct(total_split, total_names)}   <- ต้องเป็น 0")
    print(f"คลุมได้      {pct(total_correct, total_boundaries)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
