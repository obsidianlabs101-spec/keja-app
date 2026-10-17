package com.keja.app.data.network

import okhttp3.Interceptor
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.OkHttpClient
import okhttp3.Protocol
import okhttp3.Request
import okhttp3.Response
import okhttp3.ResponseBody.Companion.toResponseBody
import java.io.File
import java.io.IOException
import java.security.MessageDigest
import java.util.concurrent.ConcurrentHashMap

/**
 * Response cache for public, non-personal GET requests: memory + disk,
 * with "stale-while-revalidate".
 *
 *  - fresh copy (within its TTL)          -> answered instantly from memory
 *  - older copy of a FEED request         -> still answered instantly, and
 *    (Home list, counts, categories...)      refreshed in the background, so
 *                                            the app opens instantly even if
 *                                            the server is waking up
 *  - no copy                              -> asked from the server
 *  - server unreachable / failing         -> an older copy (up to 24h) is
 *                                            shown instead of an error
 *
 * Disk copies survive closing the app, so the SECOND open of the day is
 * instant too. Any successful write (new listing, swipe, comment, admin
 * change...) empties the cache, so you never look at stale data after
 * changing something yourself. Entries are keyed by URL + login token, so
 * accounts never see each other's data.
 */
class ResponseCacheInterceptor(private val dir: File) : Interceptor {

    /** Set by ApiClient once the OkHttpClient exists (used for background refreshes). */
    @Volatile var refreshClient: OkHttpClient? = null

    private class Entry(val savedAt: Long, val ttl: Long, val swr: Boolean, val body: ByteArray, val contentType: String?)

    private val memory = ConcurrentHashMap<String, Entry>()
    private val refreshing = ConcurrentHashMap.newKeySet<String>()

    private class Rule(val ttl: Long, val swr: Boolean)

    private fun rule(path: String): Rule? = when {
        path == "/properties/" || path == "/properties" -> Rule(45_000, true)
        path == "/properties/category-counts" -> Rule(60_000, true)
        path == "/properties/categories" || path == "/properties/locations" -> Rule(300_000, true)
        path.startsWith("/ads/") -> Rule(120_000, true)
        path == "/properties/discover" -> Rule(120_000, false) // same order when you come back; reshuffles after 2 min
        UUID_PATH.matches(path) -> Rule(60_000, false)          // one listing's details
        path.startsWith("/properties/landlord/") -> Rule(60_000, false)
        else -> null
    }

    override fun intercept(chain: Interceptor.Chain): Response {
        val request = chain.request()
        val path = request.url.encodedPath

        if (request.method != "GET") {
            val response = chain.proceed(request)
            if (response.isSuccessful) clearAll()
            return response
        }

        val rule = rule(path) ?: return chain.proceed(request)
        val isRefresh = request.header(REFRESH_HEADER) != null
        val key = (request.header("Authorization") ?: "") + "|" + request.url
        val now = System.currentTimeMillis()
        val entry = if (isRefresh) null else load(key)

        if (entry != null) {
            val age = now - entry.savedAt
            if (age < entry.ttl) return fromEntry(request, entry, "hit")
            if (entry.swr && age < SWR_MAX_AGE) {
                refreshInBackground(request, key)
                return fromEntry(request, entry, "stale")
            }
        }

        val response = try {
            chain.proceed(request.newBuilder().removeHeader(REFRESH_HEADER).build())
        } catch (e: IOException) {
            // Offline / server asleep and timing out: an old copy beats an error screen.
            val old = load(key)
            if (old != null && now - old.savedAt < OFFLINE_MAX_AGE) return fromEntry(request, old, "offline")
            throw e
        }

        if (response.code == 200) {
            val body = response.body ?: return response
            val bytes = body.bytes()
            if (bytes.size <= MAX_BYTES) store(key, Entry(now, rule.ttl, rule.swr, bytes, body.contentType()?.toString()))
            return response.newBuilder().body(bytes.toResponseBody(body.contentType())).build()
        }
        if (response.code >= 500) {
            val old = load(key)
            if (old != null && now - old.savedAt < OFFLINE_MAX_AGE) { response.close(); return fromEntry(request, old, "error-fallback") }
        }
        return response
    }

    // ---------------------------------------------------------------- helpers
    private fun fromEntry(request: Request, e: Entry, state: String): Response =
        Response.Builder()
            .request(request)
            .protocol(Protocol.HTTP_1_1)
            .code(200)
            .message("OK (cached)")
            .header("X-Keja-Cache", state)
            .body(e.body.toResponseBody(e.contentType?.toMediaTypeOrNull()))
            .build()

    private fun refreshInBackground(request: Request, key: String) {
        val client = refreshClient ?: return
        if (!refreshing.add(key)) return
        // Same request again, marked so it skips the cache lookup but still stores the result.
        val again = request.newBuilder().header(REFRESH_HEADER, "1").build()
        client.newCall(again).enqueue(object : okhttp3.Callback {
            override fun onFailure(call: okhttp3.Call, e: IOException) { refreshing.remove(key) }
            override fun onResponse(call: okhttp3.Call, response: Response) { response.close(); refreshing.remove(key) }
        })
    }

    private fun clearAll() {
        memory.clear()
        runCatching { dir.listFiles()?.forEach { it.delete() } }
    }

    private fun fileFor(key: String): File {
        val sha = MessageDigest.getInstance("SHA-1").digest(key.toByteArray()).joinToString("") { "%02x".format(it) }
        return File(dir, sha)
    }

    private fun store(key: String, e: Entry) {
        if (memory.size > MAX_ENTRIES) memory.entries.removeIf { System.currentTimeMillis() - it.value.savedAt > SWR_MAX_AGE }
        memory[key] = e
        runCatching {
            dir.mkdirs()
            // line 1: savedAt|ttl|swr|contentType ; rest: body
            val head = "${e.savedAt}|${e.ttl}|${if (e.swr) 1 else 0}|${e.contentType ?: ""}\n".toByteArray()
            fileFor(key).writeBytes(head + e.body)
        }
    }

    private fun load(key: String): Entry? {
        memory[key]?.let { return it }
        return runCatching {
            val f = fileFor(key)
            if (!f.exists()) return null
            val raw = f.readBytes()
            val nl = raw.indexOf('\n'.code.toByte())
            if (nl < 0) return null
            val parts = String(raw, 0, nl).split("|", limit = 4)
            val e = Entry(parts[0].toLong(), parts[1].toLong(), parts[2] == "1", raw.copyOfRange(nl + 1, raw.size), parts.getOrNull(3)?.ifBlank { null })
            if (System.currentTimeMillis() - e.savedAt > OFFLINE_MAX_AGE) { f.delete(); return null }
            memory[key] = e
            e
        }.getOrNull()
    }

    private companion object {
        const val REFRESH_HEADER = "X-Keja-Refresh"
        const val MAX_BYTES = 1_500_000
        const val MAX_ENTRIES = 120
        const val SWR_MAX_AGE = 30 * 60 * 1000L        // feeds may be shown up to 30 min old while refreshing
        const val OFFLINE_MAX_AGE = 24 * 60 * 60 * 1000L // ...and up to 24h old if the server can't be reached
        val UUID_PATH = Regex("^/properties/[0-9a-fA-F-]{36}$")
    }
}
