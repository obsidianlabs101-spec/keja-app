package com.keja.app.data.notify

import android.content.Context
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.keja.app.data.AppContainer
import kotlinx.coroutines.flow.first
import java.util.concurrent.TimeUnit

private const val UNIQUE_PERIODIC_NAME = "keja-alerts-sync"
private const val ONE_TIME_NAME = "keja-alerts-sync-now"

/** Background check for new Alerts (see AlertsScreen / notify_service.py on
 * the backend), so a landlord number or an application decision reaches the
 * phone's notification panel even if Keja isn't open. Android's WorkManager
 * enforces a 15-minute floor on periodic work — this isn't instant push,
 * but it's real background delivery with no extra backend infrastructure
 * (no Firebase project) required. */
class AlertsSyncWorker(appContext: Context, params: WorkerParameters) : CoroutineWorker(appContext, params) {
    override suspend fun doWork(): Result {
        val sessionStore = AppContainer.sessionStore(applicationContext)
        val token = runCatching { sessionStore.tokenFlow.first() }.getOrNull()
        if (token.isNullOrBlank()) return Result.success()

        val repo = AppContainer.repository(applicationContext)
        val items = runCatching { repo.notifications() }.getOrNull() ?: return Result.retry()
        val already = runCatching { sessionStore.notifiedAlertIds() }.getOrDefault(emptySet())

        // First sync on a device (or after clearing app data) would otherwise
        // dump every historical alert into the tray at once — only notify
        // for genuinely new ones once a baseline exists.
        if (already.isNotEmpty()) {
            items.filter { it.id !in already }.forEach { AlertNotifier.notify(applicationContext, it) }
        }
        runCatching { sessionStore.markAlertsNotified(items.map { it.id }.toSet()) }
        return Result.success()
    }
}

object AlertsSync {
    fun schedulePeriodic(context: Context) {
        val request = PeriodicWorkRequestBuilder<AlertsSyncWorker>(15, TimeUnit.MINUTES)
            .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
            .build()
        WorkManager.getInstance(context)
            .enqueueUniquePeriodicWork(UNIQUE_PERIODIC_NAME, ExistingPeriodicWorkPolicy.KEEP, request)
    }

    /** Runs one immediate check — called right after login/app-open so a
     * fresh alert doesn't wait for the next 15-minute cycle. */
    fun checkNow(context: Context) {
        val request = OneTimeWorkRequestBuilder<AlertsSyncWorker>()
            .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
            .build()
        WorkManager.getInstance(context).enqueueUniqueWork(ONE_TIME_NAME, ExistingWorkPolicy.REPLACE, request)
    }

    fun cancel(context: Context) {
        WorkManager.getInstance(context).cancelUniqueWork(UNIQUE_PERIODIC_NAME)
        WorkManager.getInstance(context).cancelUniqueWork(ONE_TIME_NAME)
    }
}
