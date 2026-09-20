package com.keja.app.data

import android.content.Context

/** Deliberately no Hilt/Koin here — a from-scratch CI build has enough
 * moving parts already; a hand-rolled singleton container keeps the
 * dependency graph (SessionStore -> Repository) trivial and obvious. */
object AppContainer {
    @Volatile private var repository: KejaRepository? = null
    @Volatile private var sessionStore: SessionStore? = null

    fun sessionStore(context: Context): SessionStore =
        sessionStore ?: synchronized(this) {
            sessionStore ?: SessionStore(context.applicationContext).also { sessionStore = it }
        }

    fun repository(context: Context): KejaRepository =
        repository ?: synchronized(this) {
            repository ?: KejaRepository(sessionStore(context)).also { repository = it }
        }
}
