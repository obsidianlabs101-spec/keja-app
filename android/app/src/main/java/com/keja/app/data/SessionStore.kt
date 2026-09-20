package com.keja.app.data

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.google.gson.Gson
import com.keja.app.data.model.User
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.first

private val Context.dataStore by preferencesDataStore(name = "keja_session")

class SessionStore(private val context: Context) {
    private val tokenKey = stringPreferencesKey("token")
    private val userJsonKey = stringPreferencesKey("user_json")
    private val gson = Gson()

    val tokenFlow: Flow<String?> = context.dataStore.data.map { it[tokenKey] }
    val userFlow: Flow<User?> = context.dataStore.data.map { prefs ->
        prefs[userJsonKey]?.let { runCatching { gson.fromJson(it, User::class.java) }.getOrNull() }
    }

    suspend fun currentToken(): String? = context.dataStore.data.first()[tokenKey]

    suspend fun save(token: String, user: User) {
        context.dataStore.edit { prefs ->
            prefs[tokenKey] = token
            prefs[userJsonKey] = gson.toJson(user)
        }
    }

    suspend fun updateUser(user: User) {
        context.dataStore.edit { prefs -> prefs[userJsonKey] = gson.toJson(user) }
    }

    suspend fun clear() {
        context.dataStore.edit { it.clear() }
    }
}
