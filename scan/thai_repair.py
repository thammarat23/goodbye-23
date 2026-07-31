# -*- coding: utf-8 -*-
"""ซ่อมคำไทยที่ OCR ทำเสีย โดยใช้พจนานุกรมและความถี่คำเป็นตัวตัดสิน

ความเสียหายที่พบในไฟล์จริง (โฟลเดอร์ "หนังสือรอแก้") คือ OCR แทรกสระหรือ
วรรณยุกต์เกินเข้ามากลางคำ

    เป็นนักเขียนนามโรจน์   ->  เป็นั้นักเขียนั้นามโรจน์
    ถนนพระรามสี่          ->  ถนั้นพระรามสี่
    มีชื่อเสียงกระเดื่อง    ->  มีชื่อเสียังกระเดื่อง

ปัญหาคือรูปที่เพี้ยนมีหน้าตาเหมือนคำไทยที่ถูกต้อง ("นั้น" "ยัง" ล้วนเป็นคำจริง)
จะแทนที่ตรงๆ ทั้งไฟล์ไม่ได้ เพราะจะพังคำที่ถูกอยู่แล้ว

หลักความปลอดภัยของโมดูลนี้
    แก้ก็ต่อเมื่อพิสูจน์ได้ว่า ก่อนแก้ไม่ใช่คำในพจนานุกรม และหลังแก้เป็นคำจริง
    ทุกตัว ถ้าพิสูจน์ไม่ได้จะไม่แตะ แล้วรายงานไว้ให้คนตัดสินแทน

    ผลพลอยได้ที่สำคัญคือชื่อคนจีนทับศัพท์ซึ่งมีเต็มไปหมดในนิยายกำลังภายใน
    ("จูก้วะแชสุ้น" "ลุ้ยซีเพ้ง" "เล่งสุ้น") ไม่มีในพจนานุกรมทั้งก่อนและหลัง
    จึงถูกปล่อยไว้เสมอ ไม่มีทางถูกแก้พลาด
"""
from __future__ import annotations

import math
import re
from functools import lru_cache
from itertools import combinations

from pythainlp.tokenize import word_tokenize
from pythainlp.corpus.common import thai_words

THAI_RE = re.compile("[฀-๿]")
# เครื่องหมายที่ OCR มักแทรกเกิน (สระอั ไม้เอก-จัตวา ไม้ไต่คู้)
MARKS = "ั่้๊๋็"
MARK_RE = re.compile(f"[{MARKS}]")

# ยาวเกินนี้ไม่ลองซ่อม กันการรวมคำข้ามวลีจนความหมายเพี้ยน
MAX_WINDOW_CHARS = 18
# ลบเครื่องหมายได้มากสุดกี่ตัวต่อหนึ่งจุด
MAX_REMOVALS = 2

# สั้นกว่านี้ไม่ซ่อม เพราะนิยายกำลังภายในเต็มไปด้วยคำทับศัพท์สั้นๆ ที่ไม่มีใน
# พจนานุกรม เผลอซ่อมแล้วจะได้คำจริงที่ผิดความหมาย
#
# เคสจริงที่เจอ: "ได้หวัน" (ที่จริงคือ ไต้หวัน แต่ OCR อ่าน ต เป็น ด)
# ตัว "หวัน" ไม่มีในพจนานุกรม ถ้าปล่อยให้ซ่อมจะกลายเป็น "หวน" ซึ่งเป็นคำจริง
# แต่ความหมายคนละเรื่อง กลายเป็นทำของเสียให้เสียหนักกว่าเดิม
MIN_CHUNK_CHARS = 5

# เศษสระ/วรรณยุกต์ที่ลอยอยู่โดยไม่มีพยัญชนะเกาะ เป็นขยะแน่นอน ลบได้เลย
ORPHAN_MARKS = re.compile(f"^[{MARKS}ะ-ฺ็-๎]+$")

_WORDS: set[str] | None = None
_FREQ: dict[str, int] | None = None


def _load() -> tuple[set[str], dict[str, int]]:
    """คลังคำ = พจนานุกรมหลักของ pythainlp เท่านั้น

    เคยลองขยายคลังด้วยคำจากคลังความถี่ TNC เพื่อกันคำเฉพาะอย่าง "หวัน"
    (จาก ไต้หวัน) ไม่ให้ถูกซ่อมผิด แต่ผลออกมาแย่ลงชัดเจน เพราะคลังความถี่
    มีเศษคำปนอยู่มาก พอรับ "กวะแช" "แลว" "สุน" เป็นคำจริง ตัวซ่อมก็เอาไป
    ใช้ยืนยันผลลัพธ์ผิดๆ จน "จูก้วะแชสุ้น" และ "ล้วนแล้วแต่" พังทั้งคู่
    ใช้พจนานุกรมหลักอย่างเดียวปลอดภัยกว่า
    """
    global _WORDS, _FREQ
    if _WORDS is None:
        _WORDS = set(thai_words())
        try:
            from pythainlp.corpus import tnc
            _FREQ = dict(tnc.word_freqs())
        except Exception:
            _FREQ = {}
    return _WORDS, _FREQ


def is_thai(token: str) -> bool:
    return bool(THAI_RE.search(token))


@lru_cache(maxsize=200_000)
def _tokens(text: str) -> tuple[str, ...]:
    return tuple(word_tokenize(text, engine="newmm"))


def all_known(text: str) -> bool:
    words, _ = _load()
    return all(t in words for t in _tokens(text) if is_thai(t))


def plausibility(text: str) -> float:
    """คะแนนความน่าเป็นข้อความจริง = ผลรวม log ความถี่ของคำที่ประกอบขึ้น

    ใช้แยกกรณีที่ผลลัพธ์เป็นคำจริงทั้งคู่ เช่น "ถนน" (พบ 8,632 ครั้ง) กับ
    "ถนัน" (พบ 1 ครั้ง) ซึ่งถ้าดูแค่ "เป็นคำไหม" จะตัดสินไม่ได้
    """
    _, freq = _load()
    return sum(math.log(freq.get(t, 0) + 1) for t in _tokens(text) if is_thai(t))


def _variants(chunk: str):
    """ผลิตตัวเลือกการซ่อม: ลบเครื่องหมายที่แทรกเกิน และแก้ ้า ที่ควรเป็น ำ"""
    positions = [m.start() for m in MARK_RE.finditer(chunk)]
    for n in range(1, MAX_REMOVALS + 1):
        for combo in combinations(positions, n):
            drop = set(combo)
            yield "".join(c for i, c in enumerate(chunk) if i not in drop)
    # OCR อ่านสระอำเป็นไม้โท+สระอาบ่อยมาก เช่น ประจ้า -> ประจำ
    if "้า" in chunk:
        yield chunk.replace("้า", "ำ")
    if "ํา" in chunk:
        yield chunk.replace("ํา", "ำ")


def repair_line(line: str) -> tuple[str, list[tuple[str, str]], list[str]]:
    """คืน (บรรทัดที่ซ่อมแล้ว, รายการที่แก้, รายการที่น่าสงสัยแต่ไม่กล้าแก้)"""
    if not is_thai(line):
        return line, [], []

    words, _ = _load()
    toks = list(_tokens(line))
    out: list[str] = []
    fixes: list[tuple[str, str]] = []
    unsure: list[str] = []

    i = 0
    while i < len(toks):
        token = toks[i]
        if not is_thai(token) or token in words:
            out.append(token)
            i += 1
            continue

        # เศษสระ/วรรณยุกต์ลอยเดี่ยว ไม่ต้องพิสูจน์อะไร ทิ้งได้เลย
        if ORPHAN_MARKS.match(token):
            fixes.append((token, ""))
            i += 1
            continue

        # จุดเสียมักคาบเกี่ยวคำที่พจนานุกรมรู้จัก ("ถ" + "นั้น" ที่จริงคือ "ถนน")
        # จึงต้องขยายหน้าต่างออกไปทีละคำจนกว่าจะพิสูจน์ได้
        best: tuple[str, int, float] | None = None
        for end in range(i + 1, len(toks) + 1):
            window = "".join(toks[i:end])
            if len(window) > MAX_WINDOW_CHARS:
                break
            if len(window) >= MIN_CHUNK_CHARS:
                for cand in _variants(window):
                    if cand != window and all_known(cand):
                        scored = plausibility(cand)
                        if best is None or scored > best[2]:
                            best = (cand, end, scored)
            if best:
                break

        if best:
            cand, end, _score = best
            out.append(cand)
            fixes.append(("".join(toks[i:end]), cand))
            i = end
        else:
            out.append(token)
            if MARK_RE.search(token) and len(token) > 2:
                unsure.append(token)
            i += 1

    return "".join(out), fixes, unsure


def repair_text(text: str) -> tuple[str, list[tuple[str, str]], list[str]]:
    lines, fixes, unsure = [], [], []
    for line in text.split("\n"):
        fixed, f, u = repair_line(line)
        lines.append(fixed)
        fixes.extend(f)
        unsure.extend(u)
    return "\n".join(lines), fixes, unsure
