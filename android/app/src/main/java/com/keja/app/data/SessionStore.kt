package com.keja.app.data

import android.content.Context
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.google.gson.Gson
import com.keja.app.data.model.User
import com.keja.app.ui.theme.KejaThemeStyle
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.first

private val Context.dataStore by preferencesDataStore(name = "keja_session")

class SessionStore(private val context: Context) {
    private val tokenKey = stringPreferencesKey("token")
    private val userJsonKey = stringPreferencesKey("user_json")
    private val themeStyleKey = stringPreferencesKey("theme_style") // "pro" | "rangi"
    private val darkOverrideKey = booleanPreferencesKey("dark_override") // absent = follow system
    private val gson = Gson()

    val tokenFlow: Flow<String?> = context.dataStore.data.map { it[tokenKey] }
    val userFlow: Flow<User?> = context.dataStore.data.map { prefs ->
        prefs[userJsonKey]?.let { runCatching { gson.fromJson(it, User::class.java) }.getOrNull() }
    }

    // null = follow the system's light/dark setting, same default as the website.
    val darkOverrideFlow: Flow<Boolean?> = context.dataStore.data.map { it[darkOverrideKey] }
    val themeStyleFlow: Flow<KejaThemeStyle> = context.dataStore.data.map { prefs ->
        if (prefs[themeStyleKey] == "rangi") KejaThemeStyle.RANGI else KejaThemeStyle.PROFESSIONAL
    }

    suspend fun setDarkOverride(value: Boolean?) {
        context.dataStore.edit { prefs ->
            if (value == null) prefs.remove(darkOverrideKey) else prefs[darkOverrideKey] = value
        }
    }

    suspend fun setThemeStyle(style: KejaThemeStyle) {
        context.dataStore.edit { prefs -> prefs[themeStyleKey] = if (style == KejaThemeStyle.RANGI) "rangi" else "pro" }
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
        // Deliberately keep theme_style / dark_override — logging out
        // shouldn't reset a display preference the person already set.
        context.dataStore.edit { prefs ->
            prefs.remove(tokenKey)
            prefs.remove(userJsonKey)
        }
    }
}

