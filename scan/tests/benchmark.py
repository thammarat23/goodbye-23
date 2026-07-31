#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""วัดความแม่นยำของตัวซ่อมในระดับที่เชื่อถือได้

ชุดทดสอบมือมีแค่ไม่กี่เคส เชื่อเป็นตัวเลขจริงไม่ได้ ตัวนี้จึงสร้างข้อความ
จำนวนมาก ทำให้เสียตามรูปแบบที่พบในไฟล์จริง แล้ววัดสามอย่าง

  กู้คืนได้    ข้อความที่เสีย ซ่อมกลับมาถูกต้องกี่ %
  ทำของพัง    ข้อความที่ถูกอยู่แล้ว ถูกซ่อมจนเสียกี่ %   <- ตัวที่สำคัญที่สุด
  ชื่อรอด      ชื่อทับศัพท์ที่ไม่มีในพจนานุกรม รอดกี่ %

ตัวที่สองกับสามสำคัญกว่าตัวแรก เพราะกู้ไม่ได้ยังมีต้นฉบับให้กลับไปดู
แต่ถ้าทำของดีพัง ความเสียหายกระจายไปทั้งเล่มโดยไม่มีใครรู้

ใช้:
    python3 scan/tests/benchmark.py --lines 2000
    python3 scan/tests/benchmark.py --lines 20000 --seed 7
"""
from __future__ import annotations

import argparse
import random
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from thai_repair import repair_line  # noqa: E402
from fix_ocr_text import repair as safe_repair  # noqa: E402

from pythainlp.corpus.common import thai_words  # noqa: E402
from pythainlp.corpus import tnc  # noqa: E402

# ── สร้างข้อความต้นฉบับที่ "ถูกต้อง" ────────────────────────────────────────

# พยางค์ที่ใช้ประกอบชื่อคนจีนทับศัพท์แบบที่พบในนิยายกำลังภายใน
NAME_SYLLABLES = [
    "เล่ง", "สุ้น", "ลุ้ย", "ซี", "เพ้ง", "จู", "ก้วะ", "แช", "อ้อ", "เซ็ง",
    "เอี้ย", "ฮุ้น", "เจ๊ก", "เตียว", "บู๊", "เซียว", "ฮื้อ", "ยี้", "ก๋วย",
    "เจ๋ง", "อึ้ง", "ย้ง", "ตั้ง", "เม่ง", "ไต้", "อุ้ย", "เสี่ยว", "หลิ่ว",
]


def make_name(rng: random.Random) -> str:
    return "".join(rng.choice(NAME_SYLLABLES) for _ in range(rng.randint(2, 4)))


def build_sentences(n: int, rng: random.Random) -> list[tuple[str, set[str]]]:
    """คืน [(ประโยค, ชุดชื่อที่อยู่ในประโยคนั้น)]"""
    freq = dict(tnc.word_freqs())
    # ต้อง sorted() เพราะ thai_words() คืน set ซึ่งลำดับการวนเปลี่ยนทุกครั้งที่
    # รันโพรเซสใหม่ (hash randomization) ถ้าไม่ตรึงลำดับ ต่อให้ใส่ seed เดียวกัน
    # ก็ได้ข้อความทดสอบคนละชุด เอาผลมาเทียบกันไม่ได้
    words = sorted(w for w in thai_words() if re.fullmatch("[฀-๿]+", w) and len(w) > 1)
    weights = [freq.get(w, 1) for w in words]

    out = []
    for _ in range(n):
        picked = rng.choices(words, weights=weights, k=rng.randint(6, 14))
        names: set[str] = set()
        # แทรกชื่อทับศัพท์เข้าไปในบางประโยค เหมือนบทสนทนาในนิยายจริง
        if rng.random() < 0.5:
            name = make_name(rng)
            names.add(name)
            picked.insert(rng.randrange(len(picked)), name)
        out.append(("".join(picked), names))
    return out


# ── ทำให้เสียตามรูปแบบที่พบในไฟล์จริง ──────────────────────────────────────

def corrupt(text: str, rng: random.Random) -> str:
    """จำลองความเสียหายที่ OCR ทำจริงกับไฟล์ในโฟลเดอร์ "หนังสือรอแก้"

    รูปแบบที่สังเกตได้จากกระบี่เหนือกระบี่ เล่ม 1-2
      นน -> นั้น    เป็นนักเขียน -> เป็นั้นักเขียน
      ยง -> ยัง     เสียง -> เสียัง
      ำ  -> ํา      จำหน่าย -> จําหน่าย (นิคหิต+สระอา)
      ำ  -> ้า      ประจำ -> ประจ้า, น้ำเสียง -> น้าเสียง
    """
    if "นน" in text and rng.random() < 0.8:
        text = text.replace("นน", "นั้น", 1)
    if "ยง" in text and rng.random() < 0.8:
        text = text.replace("ยง", "ยัง", 1)
    if "ำ" in text and rng.random() < 0.5:
        text = text.replace("ำ", "ํา", 1)
    elif "ำ" in text and rng.random() < 0.5:
        text = text.replace("ำ", "้า", 1)
    return text


def run_repair(text: str) -> str:
    pre, _ = safe_repair(text)
    fixed, _f, _u = repair_line(pre)
    return fixed


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="วัดความแม่นยำตัวซ่อมข้อความไทย")
    parser.add_argument("--lines", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args(argv)

    rng = random.Random(args.seed)
    print(f"สร้างข้อความทดสอบ {args.lines:,} บรรทัด (seed {args.seed})...")
    sentences = build_sentences(args.lines, rng)

    recovered = corrupted_total = 0
    broken = clean_total = 0
    names_total = names_survived = 0
    started = time.time()

    for i, (clean, names) in enumerate(sentences, 1):
        damaged = corrupt(clean, rng)

        if damaged != clean:
            corrupted_total += 1
            if run_repair(damaged) == clean:
                recovered += 1
        else:
            clean_total += 1
            if run_repair(clean) != clean:
                broken += 1

        for name in names:
            names_total += 1
            if name in run_repair(damaged):
                names_survived += 1

        if i % 500 == 0:
            rate = i / (time.time() - started)
            print(f"  {i:,}/{args.lines:,}  ({rate:.0f} บรรทัด/วินาที)")

    elapsed = time.time() - started
    print(f"\nใช้เวลา {elapsed:.0f} วินาที ({args.lines / elapsed:.0f} บรรทัด/วินาที)\n")

    def pct(a: int, b: int) -> str:
        return f"{a / b * 100:5.1f}%  ({a:,}/{b:,})" if b else "     -"

    print(f"กู้คืนได้   {pct(recovered, corrupted_total)}")
    print(f"ทำของพัง   {pct(broken, clean_total)}   <- ยิ่งต่ำยิ่งดี")
    print(f"ชื่อรอด     {pct(names_survived, names_total)}   <- ยิ่งสูงยิ่งดี")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
