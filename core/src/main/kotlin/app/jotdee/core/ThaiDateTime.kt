package app.jotdee.core

import java.time.DayOfWeek
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.LocalTime
import java.time.temporal.ChronoUnit
import java.time.temporal.TemporalAdjusters

enum class Repeat { DAILY, WEEKLY, MONTHLY, YEARLY }

/**
 * When something should happen, read from a Thai sentence.
 * [time] is null when no time was said; the UI then asks or uses a default.
 */
data class ParsedWhen(
    val date: LocalDate,
    val time: LocalTime?,
    val repeat: Repeat?,
    val remindBeforeMinutes: Int?,
)

/**
 * Reads dates and times the way Thai people say them:
 * "พรุ่งนี้แปดโมงเช้า", "บ่ายสอง", "สองทุ่มครึ่ง", "ตีห้า", "วันศุกร์หน้า",
 * "ทุกวันที่ 5", "15 พ.ย.", "อีก 30 นาที", "เตือนก่อนชั่วโมงนึง".
 *
 * Bare "N โมง" with N 1–5 follows the traditional count from 6 a.m.
 * ("สองโมง" = 08:00). The app always shows the result for confirmation.
 */
object ThaiDateTime {
    private const val N = ThaiNumbers.PATTERN
    private const val WD = "(จันทร์|อังคาร|พุธ|พฤหัสบดี|พฤหัส|ศุกร์|เสาร์|อาทิตย์)"
    private const val MINUTES = "(?:(ครึ่ง)|($N)นาที)?"

    private val weekdays = mapOf(
        "จันทร์" to DayOfWeek.MONDAY, "อังคาร" to DayOfWeek.TUESDAY, "พุธ" to DayOfWeek.WEDNESDAY,
        "พฤหัสบดี" to DayOfWeek.THURSDAY, "พฤหัส" to DayOfWeek.THURSDAY, "ศุกร์" to DayOfWeek.FRIDAY,
        "เสาร์" to DayOfWeek.SATURDAY, "อาทิตย์" to DayOfWeek.SUNDAY,
    )

    private val monthNames = listOf(
        "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
        "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม",
    )
    private val monthAbbr = listOf(
        "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค.",
    )
    // Full names, then abbreviations with the last dot optional ("พ.ย." or "พ.ย").
    private val monthPattern = (monthNames + monthAbbr.map { it.removeSuffix(".").replace(".", "\\.") + "\\.?" })
        .joinToString("|", "(", ")")

    private val offsetRe = Regex("(?:เตือน)?ก่อน($N)?(นาที|ชั่วโมง|ชม\\.?|วัน)(นึง|หนึ่ง)?")
    private val relativeRe = Regex("อีก($N)(นาที|ชั่วโมง|ชม\\.?|วัน)")

    private val clockRe = Regex("(\\d{1,2})[:.](\\d{2})")
    private val midnightRe = Regex("เที่ยงคืน")
    private val noonRe = Regex("เที่ยง(?:วัน)?$MINUTES")
    private val afternoonRe = Regex("บ่าย(?:($N)(โมง)?|(โมง))$MINUTES")
    private val eveningRe = Regex("(?:($N)ทุ่ม|ทุ่ม(?:นึง|หนึ่ง)?)$MINUTES")
    private val lateNightRe = Regex("ตี($N)$MINUTES")
    private val dayClockRe = Regex("(?<!ชั่ว)($N)?โมง(เช้า|เย็น|ตรง)?$MINUTES")

    private val weekdayRe = Regex("วัน$WD(หน้า)?")
    private val dayOfMonthRe = Regex("วันที่($N)")
    private val dayMonthRe = Regex("($N)$monthPattern")

    fun parse(text: String, now: LocalDateTime): ParsedWhen? {
        var s = ThaiNumbers.normalizeDigits(text).replace(Regex("\\s+"), "")

        val offset = offsetRe.find(s)?.let { m ->
            s = s.removeRange(m.range)
            val n = m.groupValues[1].takeIf { it.isNotEmpty() }?.let(ThaiNumbers::parse) ?: 1
            n * unitMinutes(m.groupValues[2])
        }

        relativeRe.find(s)?.let { m ->
            val n = ThaiNumbers.parse(m.groupValues[1]) ?: return@let
            val at = now.plusMinutes(n.toLong() * unitMinutes(m.groupValues[2])).truncatedTo(ChronoUnit.MINUTES)
            return ParsedWhen(at.toLocalDate(), at.toLocalTime(), parseRepeat(s).first, offset)
        }

        val (repeat, repeatDay) = parseRepeat(s)
        val time = parseTime(s)
        var (date, fromWeekday) = parseDate(s, now.toLocalDate())

        if (date == null && repeatDay != null) {
            date = nextDayOfMonth(now.toLocalDate(), repeatDay)
        }
        if (date == null && time == null && repeat == null && offset == null) return null

        val today = now.toLocalDate()
        if (date == null) {
            date = if (time != null && !time.isAfter(now.toLocalTime())) today.plusDays(1) else today
        } else if (date == today && time != null && !time.isAfter(now.toLocalTime())) {
            // "วันพุธ บ่ายโมง" said on Wednesday afternoon means next Wednesday;
            // "ทุกวันที่ 7" said after the time has passed starts next month.
            if (fromWeekday) date = date.plusWeeks(1)
            else if (repeatDay != null) date = nextDayOfMonth(today.plusDays(1), repeatDay)
        }
        return ParsedWhen(date ?: today, time, repeat, offset)
    }

    private fun unitMinutes(unit: String): Int = when {
        unit.startsWith("นาที") -> 1
        unit.startsWith("วัน") -> 24 * 60
        else -> 60
    }

    private fun parseRepeat(s: String): Pair<Repeat?, Int?> {
        Regex("ทุกวันที่($N)").find(s)?.let { return Repeat.MONTHLY to ThaiNumbers.parse(it.groupValues[1]) }
        if (Regex("ทุกวัน$WD").containsMatchIn(s)) return Repeat.WEEKLY to null
        if ("ทุกวัน" in s) return Repeat.DAILY to null
        if ("ทุกสัปดาห์" in s || "ทุกอาทิตย์" in s) return Repeat.WEEKLY to null
        if ("ทุกเดือน" in s) return Repeat.MONTHLY to null
        if ("ทุกปี" in s) return Repeat.YEARLY to null
        return null to null
    }

    private fun minutesOf(m: MatchResult, halfGroup: Int): Int {
        if (m.groupValues[halfGroup].isNotEmpty()) return 30
        return m.groupValues[halfGroup + 1].takeIf { it.isNotEmpty() }?.let(ThaiNumbers::parse) ?: 0
    }

    private fun time(h: Int, m: Int): LocalTime? = if (h in 0..23 && m in 0..59) LocalTime.of(h, m) else null

    internal fun parseTime(s: String): LocalTime? {
        clockRe.find(s)?.let { m ->
            time(m.groupValues[1].toInt(), m.groupValues[2].toInt())?.let { return it }
        }
        if (midnightRe.containsMatchIn(s)) return LocalTime.MIDNIGHT
        noonRe.find(s)?.let { m -> return time(12, minutesOf(m, 1)) }
        afternoonRe.find(s)?.let { m ->
            val n = m.groupValues[1].takeIf { it.isNotEmpty() }?.let(ThaiNumbers::parse) ?: 1
            return time(12 + n, minutesOf(m, 4))
        }
        eveningRe.find(s)?.let { m ->
            val n = m.groupValues[1].takeIf { it.isNotEmpty() }?.let(ThaiNumbers::parse) ?: 1
            return time(18 + n, minutesOf(m, 2))
        }
        lateNightRe.find(s)?.let { m ->
            val n = ThaiNumbers.parse(m.groupValues[1]) ?: return@let
            if (n in 1..6) return time(n, minutesOf(m, 2))
        }
        dayClockRe.find(s)?.let { m ->
            val n = m.groupValues[1].takeIf { it.isNotEmpty() }?.let(ThaiNumbers::parse)
            val suffix = m.groupValues[2]
            if (n == null && suffix != "เช้า") return@let
            val hour = when {
                n == null -> 7
                suffix == "เย็น" -> if (n < 12) n + 12 else n
                n in 1..5 -> n + 6
                else -> n
            }
            return time(hour, minutesOf(m, 3))
        }
        return null
    }

    /** Returns the date said, and whether it came from a weekday name. */
    private fun parseDate(s: String, today: LocalDate): Pair<LocalDate?, Boolean> {
        if ("มะรืน" in s) return today.plusDays(2) to false
        if ("พรุ่งนี้" in s) return today.plusDays(1) to false
        if ("วันนี้" in s || "คืนนี้" in s) return today to false

        weekdayRe.find(s)?.let { m ->
            val day = weekdays.getValue(m.groupValues[1])
            var d = today.with(TemporalAdjusters.nextOrSame(day))
            if (m.groupValues[2].isNotEmpty()) d = d.plusWeeks(1)
            return d to true
        }

        dayMonthRe.find(s)?.let { m ->
            val day = ThaiNumbers.parse(m.groupValues[1]) ?: return@let
            val month = monthIndex(m.groupValues[2]) ?: return@let
            val thisYear = runCatching { LocalDate.of(today.year, month, day) }.getOrNull() ?: return@let
            return (if (thisYear.isBefore(today)) thisYear.plusYears(1) else thisYear) to false
        }

        dayOfMonthRe.find(s)?.let { m ->
            val day = ThaiNumbers.parse(m.groupValues[1]) ?: return@let
            return nextDayOfMonth(today, day) to false
        }
        return null to false
    }

    private fun monthIndex(token: String): Int? {
        val i = monthNames.indexOf(token)
        if (i >= 0) return i + 1
        val j = monthAbbr.indexOfFirst { it.removeSuffix(".") == token.removeSuffix(".") }
        return if (j >= 0) j + 1 else null
    }

    /** The next date (today included) whose day of month is [day]; short months use their last day. */
    private fun nextDayOfMonth(from: LocalDate, day: Int): LocalDate? {
        if (day !in 1..31) return null
        var month = from.withDayOfMonth(1)
        repeat(2) {
            val d = month.withDayOfMonth(minOf(day, month.lengthOfMonth()))
            if (!d.isBefore(from)) return d
            month = month.plusMonths(1)
        }
        return null
    }
}
