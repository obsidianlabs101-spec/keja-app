package com.keja.app.data

/**
 * A shuffle seed that stays the same for ~10 minutes: leaving Discover and
 * coming back keeps your place and order, while a later visit reshuffles.
 * The server uses it so page 2 continues page 1 with no repeats or gaps.
 */
object DiscoverSeed {
    private var value: String? = null
    private var createdAt = 0L

    @Synchronized
    fun current(): String {
        val now = System.currentTimeMillis()
        val v = value
        if (v == null || now - createdAt > 10 * 60 * 1000) {
            value = java.lang.Long.toString(kotlin.random.Random.nextLong(Long.MAX_VALUE), 36)
            createdAt = now
        }
        return value!!
    }
}
