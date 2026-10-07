package app.jotdee.core

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class ThaiIdCardTest {
    @Test
    fun `valid check digit passes and a changed digit fails`() {
        assertTrue(ThaiIdCard.isValid("1101700123456"))
        assertTrue(ThaiIdCard.isValid("1 1017 00123 45 6"))
        assertFalse(ThaiIdCard.isValid("1101700123457"))
        assertFalse(ThaiIdCard.isValid("110170012345"))
    }

    @Test
    fun `finds ids in noisy OCR text with Thai digits and dashes`() {
        val ocr = """
            บัตรประจำตัวประชาชน Thai National ID Card
            เลขประจำตัวประชาชน ๓-๑๐๐๕-๐๑๒๓๔-๕๖-๓
            วันออกบัตร 12 ม.ค. 2565 โทร 0812345678
        """.trimIndent()
        assertEquals(listOf("3100501234563"), ThaiIdCard.findAll(ocr))
    }

    @Test
    fun `phone numbers and invalid 13 digit runs are ignored`() {
        assertEquals(emptyList(), ThaiIdCard.findAll("โทร 081-234-5678 บัญชี 1234567890123"))
    }

    @Test
    fun `mask keeps only first and last digit`() {
        assertEquals("1-••••-•••••-••-6", ThaiIdCard.mask("1101700123456"))
    }
}
