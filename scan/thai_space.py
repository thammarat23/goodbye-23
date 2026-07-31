# -*- coding: utf-8 -*-
"""แทรกช่องว่างคืนให้ข้อความไทยที่ติดกันเป็นพืด

ตัวคลีนรุ่นก่อนกินช่องว่างระหว่างวลีไป ทำให้ได้ข้อความแบบ

    จัดรูปเล่มเลิศชัยฮวดวิจิตรพิมพ์ครั้งแรกเดือนมิถุนายนพ.ศ.

ซึ่งอ่านยากมากและทำให้ตัวสังเคราะห์เสียงเว้นวรรคผิด

เรื่องนี้เสี่ยงกว่าการซ่อมคำ เพราะแทรกผิดที่แล้วอ่านออกเสียงเพี้ยนทันที
โดยเฉพาะชื่อคนจีนทับศัพท์ที่ถ้าโดนผ่ากลางจะกลายเป็นคนละชื่อ
("ลุ้ยซีเพ้ง" -> "ลุ้ย ซี เพ้ง")

หลักที่ใช้จึงเป็น "แทรกเฉพาะที่มั่นใจ"

  - แตะเฉพาะช่วงที่ติดกันยาวผิดปกติจริงๆ ข้อความไทยปกติไม่เว้นวรรคทุกคำ
    อยู่แล้ว ช่วงสั้นจึงไม่ใช่ความเสียหาย
  - แทรกเฉพาะรอยต่อที่ทั้งสองข้างเป็นคำในพจนานุกรม ถ้าข้างใดข้างหนึ่ง
    ไม่รู้จัก แปลว่าอาจเป็นชื่อเฉพาะ ปล่อยไว้
  - ไม่แทรกรอบคำตัวเดียว เพราะมักเป็นเศษจากการตัดคำผิด

ปิดไว้เป็นค่าเริ่มต้น ต้องสั่ง --space เอง
"""
from __future__ import annotations

import math
import os
import re
from collections import Counter

from thai_repair import _load, _tokens

# ช่วงอักษรไทยติดกันยาวเกินนี้ถือว่าช่องว่างหายไปจริง
MIN_RUN_CHARS = 40

# คำสั้นกว่านี้ไม่ใช้เป็นหลักฐานว่าตรงนั้นเป็นรอยต่อของวลี
#
# ตัวเลขนี้คือด่านกันชื่อถูกผ่ากลาง พยางค์ที่ประกอบชื่อคนจีนทับศัพท์
# หลายตัวบังเอิญเป็นคำไทยจริง ("ซี" "จู" "ไต้") กฎแค่ "สองข้างเป็นคำ"
# จึงกันไม่อยู่ ต้องบังคับความยาวด้วย
MIN_WORD_CHARS = int(os.environ.get("THAI_SPACE_MIN_WORD", "2"))

RUN_RE = re.compile(f"[฀-๿]{{{MIN_RUN_CHARS},}}")


# คู่คำที่ติดกันแน่นเกินค่านี้ถือว่าเป็นก้อนเดียว ห้ามผ่า
#
#    glue   แทรกถูกที่   ผ่ากลางชื่อ   คลุมได้
#     4.0     99.0%       16.7%      96.5%
#     3.0     99.5%        0.8%      96.5%   <- เลือกค่านี้
#     2.0     99.5%        0.8%      96.3%
#     1.0     99.5%        0.8%      94.9%
#
# ต่ำกว่า 3.0 ไม่ได้กันชื่อเพิ่มแล้ว มีแต่เสียความครอบคลุม
MIN_GLUE = float(os.environ.get("THAI_SPACE_MIN_GLUE", "3.0"))
# คู่คำต้องพบร่วมกันอย่างน้อยกี่ครั้งจึงจะเชื่อสถิติได้
MIN_PAIR_COUNT = int(os.environ.get("THAI_SPACE_MIN_PAIR", "3"))


def build_glue(text: str) -> set[tuple[str, str]]:
    """หาคู่คำที่ "ติดกันเสมอ" จากตัวหนังสือเอง แล้วห้ามแทรกช่องว่างคั่น

    ชื่อตัวละครในนิยายซ้ำเป็นร้อยครั้งทั้งเล่ม และพยางค์ที่ประกอบชื่อมักไม่
    ค่อยไปโผล่ที่อื่น เช่น "อ้อเล้งเซ็ง" ตัดคำได้ "อ้อ"+"เล้ง"+"เซ็ง" ซึ่ง
    เป็นคำในพจนานุกรมทั้งสามตัว พจนานุกรมจึงแยกไม่ออกว่านี่คือชื่อคน

    แต่ทางสถิติแยกออก ถ้า "อ้อ" ปรากฏ 200 ครั้งแล้วตามด้วย "เล้ง" ทั้ง 200
    ครั้ง แปลว่าสองคำนี้เป็นก้อนเดียวกัน ไม่ใช่สองคำที่บังเอิญอยู่ติดกัน
    วัดด้วยค่าที่บอกว่าคู่นี้อยู่ด้วยกันบ่อยกว่าที่ควรจะเป็นแค่ไหน

    ต้องคำนวณจากทั้งเล่ม ไม่ใช่ทีละบรรทัด ถึงจะมีข้อมูลพอ
    """
    counts: Counter[str] = Counter()
    pairs: Counter[tuple[str, str]] = Counter()
    total = 0
    for run in RUN_RE.findall(text):
        toks = _tokens(run)
        counts.update(toks)
        total += len(toks)
        pairs.update(zip(toks, toks[1:]))
    if total < 2:
        return set()

    glue: set[tuple[str, str]] = set()
    for (a, b), n in pairs.items():
        if n < MIN_PAIR_COUNT:
            continue
        expected = counts[a] * counts[b] / total
        if expected <= 0:
            continue
        if math.log(n / expected) >= MIN_GLUE:
            glue.add((a, b))
    return glue


def split_run(run: str, glue: set[tuple[str, str]]) -> str:
    """แทรกช่องว่างในช่วงที่ติดกัน คืนข้อความที่เว้นวรรคแล้ว"""
    words, _ = _load()
    toks = list(_tokens(run))
    out: list[str] = []
    for index, tok in enumerate(toks):
        if index == 0:
            out.append(tok)
            continue
        prev = toks[index - 1]
        confident = (
            prev in words
            and tok in words
            and len(prev) >= MIN_WORD_CHARS
            and len(tok) >= MIN_WORD_CHARS
            and (prev, tok) not in glue
        )
        out.append((" " if confident else "") + tok)
    return "".join(out)


def add_spaces(text: str) -> tuple[str, int]:
    """คืน (ข้อความที่เว้นวรรคแล้ว, จำนวนช่องว่างที่แทรก)

    รับทั้งเล่มมาทีเดียว เพราะต้องใช้สถิติจากทั้งเล่มหาว่าคู่คำไหนเป็นชื่อ
    """
    glue = build_glue(text)
    added = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal added
        spaced = split_run(match.group(0), glue)
        added += spaced.count(" ")
        return spaced

    return RUN_RE.sub(replace, text), added


def count_runs(text: str) -> int:
    return len(RUN_RE.findall(text))
