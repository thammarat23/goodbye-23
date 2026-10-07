package app.jotdee.core

import java.time.LocalDate
import java.time.LocalDateTime
import java.time.LocalTime
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull

class ThaiDateTimeTest {
    // Wednesday 7 October 2026, 10:00
    private val now = LocalDateTime.of(2026, 10, 7, 10, 0)
    private val today = now.toLocalDate()

    private fun at(text: String) = ThaiDateTime.parse(text, now)!!.let { it.date to it.time }
    private fun d(day: Int, month: Int = 10) = LocalDate.of(2026, month, day)
    private fun t(h: Int, m: Int = 0) = LocalTime.of(h, m)

    @Test fun `tomorrow at eight in the morning`() =
        assertEquals(d(8) to t(8), at("เตือนพรุ่งนี้แปดโมงเช้าเอารถเข้าศูนย์"))

    @Test fun `afternoon hours`() {
        assertEquals(today to t(14), at("บ่ายสอง"))
        assertEquals(today to t(13), at("บ่ายโมง"))
        assertEquals(today to t(15, 30), at("บ่ายสามโมงครึ่ง"))
    }

    @Test fun `evening thum and late night tee`() {
        assertEquals(today to t(20, 30), at("สองทุ่มครึ่ง"))
        assertEquals(today to t(19), at("ทุ่มนึง"))
        assertEquals(d(8) to t(5), at("ตีห้า"))
    }

    @Test fun `traditional morning count and evening mong`() {
        assertEquals(d(8) to t(9), at("สามโมงเช้า"))
        assertEquals(today to t(17), at("ห้าโมงเย็น"))
        assertEquals(today to t(11), at("สิบเอ็ดโมง"))
        assertEquals(d(8) to t(8, 15), at("แปดโมงสิบห้านาที"))
    }

    @Test fun `noon and clock digits including Thai digits`() {
        assertEquals(today to t(12, 30), at("เที่ยงครึ่ง"))
        assertEquals(today to t(10, 45), at("๑๐:๔๕"))
        assertEquals(today to t(18), at("ประชุม 18.00 น."))
    }

    @Test fun `weekdays and next week`() {
        assertEquals(d(9) to t(15), at("วันศุกร์บ่ายสาม"))
        assertEquals(d(16) to t(15), at("วันศุกร์หน้า บ่ายสาม"))
        assertEquals(d(14) to t(9), at("วันพุธ สามโมงเช้า")) // today's 09:00 already passed
    }

    @Test fun `day and month`() {
        assertEquals(d(15, 11) to null, at("ต่อประกันรถ 15 พ.ย."))
        assertEquals(d(15, 11) to null, at("15 พฤศจิกายน"))
        assertEquals(LocalDate.of(2027, 1, 3) to null, at("3 ม.ค."))
    }

    @Test fun `monthly repeat on a day`() {
        val p = ThaiDateTime.parse("จ่ายค่าอินเทอร์เน็ต ทุกวันที่ 5 เวลา 09:00", now)!!
        assertEquals(Repeat.MONTHLY, p.repeat)
        assertEquals(d(5, 11), p.date)
        assertEquals(t(9), p.time)
    }

    @Test fun `weekly and daily repeat`() {
        val weekly = ThaiDateTime.parse("ทุกวันจันทร์ เจ็ดโมง", now)!!
        assertEquals(Repeat.WEEKLY, weekly.repeat)
        assertEquals(d(12) to t(7), weekly.date to weekly.time)
        assertEquals(Repeat.DAILY, ThaiDateTime.parse("กินยาทุกวัน เที่ยง", now)!!.repeat)
    }

    @Test fun `relative time and reminder offset`() {
        assertEquals(today to t(10, 30), at("อีก 30 นาที"))
        val p = ThaiDateTime.parse("พรุ่งนี้แปดโมง เตือนก่อนชั่วโมงนึง", now)!!
        assertEquals(60, p.remindBeforeMinutes)
        assertEquals(d(8) to t(8), p.date to p.time)
        assertEquals(24 * 60, ThaiDateTime.parse("15 พ.ย. เตือนก่อน 1 วัน", now)!!.remindBeforeMinutes)
    }

    @Test fun `nothing to parse`() {
        assertNull(ThaiDateTime.parse("จ่ายค่าไฟ", now))
        assertNull(ThaiDateTime.parse("ไปตีกอล์ฟกับเพื่อน", now))
    }
}
