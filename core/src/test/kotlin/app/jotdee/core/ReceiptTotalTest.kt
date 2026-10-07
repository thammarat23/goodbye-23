package app.jotdee.core

import java.math.BigDecimal
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue

class ReceiptTotalTest {
    @Test
    fun `picks the grand total line over items and VAT`() {
        val ocr = """
            ร้านแอร์บ้าน
            ใบเสร็จรับเงิน
            ค่าบริการล้างแอร์ 2 เครื่อง   900.00
            เติมน้ำยา                 340.00
            ภาษีมูลค่าเพิ่ม 7%          81.12
            รวมทั้งสิ้น (รวมภาษี)     1,240.00
            เงินสด                    1,500.00
            ทอน                        260.00
        """.trimIndent()
        val r = ReceiptTotal.find(ocr)!!
        assertEquals(BigDecimal("1240.00"), r.amount)
        assertTrue(r.byKeyword)
    }

    @Test
    fun `English receipt and Thai digits`() {
        assertEquals(BigDecimal("1250.50"), ReceiptTotal.find("Coffee 120.00\nSubtotal 1,180.00\nTOTAL 1,250.50")!!.amount)
        assertEquals(BigDecimal("355"), ReceiptTotal.find("ข้าวมันไก่ ๕๐\nยอดรวม ๓๕๕")!!.amount)
    }

    @Test
    fun `falls back to the largest amount with satang`() {
        val r = ReceiptTotal.find("ก๋วยเตี๋ยว 60.00\nน้ำแข็ง 10.00\n7-11 สาขา 1234\n70.00")!!
        assertEquals(BigDecimal("70.00"), r.amount)
        assertEquals(false, r.byKeyword)
    }

    @Test
    fun `no amount at all`() {
        assertNull(ReceiptTotal.find("ขอบคุณที่ใช้บริการ"))
    }
}
