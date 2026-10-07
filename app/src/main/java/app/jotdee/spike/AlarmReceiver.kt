package app.jotdee.spike

import android.app.AlarmManager
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.media.AudioAttributes
import android.media.RingtoneManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat

/** Spike 2: records when each test alarm actually fired, then rings. */
class AlarmReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val id = intent.getIntExtra(EXTRA_ID, -1)
        val expected = intent.getLongExtra(EXTRA_EXPECTED, 0L)
        AlarmLog.record(context, id, expected, System.currentTimeMillis())

        ensureChannel(context)
        val open = PendingIntent.getActivity(
            context, 0, Intent(context, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        val notification = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_lock_idle_alarm)
            .setContentTitle("เตือนทดสอบ #$id")
            .setContentText("ช้ากว่ากำหนด ${(System.currentTimeMillis() - expected) / 1000} วินาที")
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setContentIntent(open)
            .setAutoCancel(true)
            .build()
        if (NotificationManagerCompat.from(context).areNotificationsEnabled()) {
            try {
                NotificationManagerCompat.from(context).notify(1000 + id, notification)
            } catch (_: SecurityException) {
                // Notification permission revoked; the timing is already logged.
            }
        }
    }

    companion object {
        const val EXTRA_ID = "id"
        const val EXTRA_EXPECTED = "expected"
        private const val CHANNEL_ID = "alarm_test"

        private fun ensureChannel(context: Context) {
            val manager = context.getSystemService(NotificationManager::class.java)
            if (manager.getNotificationChannel(CHANNEL_ID) != null) return
            val channel = NotificationChannel(CHANNEL_ID, "เตือนทดสอบ", NotificationManager.IMPORTANCE_HIGH).apply {
                setSound(
                    RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM),
                    AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ALARM).build(),
                )
                enableVibration(true)
            }
            manager.createNotificationChannel(channel)
        }

        /** Schedules [count] alarms, one every [intervalMinutes], with setAlarmClock (the most reliable API). */
        fun scheduleTest(context: Context, count: Int, intervalMinutes: Int) {
            val am = context.getSystemService(AlarmManager::class.java)
            cancelAll(context)
            AlarmLog.clear(context)
            val start = System.currentTimeMillis()
            val show = PendingIntent.getActivity(
                context, 0, Intent(context, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE,
            )
            for (i in 1..count) {
                val at = start + i * intervalMinutes * 60_000L
                val fire = PendingIntent.getBroadcast(
                    context, i,
                    Intent(context, AlarmReceiver::class.java).putExtra(EXTRA_ID, i).putExtra(EXTRA_EXPECTED, at),
                    PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
                )
                am.setAlarmClock(AlarmManager.AlarmClockInfo(at, show), fire)
                AlarmLog.planned(context, i, at)
            }
        }

        fun cancelAll(context: Context) {
            val am = context.getSystemService(AlarmManager::class.java)
            for (i in 1..MAX_ALARMS) {
                val pi = PendingIntent.getBroadcast(
                    context, i, Intent(context, AlarmReceiver::class.java),
                    PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_NO_CREATE,
                ) ?: continue
                am.cancel(pi)
            }
        }

        fun canScheduleExact(context: Context): Boolean =
            Build.VERSION.SDK_INT < Build.VERSION_CODES.S ||
                context.getSystemService(AlarmManager::class.java).canScheduleExactAlarms()

        const val MAX_ALARMS = 100
    }
}

/** Planned and actual fire times, kept in SharedPreferences so they survive the app being killed. */
object AlarmLog {
    data class Row(val id: Int, val expected: Long, val actual: Long?)

    private fun prefs(context: Context) = context.getSharedPreferences("alarm_log", Context.MODE_PRIVATE)

    fun clear(context: Context) = prefs(context).edit().clear().apply()

    fun planned(context: Context, id: Int, at: Long) = prefs(context).edit().putLong("p$id", at).apply()

    fun record(context: Context, id: Int, expected: Long, actual: Long) =
        prefs(context).edit().putLong("p$id", expected).putLong("a$id", actual).commit()

    fun rows(context: Context): List<Row> {
        val all = prefs(context).all
        return all.keys.filter { it.startsWith("p") }.mapNotNull { it.drop(1).toIntOrNull() }.sorted().map { id ->
            Row(id, all["p$id"] as Long, all["a$id"] as Long?)
        }
    }
}
