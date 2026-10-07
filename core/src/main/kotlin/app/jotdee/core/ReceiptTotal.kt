package app.jotdee.core

import java.math.BigDecimal

/** Finds the grand total in OCR text of a Thai or English receipt. */
object ReceiptTotal {
    private const val STRONG_KEYWORDS = 3

    // Strongest first: a line with an earlier keyword beats one with a later keyword.
    private val keywords = listOf(
        "รวมทั้งสิ้น", "ยอดสุทธิ", "ยอดชำระ", "ยอดรวม", "รวมเงิน", "grand total", "amount due", "net total", "total", "รวม",
    )
    // Lines that carry an amount but are never the total.
    private val excluded = listOf("ภาษี", "vat", "ส่วนลด", "discount", "ทอน", "change", "เงินสด", "cash", "รับเงิน", "ก่อน")

    private val amount = Regex("(\\d{1,3}(?:,\\d{3})+|\\d+)(?:\\.(\\d{1,2}))?")

    data class Result(val amount: BigDecimal, val line: String, val byKeyword: Boolean)

    fun find(ocrText: String): Result? {
        val lines = ThaiNumbers.normalizeDigits(ocrText).lines().map { it.trim() }.filter { it.isNotEmpty() }

        for ((rank, keyword) in keywords.withIndex()) {
            for (line in lines.asReversed()) {
                val lower = line.lowercase()
                if (keyword !in lower) continue
                // "รวมทั้งสิ้น (รวมภาษี)" is still the total; only weaker keywords are filtered.
                if (rank >= STRONG_KEYWORDS && excluded.any { it in lower }) continue
                lastAmount(line)?.let { return Result(it, line, byKeyword = true) }
            }
        }

        // No keyword: the largest amount with satang (.xx) is usually the total.
        return lines
            .flatMap { line -> amount.findAll(line).filter { it.groupValues[2].isNotEmpty() }.map { parse(it) to line } }
            .maxByOrNull { it.first }
            ?.let { Result(it.first, it.second, byKeyword = false) }
    }

    private fun lastAmount(line: String): BigDecimal? = amount.findAll(line).lastOrNull()?.let { parse(it) }

    private fun parse(m: MatchResult): BigDecimal {
        val whole = m.groupValues[1].replace(",", "")
        val frac = m.groupValues[2]
        return BigDecimal(if (frac.isEmpty()) whole else "$whole.$frac")
    }
}
