package app.jotdee.spike

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import app.jotdee.core.ThaiDateTime
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import java.util.Locale

/** Try the Thai date/time reader with your own sentences, typed or dictated by the keyboard mic. */
@Composable
fun ParserScreen() {
    var text by remember { mutableStateOf("พรุ่งนี้บ่ายสองโทรหาช่าง เตือนก่อนชั่วโมงนึง") }
    val parsed = remember(text) { ThaiDateTime.parse(text, LocalDateTime.now()) }
    val dateFmt = remember { DateTimeFormatter.ofPattern("EEEE d MMMM yyyy", Locale("th", "TH")) }

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        OutlinedTextField(text, { text = it }, label = { Text("พิมพ์หรือพูดผ่านไมค์ของคีย์บอร์ด") }, modifier = Modifier.fillMaxWidth())
        Text(
            if (parsed == null) "ไม่พบวันหรือเวลา"
            else buildString {
                appendLine("วันที่: ${parsed.date.format(dateFmt)}")
                appendLine("เวลา: ${parsed.time ?: "ไม่ได้ระบุ"}")
                appendLine("ทำซ้ำ: ${parsed.repeat ?: "ไม่ทำซ้ำ"}")
                append("เตือนล่วงหน้า: ${parsed.remindBeforeMinutes?.let { "$it นาที" } ?: "ไม่ระบุ"}")
            },
            style = MaterialTheme.typography.titleMedium,
        )
        Text(
            "ลอง: บ่ายสาม · สองทุ่มครึ่ง · ตีห้า · วันศุกร์หน้า · 15 พ.ย. · ทุกวันที่ 5 เวลา 09:00 · อีก 30 นาที",
            style = MaterialTheme.typography.bodySmall,
        )
    }
}
