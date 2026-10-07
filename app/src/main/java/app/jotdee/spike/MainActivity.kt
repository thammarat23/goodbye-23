package app.jotdee.spike

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent { SpikeApp() }
    }
}

private val ivory = lightColorScheme(
    primary = Color(0xFF8C6A2F),
    onPrimary = Color.White,
    background = Color(0xFFF7F5F0),
    surface = Color(0xFFF7F5F0),
    onBackground = Color(0xFF1A1814),
    onSurface = Color(0xFF1A1814),
)

@Composable
private fun SpikeApp() {
    var tab by rememberSaveable { mutableIntStateOf(0) }
    val tabs = listOf("OCR ไทย", "เตือน", "ค้นหา", "วันเวลา")
    MaterialTheme(colorScheme = ivory) {
        Scaffold(modifier = Modifier.fillMaxSize()) { padding ->
            Column(Modifier.padding(padding)) {
                TabRow(selectedTabIndex = tab) {
                    tabs.forEachIndexed { i, label ->
                        Tab(selected = tab == i, onClick = { tab = i }, text = { Text(label) })
                    }
                }
                Box(Modifier.fillMaxSize()) {
                    when (tab) {
                        0 -> OcrScreen()
                        1 -> AlarmScreen()
                        2 -> SearchScreen()
                        else -> ParserScreen()
                    }
                }
            }
        }
    }
}
