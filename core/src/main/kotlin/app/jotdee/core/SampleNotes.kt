package app.jotdee.core

import kotlin.random.Random

/** Generated Thai notes for search benchmarks; the same seed gives the same notes. */
object SampleNotes {
    val fragments = listOf(
        "ต่อประกันรถ", "ค่าไฟเดือนนี้", "ส่งเอกสารให้ฝ่ายบัญชี", "นัดทันตแพทย์", "ซื้อของเข้าบ้าน",
        "ประชุมทีมเรื่องงบประมาณ", "โทรหาช่างแอร์", "จ่ายค่าอินเทอร์เน็ต", "ไอเดียโครงการใหม่",
        "ใบเสร็จค่าซ่อมแอร์", "กินยาหลังอาหาร", "วิ่งรอบสวนสาธารณะ", "ผ่อนรถงวดที่", "เติมน้ำมัน",
        "วันเกิดแม่", "ร้านกาแฟเปิดใหม่", "สมัครคอร์สภาษาอังกฤษ", "ตรวจสุขภาพประจำปี",
    )

    /** [count] (title, body) pairs. */
    fun generate(count: Int, seed: Int = 42): Sequence<Pair<String, String>> {
        val r = Random(seed)
        return generateSequence {
            val title = fragments[r.nextInt(fragments.size)]
            val body = (1..r.nextInt(3, 9)).joinToString("") { fragments[r.nextInt(fragments.size)] }
            title to body
        }.take(count)
    }

    /** Trigram full-text search only works for terms of 3 or more characters. */
    fun needsLikeFallback(term: String): Boolean = term.codePointCount(0, term.length) < 3
}
