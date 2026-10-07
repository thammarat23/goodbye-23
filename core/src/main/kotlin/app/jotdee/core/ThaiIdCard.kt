package app.jotdee.core

/**
 * Thai national ID numbers: 13 digits, the last one a check digit.
 * Used to recognise a scanned ID card and route it to the Vault.
 */
object ThaiIdCard {
    private val candidate = Regex("[0-9][0-9 \\-]{11,24}[0-9]")

    /** True when [id] is 13 digits (separators allowed) with a valid check digit. */
    fun isValid(id: String): Boolean {
        val digits = ThaiNumbers.normalizeDigits(id).filter { it.isDigit() }
        if (digits.length != 13) return false
        val sum = (0 until 12).sumOf { i -> (digits[i] - '0') * (13 - i) }
        val check = (11 - sum % 11) % 10
        return check == digits[12] - '0'
    }

    /** All valid ID numbers found in OCR text, as 13 plain digits, in order of appearance. */
    fun findAll(text: String): List<String> {
        val normalized = ThaiNumbers.normalizeDigits(text)
        return candidate.findAll(normalized)
            .map { m -> m.value.filter { it.isDigit() } }
            .filter { it.length == 13 && isValid(it) }
            .distinct()
            .toList()
    }

    /** Shows only the first and last digit: 1-••••-•••••-••-3. */
    fun mask(id: String): String {
        val d = id.filter { it.isDigit() }
        require(d.length == 13) { "Expected 13 digits" }
        return "${d[0]}-••••-•••••-••-${d[12]}"
    }
}
