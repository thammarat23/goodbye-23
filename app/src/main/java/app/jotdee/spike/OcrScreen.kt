package app.jotdee.spike

import android.content.Context
import android.graphics.Bitmap
import android.graphics.ImageDecoder
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
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
import app.jotdee.core.ReceiptTotal
import app.jotdee.core.ThaiIdCard
import com.googlecode.tesseract.android.TessBaseAPI
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

/** Spike 1: how well does Tesseract read Thai receipts and ID cards on this phone? */
@Composable
fun OcrScreen() {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var model by remember { mutableStateOf("fast") }
    var status by remember { mutableStateOf("เลือกรูปใบเสร็จหรือบัตร แล้วดูว่าอ่านถูกแค่ไหน") }
    var text by remember { mutableStateOf("") }
    var findings by remember { mutableStateOf("") }

    val picker = rememberLauncherForActivityResult(ActivityResultContracts.PickVisualMedia()) { uri ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            text = ""
            findings = ""
            try {
                status = "กำลังเตรียมโมเดลภาษาไทย ($model)…"
                val dataDir = withContext(Dispatchers.IO) { ensureModel(context, model) }
                status = "กำลังอ่านภาพ…"
                val started = System.nanoTime()
                val result = withContext(Dispatchers.Default) { recognize(context, uri, dataDir) }
                val ms = (System.nanoTime() - started) / 1_000_000
                text = result
                status = "อ่านเสร็จใน $ms ms · โมเดล $model"
                val total = ReceiptTotal.find(result)
                val ids = ThaiIdCard.findAll(result)
                findings = buildString {
                    appendLine(if (total != null) "ยอดรวม: ฿${total.amount} (จากบรรทัด “${total.line}”)" else "ยอดรวม: ไม่พบ")
                    append(if (ids.isNotEmpty()) "เลขบัตรประชาชนที่ถูกต้อง: ${ids.joinToString { ThaiIdCard.mask(it) }}" else "เลขบัตรประชาชน: ไม่พบ")
                }
            } catch (e: Exception) {
                status = "ผิดพลาด: ${e.message}"
            }
        }
    }

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("โมเดล: fast เร็วกว่า · best แม่นกว่า (ดาวน์โหลดครั้งแรกต้องต่อเน็ต)", style = MaterialTheme.typography.bodySmall)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            FilterChip(selected = model == "fast", onClick = { model = "fast" }, label = { Text("fast") })
            FilterChip(selected = model == "best", onClick = { model = "best" }, label = { Text("best") })
        }
        Button(onClick = { picker.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) }) {
            Text("เลือกรูปจากเครื่อง")
        }
        Text(status, style = MaterialTheme.typography.bodyMedium)
        if (findings.isNotEmpty()) Text(findings, style = MaterialTheme.typography.titleMedium)
        if (text.isNotEmpty()) SelectionContainer { Text(text, style = MaterialTheme.typography.bodySmall) }
    }
}

private const val MODEL_URL = "https://github.com/tesseract-ocr/tessdata_%s/raw/main/%s.traineddata"

/** Downloads tha + eng models once; returns the folder that holds tessdata/. */
private fun ensureModel(context: Context, model: String): File {
    val root = File(context.filesDir, "tess_$model")
    val tessdata = File(root, "tessdata").apply { mkdirs() }
    for (lang in listOf("tha", "eng")) {
        val file = File(tessdata, "$lang.traineddata")
        if (file.exists() && file.length() > 0) continue
        val tmp = File(tessdata, "$lang.part")
        val conn = URL(MODEL_URL.format(model, lang)).openConnection() as HttpURLConnection
        conn.instanceFollowRedirects = true
        conn.connectTimeout = 15_000
        conn.readTimeout = 60_000
        conn.inputStream.use { input -> tmp.outputStream().use { input.copyTo(it) } }
        check(tmp.renameTo(file)) { "บันทึกโมเดล $lang ไม่สำเร็จ" }
    }
    return root
}

private fun recognize(context: Context, uri: Uri, dataDir: File): String {
    val bitmap = loadBitmap(context, uri)
    val api = TessBaseAPI()
    try {
        check(api.init(dataDir.absolutePath, "tha+eng")) { "เปิดโมเดล OCR ไม่สำเร็จ" }
        api.setImage(bitmap)
        return api.getUTF8Text() ?: ""
    } finally {
        api.recycle()
        bitmap.recycle()
    }
}

/** Decodes to ARGB_8888 (what Tesseract needs), long side at most 2400 px. */
private fun loadBitmap(context: Context, uri: Uri): Bitmap {
    val source = ImageDecoder.createSource(context.contentResolver, uri)
    return ImageDecoder.decodeBitmap(source) { decoder, info, _ ->
        decoder.allocator = ImageDecoder.ALLOCATOR_SOFTWARE
        val longSide = maxOf(info.size.width, info.size.height)
        if (longSide > 2400) {
            val scale = 2400f / longSide
            decoder.setTargetSize((info.size.width * scale).toInt(), (info.size.height * scale).toInt())
        }
    }.copy(Bitmap.Config.ARGB_8888, false)
}
