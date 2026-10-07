package app.jotdee.spike

import android.Manifest
import android.content.Intent
import android.os.Build
import android.os.PowerManager
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/** Spike 2: do alarms ring on time on this phone, overnight, with the screen off? */
@Composable
fun AlarmScreen() {
    val context = LocalContext.current
    var count by remember { mutableStateOf("16") }
    var interval by remember { mutableStateOf("30") }
    var refresh by remember { mutableIntStateOf(0) }
    val notifPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { refresh++ }

    val power = context.getSystemService(PowerManager::class.java)
    val ignoringBattery = remember(refresh) { power.isIgnoringBatteryOptimizations(context.packageName) }
    val exactOk = remember(refresh) { AlarmReceiver.canScheduleExact(context) }
    val rows = remember(refresh) { AlarmLog.rows(context) }
    val fmt = remember { SimpleDateFormat("dd MMM HH:mm:ss", Locale("th", "TH")) }

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("เครื่อง: ${Build.MANUFACTURER} ${Build.MODEL} · Android ${Build.VERSION.RELEASE}", style = MaterialTheme.typography.bodySmall)
        Text(
            "ตั้งเตือนแบบแม่นยำ: ${if (exactOk) "อนุญาตแล้ว" else "ยังไม่อนุญาต"} · " +
                "ยกเว้นการประหยัดแบต: ${if (ignoringBattery) "ใช่" else "ไม่ใช่"}",
            style = MaterialTheme.typography.bodyMedium,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            if (Build.VERSION.SDK_INT >= 33) {
                OutlinedButton(onClick = { notifPermission.launch(Manifest.permission.POST_NOTIFICATIONS) }) { Text("ขอสิทธิ์แจ้งเตือน") }
            }
            if (!exactOk && Build.VERSION.SDK_INT >= 31) {
                OutlinedButton(onClick = { context.startActivity(Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM)) }) { Text("เปิดสิทธิ์เตือน") }
            }
        }
        OutlinedButton(onClick = { context.startActivity(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)) }) {
            Text("ตั้งค่าประหยัดแบต (ทดสอบทั้งแบบเปิดและปิด)")
        }

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(count, { count = it.filter(Char::isDigit) }, label = { Text("จำนวนครั้ง") }, modifier = Modifier.width(140.dp))
            OutlinedTextField(interval, { interval = it.filter(Char::isDigit) }, label = { Text("ห่างกัน (นาที)") }, modifier = Modifier.width(160.dp))
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(
                enabled = exactOk,
                onClick = {
                    val n = (count.toIntOrNull() ?: 0).coerceIn(1, AlarmReceiver.MAX_ALARMS)
                    val m = (interval.toIntOrNull() ?: 0).coerceAtLeast(1)
                    AlarmReceiver.scheduleTest(context, n, m)
                    refresh++
                },
            ) { Text("เริ่มทดสอบ") }
            OutlinedButton(onClick = { refresh++ }) { Text("รีเฟรชผล") }
            OutlinedButton(onClick = { AlarmReceiver.cancelAll(context); AlarmLog.clear(context); refresh++ }) { Text("ล้าง") }
        }

        val fired = rows.filter { it.actual != null }
        val delays = fired.map { (it.actual!! - it.expected) / 1000 }
        Text(
            if (rows.isEmpty()) "ยังไม่ได้เริ่มทดสอบ · แนะนำ 16 ครั้ง ห่างกัน 30 นาที แล้ววางเครื่องปิดจอทิ้งไว้ทั้งคืน"
            else "ดังแล้ว ${fired.size}/${rows.size} ครั้ง" +
                if (delays.isNotEmpty()) " · ช้าสุด ${delays.max()} วินาที · เฉลี่ย ${delays.average().toInt()} วินาที" +
                    " · ${if (delays.max() <= 60) "ผ่านเกณฑ์ (≤ 60 วินาที)" else "ไม่ผ่านเกณฑ์"}" else "",
            style = MaterialTheme.typography.titleMedium,
        )
        rows.forEach { r ->
            val line = if (r.actual == null) "#${r.id}  กำหนด ${fmt.format(Date(r.expected))}  —  ยังไม่ดัง"
            else "#${r.id}  กำหนด ${fmt.format(Date(r.expected))}  ดังจริง ${fmt.format(Date(r.actual))}  (ช้า ${(r.actual - r.expected) / 1000} วิ)"
            Text(line, style = MaterialTheme.typography.bodySmall)
        }
    }
}
