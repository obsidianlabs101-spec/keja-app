package com.keja.app.data.notify

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.graphics.Canvas
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.keja.app.MainActivity
import com.keja.app.R
import com.keja.app.data.model.NotificationDto

private const val CHANNEL_ID = "keja_alerts"
private const val KEJA_PURPLE = 0xFF6D28D9.toInt()

/** Posts Keja's in-app Alerts (landlord numbers, application and listing
 * updates) as real Android system notifications, styled to match the app:
 * the brand bell as the small icon, the Keja mark as the large icon, and
 * the brand purple as the accent color. Android-only, by design — the
 * website has its own in-page bell and doesn't need OS-level pushes. */
object AlertNotifier {
    fun ensureChannel(context: Context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val manager = context.getSystemService(NotificationManager::class.java) ?: return
        if (manager.getNotificationChannel(CHANNEL_ID) != null) return
        val channel = NotificationChannel(
            CHANNEL_ID,
            "Keja alerts",
            NotificationManager.IMPORTANCE_HIGH,
        ).apply {
            description = "Landlord numbers, and updates on your applications and listings"
            enableLights(true)
            lightColor = KEJA_PURPLE
            enableVibration(true)
        }
        manager.createNotificationChannel(channel)
    }

    fun notify(context: Context, item: NotificationDto) {
        ensureChannel(context)
        // The launcher mark is a vector drawable (see ic_launcher_foreground.xml),
        // so it's rendered to a bitmap here rather than decoded directly.
        val largeIcon = runCatching {
            val drawable = androidx.core.content.ContextCompat.getDrawable(context, R.drawable.ic_launcher_foreground)
            drawable?.let {
                val bmp = android.graphics.Bitmap.createBitmap(128, 128, android.graphics.Bitmap.Config.ARGB_8888)
                val canvas = Canvas(bmp)
                canvas.drawColor(KEJA_PURPLE)
                it.setBounds(0, 0, canvas.width, canvas.height)
                it.draw(canvas)
                bmp
            }
        }.getOrNull()

        val openIntent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
            putExtra(MainActivity.EXTRA_OPEN_ROUTE, MainActivity.ROUTE_ALERTS)
        }
        val pendingIntent = PendingIntent.getActivity(
            context,
            item.id.hashCode(),
            openIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )

        val builder = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_stat_keja_bell)
            .setColor(KEJA_PURPLE)
            .setContentTitle(item.title)
            .setContentText(item.body ?: "")
            .setStyle(NotificationCompat.BigTextStyle().bigText(item.body ?: item.title))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(NotificationCompat.CATEGORY_MESSAGE)
            .setAutoCancel(true)
            .setContentIntent(pendingIntent)
        if (largeIcon != null) builder.setLargeIcon(largeIcon)

        runCatching {
            NotificationManagerCompat.from(context).notify(item.id.hashCode(), builder.build())
        }
    }
}
