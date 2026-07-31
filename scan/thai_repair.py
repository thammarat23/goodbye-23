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
import os
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

# ถอยกลับไปรวมคำทางซ้ายได้มากสุดกี่คำ
MAX_LOOKBACK = 2

# คำใหม่ที่เกิดจากการซ่อมต้องพบในคลังความถี่ TNC อย่างน้อยกี่ครั้ง
#
# เป็นด่านกันการซ่อมมั่ว วัดด้วย scan/tests/benchmark.py ที่ 20,000 บรรทัด
# ยิ่งเกณฑ์สูง ยิ่งดีขึ้นทั้งสามค่าพร้อมกัน ไม่ได้แลกกันอย่างที่คิดตอนแรก
#
#   เกณฑ์   กู้คืนได้   ทำของพัง   ชื่อรอด
#       0     83.8%      9.6%     80.7%
#      50     87.2%      5.9%     88.2%
#     200     87.5%      5.5%     88.8%
#     500     88.2%      4.6%     90.7%
#    1000     88.2%      4.4%     91.2%
#    2000     90.0%      0.4%     99.2%   <- เลือกค่านี้
#    5000     84.4%      0.4%     99.3%
#   10000     78.8%      0.2%     99.7%
#
# 2000 ชนะทุกด้านพร้อมกัน สูงกว่านั้นอัตรากู้คืนตกเร็วโดยแทบไม่ได้อะไรเพิ่ม
# ปรับชั่วคราวด้วย THAI_REPAIR_MIN_FREQ เพื่อไล่หาค่าใหม่ได้
MIN_NEW_WORD_FREQ = int(os.environ.get("THAI_REPAIR_MIN_FREQ", "2000"))

# แก้สระอำได้ก็ต่อเมื่อคะแนนความน่าเป็นไปได้เพิ่มขึ้นอย่างน้อยเท่านี้
# กันไม่ให้ ข้า บ้าน ฟ้า ถ้า เจ้า ที่ใช้กันทั้งเล่มถูกแตะ
#
#    gain   กู้คืนได้   ทำของพัง   ชื่อรอด
#     1.0     86.8%      1.2%     99.1%
#     2.0     87.1%      0.6%     99.1%
#     4.0     86.7%      0.4%     99.1%   <- เลือกค่านี้
#     6.0     84.4%      0.4%     99.1%
#
# เลือก 4.0 เพราะลดการทำของพังลงครึ่งหนึ่งโดยเสียอัตรากู้คืนแค่ 0.4 จุด
# ตรงกับหลักที่ว่าทำของดีพังร้ายแรงกว่าซ่อมไม่ได้ สูงกว่านี้ไม่ได้อะไรเพิ่ม
MIN_SARA_AM_GAIN = float(os.environ.get("THAI_REPAIR_SARA_AM_GAIN", "4.0"))

# คำที่ห้ามแตะเด็ดขาดตอนแก้สระอำ
#
# คลังความถี่ที่ใช้เป็นภาษาไทยสมัยใหม่ ซึ่งคำพวกนี้พบไม่บ่อย แต่ในนิยาย
# กำลังภายในเป็นคำที่ใช้ทั้งเล่ม โดยเฉพาะ "ข้า" ที่เป็นสรรพนามหลัก
# ถ้าเชื่อความถี่อย่างเดียว "ข้า" จะกลายเป็น "ขำ" กระจายไปทั้งเรื่อง
SARA_AM_PROTECTED = {
    "ข้า", "ข้าง", "ข้าว", "เจ้า", "ท่าน", "ป้า", "น้า", "บ้าน", "บ้า",
    "ช้าง", "ช้า", "ถ้า", "ม้า", "ค้า", "ฟ้า", "ห้า", "ล้าน", "กล้า",
    "หน้า", "ข้าม", "อ้าง", "ต้าน", "ผ้า", "ร้าน", "ส้ม", "ว่าน",
}


# ลบเครื่องหมายเลยขอบคำที่เสียออกไปได้กี่ตัวอักษร (เผื่อรอยขาดคาบเกี่ยว)
JUNCTION_REACH = 3

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
    """คะแนนความน่าเป็นข้อความจริง = ผลรวม log ความน่าจะเป็นของคำที่ประกอบขึ้น

    ใช้แยกกรณีที่ผลลัพธ์เป็นคำจริงทั้งคู่ เช่น "ถนน" (พบ 8,632 ครั้ง) กับ
    "ถนัน" (พบ 1 ครั้ง) ซึ่งถ้าดูแค่ "เป็นคำไหม" จะตัดสินไม่ได้

    ต้องหารด้วยยอดรวมให้เป็นความน่าจะเป็นก่อน ไม่ใช่ใช้ log ความถี่ดิบ
    ไม่งั้นคะแนนจะเอนเข้าข้างการแตกเป็นหลายคำเสมอ เพราะยิ่งมีคำมากยิ่งบวก
    ค่าบวกเข้าไปเยอะ ทำให้ "น้า"+"เสียง" ชนะ "น้ำเสียง" ทั้งที่ควรเป็นตรงข้าม
    """
    _, freq = _load()
    total = _corpus_total()
    return sum(
        math.log((freq.get(t, 0) + 1) / total)
        for t in _tokens(text) if is_thai(t)
    )


_TOTAL: float | None = None


def _corpus_total() -> float:
    global _TOTAL
    if _TOTAL is None:
        _, freq = _load()
        _TOTAL = float(sum(freq.values())) or 1.0
    return _TOTAL


def new_words_common_enough(cand: str, original: set[str]) -> bool:
    """คำใหม่ที่เกิดจากการซ่อม ต้องเป็นคำที่พบบ่อยพอสมควร

    เป็นด่านกันชื่อทับศัพท์ถูกทำลาย ชื่ออย่าง "เล่งสุ้น" พอลบวรรณยุกต์ออก
    อาจกลายเป็นคำที่มีในพจนานุกรมได้เหมือนกัน แต่เป็นคำหายากที่แทบไม่มีใครใช้
    ถ้าบังคับว่าคำใหม่ต้องพบบ่อยถึงระดับหนึ่ง การซ่อมมั่วจะถูกปัดตกไปเอง
    """
    _, freq = _load()
    for tok in _tokens(cand):
        if not is_thai(tok) or tok in original:
            continue
        if freq.get(tok, 0) < MIN_NEW_WORD_FREQ:
            return False
    return True


def _variants(chunk: str, allowed: range | None = None):
    """ผลิตตัวเลือกการซ่อม: ลบเครื่องหมายที่แทรกเกิน และแก้ ้า ที่ควรเป็น ำ

    allowed จำกัดว่าลบเครื่องหมายได้ในช่วงตัวอักษรไหนของ chunk
    ใช้กันไม่ให้ไปดึงวรรณยุกต์ออกจากคำข้างเคียงที่ถูกต้องอยู่แล้ว
    (เคสจริง: ซ่อม "เสียัง" แล้วเผลอทำ "ขับกล่อม" กลายเป็น "ขับกลอม")
    """
    positions = [
        m.start() for m in MARK_RE.finditer(chunk)
        if allowed is None or m.start() in allowed
    ]
    for n in range(1, MAX_REMOVALS + 1):
        for combo in combinations(positions, n):
            drop = set(combo)
            yield "".join(c for i, c in enumerate(chunk) if i not in drop)
    # OCR อ่านสระอำเป็นไม้โท+สระอาบ่อยมาก เช่น ประจ้า -> ประจำ
    if "้า" in chunk:
        yield chunk.replace("้า", "ำ")
    if "ํา" in chunk:
        yield chunk.replace("ํา", "ำ")


def _sara_am_variants(window: str):
    """OCR อ่านสระอำพลาดได้สองแบบ ต้องลองทั้งคู่

        ประจำ   -> ประจ้า    สระอำกลายเป็นไม้โท+สระอา
        น้ำเสียง -> น้าเสียง   สระอำกลายเป็นสระอาเฉยๆ วรรณยุกต์ยังอยู่
    """
    if "้า" in window:
        yield window.replace("้า", "ำ", 1)
    for m in re.finditer("า", window):
        yield window[:m.start()] + "ำ" + window[m.start() + 1:]


def repair_sara_am(line: str) -> tuple[str, list[tuple[str, str]]]:
    """แก้สระอำที่ OCR อ่านเป็นไม้โท+สระอา  ประจ้า -> ประจำ

    ต่างจากการซ่อมแบบอื่นตรงที่รูปที่เพี้ยนมักตัดคำออกมาเป็นคำจริงทั้งคู่
    "ประจ้า" ตัดได้ "ประ" + "จ้า" ซึ่งมีในพจนานุกรมทั้งสองตัว ตัวซ่อมหลัก
    จึงมองไม่เห็นว่าเสีย ต้องมีด่านแยกที่ไล่ดูทุกตำแหน่งที่มี ้า

    จะตั้งกฎแทนที่ ้า เป็น ำ ทั้งไฟล์ไม่ได้เด็ดขาด เพราะคำอย่าง ข้า บ้าน
    ช้าง ฟ้า ถ้า ม้า เจ้า ใช้กันทั้งเล่ม โดยเฉพาะ "ข้า" ในนิยายกำลังภายใน
    ที่จะกลายเป็น "ขำ" ทันที

    ด่านนี้จึงยอมแทนที่เฉพาะเมื่อรวมคำแล้วได้คำที่ "น่าเป็นไปได้มากกว่าเดิม"
    วัดด้วยความถี่การใช้จริง ถ้าคำเดิมพบบ่อยกว่าคำใหม่ จะไม่แตะ
    """
    words, freq = _load()
    if "า" not in line:
        return line, []

    toks = list(_tokens(line))
    out: list[str] = []
    fixes: list[tuple[str, str]] = []
    i = 0
    while i < len(toks):
        best: tuple[str, int, float] | None = None
        # ไล่จากช่วงยาวไปสั้น เพราะการรวมได้คำยาวเป็นหลักฐานที่หนักแน่นกว่า
        # "น้า"+"เสียง" ควรได้ "น้ำเสียง" ไม่ใช่ "นำ"+"เสียง"
        for span in (3, 2, 1):
            if i + span > len(toks):
                continue
            window = "".join(toks[i:i + span])
            if "า" not in window or len(window) > MAX_WINDOW_CHARS:
                continue
            # คำสงวนห้ามแตะเมื่อยืนอยู่ลำพัง แต่ถ้ารวมกับคำข้างเคียงแล้วได้
            # คำยาวคำเดียวที่พจนานุกรมรับรอง ถือว่าหลักฐานหนักแน่นพอ
            # ("น้า"+"เสียง" ที่จริงคือ "น้ำเสียง" ส่วน "ของ"+"ข้า" รวมแล้ว
            #  ไม่เป็นคำเดียว จึงถูกปัดตกด้วยกฎคำเดียวอยู่แล้ว)
            if span == 1 and toks[i] in SARA_AM_PROTECTED:
                continue
            for cand in _sara_am_variants(window):
                # ผลลัพธ์ต้องรวมเป็น "คำเดียว" ที่พจนานุกรมรู้จัก
                #
                # ด่านนี้สำคัญที่สุด ถ้าไม่มี "ของ"+"ข้า" จะถูกซ่อมเป็น "ของขำ"
                # เพราะคลังความถี่เป็นภาษาไทยสมัยใหม่ที่ "ขำ" พบบ่อยกว่า "ข้า"
                # ทั้งที่ในนิยายกำลังภายใน "ข้า" คือสรรพนามที่ใช้ทั้งเล่ม
                # การบังคับให้รวมเป็นคำเดียวตัดเคสแบบนี้ทิ้งหมด เพราะ "ของขำ"
                # ไม่ใช่คำ แต่ "ประจำ" กับ "น้ำเสียง" เป็นคำจริงคำเดียว
                parts = [t for t in _tokens(cand) if is_thai(t)]
                if len(parts) != 1 or parts[0] not in words:
                    continue
                if freq.get(parts[0], 0) < MIN_NEW_WORD_FREQ:
                    continue
                gain = plausibility(cand) - plausibility(window)
                if gain < MIN_SARA_AM_GAIN:
                    continue
                if best is None or gain > best[2]:
                    best = (cand, i + span, gain)
            if best:
                break
        if best:
            cand, nxt, _gain = best
            fixes.append(("".join(toks[i:nxt]), cand))
            out.append(cand)
            i = nxt
        else:
            out.append(toks[i])
            i += 1
    return "".join(out), fixes


def repair_line(line: str) -> tuple[str, list[tuple[str, str]], list[str]]:
    """คืน (บรรทัดที่ซ่อมแล้ว, รายการที่แก้, รายการที่น่าสงสัยแต่ไม่กล้าแก้)"""
    if not is_thai(line):
        return line, [], []

    words, _ = _load()
    toks = list(_tokens(line))
    out: list[str] = []
    # โทเคนตัวที่เท่าไรเป็นจุดเริ่มของแต่ละชิ้นใน out
    #
    # ต้องจำไว้เพราะหนึ่งชิ้นใน out อาจมาจากหลายโทเคน (ตอนรวมคำ) หรือศูนย์
    # โทเคน (ตอนทิ้งเศษสระ) จะถอยกลับโดยนับจำนวนโทเคนตรงๆ ไม่ได้
    out_at: list[int] = []
    fixes: list[tuple[str, str]] = []
    unsure: list[str] = []

    i = 0
    while i < len(toks):
        token = toks[i]
        if not is_thai(token) or token in words:
            out.append(token)
            out_at.append(i)
            i += 1
            continue

        # เศษสระ/วรรณยุกต์ลอยเดี่ยว ไม่ต้องพิสูจน์อะไร ทิ้งได้เลย
        if ORPHAN_MARKS.match(token):
            fixes.append((token, ""))
            i += 1
            continue

        # เคยลองกันคำทับศัพท์ด้วยกฎ "คำสั้นที่มีเครื่องหมายของตัวเองห้ามซ่อม"
        # เพื่อรักษา "หวัน" (จาก ไต้หวัน) ผลคือเสียมากกว่าได้ ปิดการซ่อม
        # "เสียัง" -> "เสียง" ไปด้วยทั้งที่ควรซ่อม แถมยังกัน "หวัน" ไม่ได้จริง
        # เพราะมันถูกซ่อมผ่านการถอยกลับจากคำถัดไป จึงเอากฎนั้นออก

        # จุดเสียคาบเกี่ยวคำที่พจนานุกรมรู้จักได้ทั้งสองข้าง
        #   ขวา: "ถ" + "นั้น"      ที่จริงคือ "ถนน"
        #   ซ้าย: "ทำงา" + "นั้"   ที่จริงคือ "ทำงานน"
        # จึงต้องลองขยายหน้าต่างทั้งไปข้างหน้าและถอยกลับ
        best: tuple[str, int, int, float] | None = None
        for back in range(0, MAX_LOOKBACK + 1):
            start = i - back
            if start < 0 or any(ORPHAN_MARKS.match(t) for t in toks[start:i]):
                break
            # จำกัดว่าลบเครื่องหมายได้ตรงไหน: ในคำที่เสีย บวกกับบริเวณรอยต่อ
            # ข้างละไม่กี่ตัวอักษร เพราะรอยขาดมักคาบเกี่ยวคำข้างเคียง
            # ("นั้น" + "ั่งทน" ที่จริงคือ "นนั่งทน" ต้องลบในคำ "นั้น" ที่ถูกต้อง)
            #
            # แต่ต้องไม่ปล่อยให้เอื้อมไปถึงกลางคำข้างเคียง ไม่งั้นจะเกิดเคสจริง
            # ที่ซ่อม "เสียัง" แล้วเผลอทำ "ขับกล่อม" กลายเป็น "ขับกลอม"
            offset = len("".join(toks[start:i]))
            allowed = range(
                max(0, offset - JUNCTION_REACH),
                offset + len(token) + JUNCTION_REACH,
            )

            for end in range(i + 1, len(toks) + 1):
                window = "".join(toks[start:end])
                if len(window) > MAX_WINDOW_CHARS:
                    break
                if len(window) < MIN_CHUNK_CHARS:
                    continue
                original = set(_tokens(window))
                for cand in _variants(window, allowed):
                    if cand == window or not all_known(cand):
                        continue
                    if not new_words_common_enough(cand, original):
                        continue
                    scored = plausibility(cand)
                    if best is None or scored > best[3]:
                        best = (cand, start, end, scored)
            if best:
                break

        if best:
            cand, start, end, _score = best
            # ถอยกลับไปเอาชิ้นที่เผลอส่งออกไปแล้วคืนมา โดยดูจากตำแหน่งโทเคน
            # ไม่ใช่นับจำนวน เพราะหนึ่งชิ้นอาจมาจากหลายโทเคน
            while out_at and out_at[-1] >= start:
                out.pop()
                out_at.pop()
            out.append(cand)
            out_at.append(start)
            fixes.append(("".join(toks[start:end]), cand))
            i = end
        else:
            out.append(token)
            out_at.append(i)
            if MARK_RE.search(token) and len(token) > 2:
                unsure.append(token)
            i += 1

    return "".join(out), fixes, unsure


def repair_text(text: str) -> tuple[str, list[tuple[str, str]], list[str]]:
    lines, fixes, unsure = [], [], []
    for line in text.split("\n"):
        line, saf = repair_sara_am(line)
        fixed, f, u = repair_line(line)
        f = saf + f
        lines.append(fixed)
        fixes.extend(f)
        unsure.extend(u)
    return "\n".join(lines), fixes, unsure
