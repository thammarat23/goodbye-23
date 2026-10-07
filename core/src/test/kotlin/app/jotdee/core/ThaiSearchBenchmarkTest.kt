package app.jotdee.core

import java.sql.Connection
import java.sql.DriverManager
import kotlin.system.measureNanoTime
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/**
 * Spike: can SQLite FTS5 with the trigram tokenizer search Thai text,
 * which has no spaces between words? Uses 10,000 generated notes.
 */
class ThaiSearchBenchmarkTest {
    private fun Connection.count(sql: String, arg: String): Int =
        prepareStatement(sql).use { st -> st.setString(1, arg); st.executeQuery().use { it.next(); it.getInt(1) } }

    @Test
    fun `fts5 trigram finds the same notes as LIKE, fast`() {
        DriverManager.getConnection("jdbc:sqlite::memory:").use { db ->
            db.createStatement().use { it.execute("CREATE VIRTUAL TABLE notes USING fts5(title, body, tokenize='trigram')") }
            db.autoCommit = false
            db.prepareStatement("INSERT INTO notes(title, body) VALUES (?, ?)").use { st ->
                for ((title, body) in SampleNotes.generate(10_000)) {
                    st.setString(1, title)
                    st.setString(2, body)
                    st.addBatch()
                }
                st.executeBatch()
            }
            db.commit()

            for (term in listOf("ประกันรถ", "ค่าไฟ", "เอกสาร", "แอร์")) {
                val like = db.count("SELECT count(*) FROM notes WHERE title LIKE '%' || ?1 || '%' OR body LIKE '%' || ?1 || '%'", term)
                var fts = 0
                val ms = measureNanoTime {
                    fts = db.count("SELECT count(*) FROM notes WHERE notes MATCH ?", "\"$term\"")
                } / 1_000_000.0
                println("FTS5 trigram '$term': $fts hits in ${"%.1f".format(ms)} ms (LIKE: $like)")
                assertEquals(like, fts, "trigram must find exactly what LIKE finds for '$term'")
                assertTrue(ms < 200, "search for '$term' took $ms ms")
            }

            // Trigram cannot index terms under 3 characters; the app falls back to LIKE for those.
            assertTrue(SampleNotes.needsLikeFallback("รถ"))
            assertEquals(0, db.count("SELECT count(*) FROM notes WHERE notes MATCH ?", "\"รถ\""))
        }
    }
}
