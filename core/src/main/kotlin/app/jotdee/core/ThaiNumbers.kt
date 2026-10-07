package app.jotdee.core

/** Thai digits and number words (0–59) as they appear in speech-to-text and OCR output. */
object ThaiNumbers {
    private const val THAI_DIGITS = "๐๑๒๓๔๕๖๗๘๙"

    private val units = mapOf(
        "หนึ่ง" to 1, "นึง" to 1, "เอ็ด" to 1, "สอง" to 2, "สาม" to 3, "สี่" to 4,
        "ห้า" to 5, "หก" to 6, "เจ็ด" to 7, "แปด" to 8, "เก้า" to 9,
    )
    private val tens = mapOf("ยี่สิบ" to 20, "สามสิบ" to 30, "สี่สิบ" to 40, "ห้าสิบ" to 50, "สิบ" to 10)

    private const val UNIT = "(?:หนึ่ง|นึง|เอ็ด|สอง|สาม|สี่|ห้า|หก|เจ็ด|แปด|เก้า)"
    private const val TENS = "(?:ยี่สิบ|สามสิบ|สี่สิบ|ห้าสิบ|สิบ)"

    /** Regex fragment (no capture group) matching a number written in digits or Thai words. */
    const val PATTERN = "(?:\\d{1,2}|$TENS$UNIT?|$UNIT)"

    /** Replaces Thai digits ๐–๙ with ASCII digits. */
    fun normalizeDigits(text: String): String = buildString(text.length) {
        for (c in text) {
            val i = THAI_DIGITS.indexOf(c)
            append(if (i >= 0) ('0' + i) else c)
        }
    }

    /** Parses a token matched by [PATTERN]; returns null when it is not a number. */
    fun parse(token: String): Int? {
        token.toIntOrNull()?.let { return it }
        for ((word, value) in tens) {
            if (token.startsWith(word)) {
                val rest = token.removePrefix(word)
                if (rest.isEmpty()) return value
                return units[rest]?.let { value + it }
            }
        }
        return units[token]
    }
}
