package com.screentimetrack.app

import android.Manifest
import android.app.AlarmManager
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import java.util.Calendar

/**
 * Pengingat harian tunggal: sesuai prinsip "sedikit notifikasi, tepat konteks"
 * (prd Bab 6). Jadwal dan teks diatur dari Flutter agar mengikuti bahasa aktif;
 * notifikasi hanya satu per hari dan bisa dimatikan kapan saja.
 */
object ReminderScheduler {
    const val PREFS = "reminder_prefs"
    const val KEY_ENABLED = "enabled"
    const val KEY_HOUR = "hour"
    const val KEY_MINUTE = "minute"
    const val KEY_TITLE = "title"
    const val KEY_BODY = "body"
    const val CHANNEL_ID = "momo_reminder"

    private const val REQUEST_CODE = 1001

    /**
     * One-shot alarms with a bounded window: inexact repeating alarms drifted
     * by many hours on some devices, and exact alarms need a special
     * permission Momo deliberately does not request.
     */
    private const val WINDOW_MS = 15 * 60 * 1000L

    fun isEnabled(context: Context): Boolean =
        prefs(context).getBoolean(KEY_ENABLED, false)

    fun schedule(context: Context, hour: Int, minute: Int, title: String, body: String) {
        if (!NativeStore.enabled(context)) return
        NativeStore.checkCommit(
            prefs(context).edit()
                .putBoolean(KEY_ENABLED, true)
                .putInt(KEY_HOUR, hour)
                .putInt(KEY_MINUTE, minute)
                .putString(KEY_TITLE, title)
                .putString(KEY_BODY, body)
        )
        setAlarm(context)
    }

    /** Synchronous so consent revocation cannot be undone by a queued write. */
    fun cancel(context: Context) {
        NativeStore.checkCommit(prefs(context).edit().putBoolean(KEY_ENABLED, false))
        val alarmManager = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        runCatching { alarmManager.cancel(pending(context)) }
    }

    fun reschedule(context: Context) {
        if (NativeStore.enabled(context) && isEnabled(context)) setAlarm(context)
    }

    private fun prefs(context: Context) =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    private fun pending(context: Context): PendingIntent {
        val intent = Intent(context, ReminderReceiver::class.java)
        return PendingIntent.getBroadcast(
            context,
            REQUEST_CODE,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
    }

    private fun setAlarm(context: Context) {
        val p = prefs(context)
        val hour = p.getInt(KEY_HOUR, 20)
        val minute = p.getInt(KEY_MINUTE, 0)
        val calendar = Calendar.getInstance().apply {
            set(Calendar.HOUR_OF_DAY, hour)
            set(Calendar.MINUTE, minute)
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
            if (timeInMillis <= System.currentTimeMillis()) {
                add(Calendar.DAY_OF_YEAR, 1)
            }
        }
        val alarmManager = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        runCatching {
            alarmManager.setWindow(
                AlarmManager.RTC_WAKEUP,
                calendar.timeInMillis,
                WINDOW_MS,
                pending(context)
            )
        }
    }
}

class ReminderReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        // Alarms may survive a kill between disabling collection and cancelling them.
        if (!NativeStore.enabled(context)) return
        val prefs = context.getSharedPreferences(ReminderScheduler.PREFS, Context.MODE_PRIVATE)
        if (!prefs.getBoolean(ReminderScheduler.KEY_ENABLED, false)) return
        // One-shot alarms do not repeat; arm tomorrow even if this notification
        // is skipped because notifications were turned off.
        ReminderScheduler.reschedule(context)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            return
        }

        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (!manager.areNotificationsEnabled()) return
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                ReminderScheduler.CHANNEL_ID,
                "Pengingat harian",
                NotificationManager.IMPORTANCE_DEFAULT
            ).apply {
                // Channel descriptions are permanent and shared by both
                // companions, so they must never name one pet.
                description = "Satu pengingat singkat per hari."
                setShowBadge(false)
            }
            manager.createNotificationChannel(channel)
        }

        val openIntent = Intent(context, MainActivity::class.java).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
        }
        val pending = PendingIntent.getActivity(
            context,
            1002,
            openIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val builder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            Notification.Builder(context, ReminderScheduler.CHANNEL_ID)
        } else {
            @Suppress("DEPRECATION")
            Notification.Builder(context)
        }

        val notification = builder
            .setContentTitle(
                prefs.getString(ReminderScheduler.KEY_TITLE, "Pengingat harian")
            )
            .setContentText(
                prefs.getString(
                    ReminderScheduler.KEY_BODY,
                    "Cek HP dan selesaikan satu misi hari ini."
                )
            )
            .setSmallIcon(R.drawable.ic_pill)
            .setContentIntent(pending)
            .setAutoCancel(true)
            .build()

        runCatching { manager.notify(101, notification) }
    }
}

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        if (!NativeStore.enabled(context)) return
        when (intent?.action) {
            Intent.ACTION_BOOT_COMPLETED,
            // An absolute alarm follows the old wall clock after these; the
            // reminder would fire at the wrong local time until reopened.
            Intent.ACTION_TIME_CHANGED,
            Intent.ACTION_TIMEZONE_CHANGED,
            Intent.ACTION_MY_PACKAGE_REPLACED -> ReminderScheduler.reschedule(context)
        }
    }
}
