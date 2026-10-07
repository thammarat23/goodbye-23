package app.jotdee.spike

import android.content.Context
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.sqlite.SQLiteConnection
import androidx.sqlite.driver.bundled.BundledSQLiteDriver
import androidx.sqlite.execSQL
import app.jotdee.core.SampleNotes
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

/** Spike 3: Thai full-text search with FTS5 trigram on 10,000 notes, on the phone itself. */
@Composable
fun SearchScreen() {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var status by remember { mutableStateOf("กดสร้างโน้ตตัวอย่างก่อน แล้วลองค้นคำภาษาไทย") }
    var query by remember { mutableStateOf("ประกันรถ") }
    var result by remember { mutableStateOf("") }

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Button(onClick = {
            scope.launch {
                status = "กำลังสร้างโน้ต 10,000 ใบ…"
                status = try {
                    withContext(SearchDb.dispatcher) { SearchDb.rebuild(context) }
                } catch (e: Exception) {
                    "ผิดพลาด: ${e.message}"
                }
            }
        }) { Text("สร้างโน้ตตัวอย่าง 10,000 ใบ") }
        Text(status, style = MaterialTheme.typography.bodyMedium)

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(query, { query = it }, label = { Text("คำค้น") }, modifier = Modifier.weight(1f))
        }
        Button(onClick = {
            scope.launch {
                result = try {
                    withContext(SearchDb.dispatcher) { SearchDb.search(context, query.trim()) }
                } catch (e: Exception) {
                    "ผิดพลาด: ${e.message}"
                }
            }
        }, modifier = Modifier.fillMaxWidth()) { Text("ค้นหา") }
        Text(result, style = MaterialTheme.typography.titleMedium)
        Text(
            "ลองคำ: ประกันรถ · ค่าไฟ · เอกสาร · แอร์ · รถ (คำ 2 ตัวอักษรจะใช้ LIKE แทน)",
            style = MaterialTheme.typography.bodySmall,
        )
    }
}

private object SearchDb {
    // One thread: a SQLiteConnection must not be used from two threads at once.
    @OptIn(ExperimentalCoroutinesApi::class)
    val dispatcher = Dispatchers.IO.limitedParallelism(1)

    private var connection: SQLiteConnection? = null

    private fun open(context: Context): SQLiteConnection =
        connection ?: BundledSQLiteDriver().open(File(context.filesDir, "search_spike.db").path).also { connection = it }

    fun rebuild(context: Context): String {
        val db = open(context)
        val version = db.prepare("SELECT sqlite_version()").use { it.step(); it.getText(0) }
        db.execSQL("DROP TABLE IF EXISTS notes")
        db.execSQL("CREATE VIRTUAL TABLE notes USING fts5(title, body, tokenize='trigram')")
        val started = System.nanoTime()
        db.execSQL("BEGIN")
        db.prepare("INSERT INTO notes(title, body) VALUES (?, ?)").use { st ->
            for ((title, body) in SampleNotes.generate(10_000)) {
                st.bindText(1, title)
                st.bindText(2, body)
                st.step()
                st.reset()
            }
        }
        db.execSQL("COMMIT")
        val ms = (System.nanoTime() - started) / 1_000_000
        return "สร้างเสร็จใน $ms ms · SQLite $version · FTS5 trigram ใช้ได้"
    }

    fun search(context: Context, term: String): String {
        if (term.isEmpty()) return "พิมพ์คำค้นก่อน"
        val db = open(context)
        val likeSql = "SELECT count(*) FROM notes WHERE title LIKE '%' || ?1 || '%' OR body LIKE '%' || ?1 || '%'"

        val likeStart = System.nanoTime()
        val likeCount = count(db, likeSql, term)
        val likeMs = (System.nanoTime() - likeStart) / 1_000_000.0

        if (SampleNotes.needsLikeFallback(term)) {
            return "“$term” สั้นกว่า 3 ตัวอักษร ใช้ LIKE: ${likeCount} ใบ ใน ${"%.1f".format(likeMs)} ms"
        }
        val ftsStart = System.nanoTime()
        val ftsCount = count(db, "SELECT count(*) FROM notes WHERE notes MATCH ?", "\"$term\"")
        val ftsMs = (System.nanoTime() - ftsStart) / 1_000_000.0
        val verdict = if (ftsCount == likeCount && ftsMs < 200) "ผ่านเกณฑ์" else "ไม่ผ่านเกณฑ์"
        return "FTS5: $ftsCount ใบ ใน ${"%.1f".format(ftsMs)} ms\nLIKE: $likeCount ใบ ใน ${"%.1f".format(likeMs)} ms\n$verdict (เจอครบและ < 200 ms)"
    }

    private fun count(db: SQLiteConnection, sql: String, arg: String): Long =
        db.prepare(sql).use { st -> st.bindText(1, arg); st.step(); st.getLong(0) }
}
