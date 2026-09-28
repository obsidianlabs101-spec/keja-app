package com.keja.app.data

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.Settings
import androidx.core.content.FileProvider
import androidx.core.content.pm.PackageInfoCompat
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.io.File
import java.util.concurrent.TimeUnit

private const val RELEASE_BASE = "https://github.com/obsidianlabs101-spec/keja-app/releases/download/android-latest"
private const val VERSION_URL = "$RELEASE_BASE/keja-version.json"
private const val APK_URL = "$RELEASE_BASE/app-debug.apk"

sealed class UpdateCheck {
    data class Available(val latestBuild: Int, val installedBuild: Int) : UpdateCheck()
    data class UpToDate(val installedBuild: Int) : UpdateCheck()
    data class Failed(val reason: String) : UpdateCheck()
}

/** Checks the newest CI build published to the android-latest release and
 * installs it over the running app. Builds are signed with one permanent
 * key (see build.gradle.kts), so Android accepts them as updates — no more
 * uninstall/reinstall. */
object AppUpdater {
    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .followRedirects(true)
        .build()

    fun installedBuild(context: Context): Int {
        val info = context.packageManager.getPackageInfo(context.packageName, 0)
        return PackageInfoCompat.getLongVersionCode(info).toInt()
    }

    suspend fun check(context: Context): UpdateCheck = withContext(Dispatchers.IO) {
        val installed = installedBuild(context)
        try {
            client.newCall(Request.Builder().url(VERSION_URL).header("Cache-Control", "no-cache").build()).execute().use { resp ->
                if (!resp.isSuccessful) return@withContext UpdateCheck.Failed("Couldn't reach the update server (${resp.code}).")
                val latest = JSONObject(resp.body?.string() ?: "").optInt("build", 0)
                if (latest > installed) UpdateCheck.Available(latest, installed) else UpdateCheck.UpToDate(installed)
            }
        } catch (e: Exception) {
            UpdateCheck.Failed("Couldn't check for updates — are you online?")
        }
    }

    /** Downloads the APK to the cache, reporting 0..1 progress (or -1f if the size is unknown). */
    suspend fun download(context: Context, onProgress: (Float) -> Unit): File = withContext(Dispatchers.IO) {
        val dir = File(context.cacheDir, "updates").apply { mkdirs() }
        dir.listFiles()?.forEach { it.delete() }
        val out = File(dir, "keja-update.apk")
        client.newCall(Request.Builder().url(APK_URL).build()).execute().use { resp ->
            if (!resp.isSuccessful) throw IllegalStateException("Download failed (${resp.code}).")
            val body = resp.body ?: throw IllegalStateException("Empty download.")
            val total = body.contentLength()
            body.byteStream().use { input ->
                out.outputStream().use { output ->
                    val buf = ByteArray(64 * 1024)
                    var done = 0L
                    while (true) {
                        val n = input.read(buf)
                        if (n < 0) break
                        output.write(buf, 0, n)
                        done += n
                        onProgress(if (total > 0) done.toFloat() / total else -1f)
                    }
                }
            }
        }
        out
    }

    fun canInstall(context: Context): Boolean = context.packageManager.canRequestPackageInstalls()

    /** Opens the "allow Keja to install apps" screen (needed once). */
    fun openInstallPermissionSettings(context: Context) {
        context.startActivity(
            Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:${context.packageName}"))
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
        )
    }

    fun install(context: Context, apk: File) {
        val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", apk)
        context.startActivity(
            Intent(Intent.ACTION_VIEW)
                .setDataAndType(uri, "application/vnd.android.package-archive")
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK),
        )
    }
}
