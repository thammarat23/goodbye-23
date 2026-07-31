#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""รันชุดทดสอบตัวซ่อมข้อความไทย

วัดสองอย่างแยกกัน เพราะสองอย่างนี้ไม่เท่ากัน
  ซ่อมได้    = แก้ข้อความเสียให้ถูก
  ทำของพัง   = แก้ข้อความที่ถูกอยู่แล้วให้เสีย  <- ร้ายแรงกว่ามาก ต้องเป็นศูนย์
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from fix_ocr_text import repair as safe_repair  # noqa: E402
from thai_repair import repair_text  # noqa: E402


def load(path: Path) -> list[tuple[str, str]]:
    cases = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        bad, _, good = line.partition("\t")
        if good:
            cases.append((bad.strip(), good.strip()))
    return cases


def main() -> int:
    cases = load(HERE / "damaged_samples.tsv")
    fixed_ok = fixed_total = 0
    broke: list[tuple[str, str]] = []
    missed: list[tuple[str, str, str]] = []

    for bad, good in cases:
        pre, _ = safe_repair(bad)
        got, _fixes, _unsure = repair_text(pre)
        already_correct = bad == good

        if already_correct:
            if got != good:
                broke.append((bad, got))
        else:
            fixed_total += 1
            if got == good:
                fixed_ok += 1
            else:
                missed.append((bad, got, good))

    print(f"ซ่อมได้     {fixed_ok}/{fixed_total}")
    print(f"ทำของพัง    {len(broke)}   (ต้องเป็น 0)")

    if broke:
        print("\n!! ทำของที่ถูกอยู่แล้วพัง")
        for bad, got in broke:
            print(f"   {bad}\n   -> {got}")
    if missed:
        print("\nยังซ่อมไม่ได้")
        for bad, got, good in missed:
            print(f"   {bad}\n   ได้    {got}\n   ควรได้ {good}")

    return 1 if broke else 0


if __name__ == "__main__":
    raise SystemExit(main())
