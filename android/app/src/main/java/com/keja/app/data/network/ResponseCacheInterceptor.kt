package com.keja.app.data.network

import okhttp3.Interceptor
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.Protocol
import okhttp3.Response
import okhttp3.ResponseBody.Companion.toResponseBody
import java.util.concurrent.ConcurrentHashMap

/**
 * Short-lived in-memory cache for public, non-personal GET requests.
 *
 * Why: every time you moved Home -> a listing -> back, the app asked the
 * server (and so the database) for exactly the same data again. Now identical
 * requests are answered from memory for a short while. Any successful write
 * (new listing, swipe, comment, admin change...) empties the cache, so you
 * never look at stale data after changing something yourself.
 *
 * Only success (200) responses are stored, so a failed/slow request is always
 * retried next time. Entries are keyed by URL + login token, so accounts never
 * see each other's data.
 */
class ResponseCacheInterceptor : Interceptor {

    private class Entry(val expiresAt: Long, val body: ByteArray, val contentType: String?)

    private val store = ConcurrentHashMap<String, Entry>()

    private fun ttlMs(path: String): Long = when {
        path == "/properties/" || path == "/properties" -> 45_000
        path == "/properties/category-counts" -> 60_000
        path == "/properties/categories" || path == "/properties/locations" -> 300_000
        path.startsWith("/ads/") -> 120_000
        path == "/properties/discover" -> 120_000 // same order when you come back; reshuffles after 2 min
        UUID_PATH.matches(path) -> 60_000          // one listing's details
        path.startsWith("/properties/landlord/") -> 60_000
        else -> 0
    }

    override fun intercept(chain: Interceptor.Chain): Response {
        val request = chain.request()
        val path = request.url.encodedPath

        if (request.method != "GET") {
            val response = chain.proceed(request)
            if (response.isSuccessful) store.clear()
            return response
        }

        val ttl = ttlMs(path)
        if (ttl == 0L) return chain.proceed(request)

        val key = (request.header("Authorization") ?: "") + "|" + request.url
        val now = System.currentTimeMillis()
        store[key]?.let { e ->
            if (e.expiresAt > now) {
                return Response.Builder()
                    .request(request)
                    .protocol(Protocol.HTTP_1_1)
                    .code(200)
                    .message("OK (cached)")
                    .header("X-Keja-Cache", "hit")
                    .body(e.body.toResponseBody(e.contentType?.toMediaTypeOrNull()))
                    .build()
            }
            store.remove(key)
        }

        val response = chain.proceed(request)
        if (response.code == 200) {
            val body = response.body ?: return response
            val bytes = body.bytes()
            if (bytes.size <= MAX_BYTES) {
                if (store.size > MAX_ENTRIES) store.entries.removeIf { it.value.expiresAt < now }
                store[key] = Entry(now + ttl, bytes, body.contentType()?.toString())
            }
            // body.bytes() consumed the stream, so hand back a fresh copy.
            return response.newBuilder().body(bytes.toResponseBody(body.contentType())).build()
        }
        return response
    }

    private companion object {
        const val MAX_BYTES = 1_500_000
        const val MAX_ENTRIES = 120
        val UUID_PATH = Regex("^/properties/[0-9a-fA-F-]{36}$")
    }
}
