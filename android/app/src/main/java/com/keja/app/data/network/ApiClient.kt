package com.keja.app.data.network

import com.keja.app.data.SessionStore
import kotlinx.coroutines.runBlocking
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.Response
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

// Same live backend the website talks to — see frontend/app.js's
// API_BASE constant. Kept as a single constant here for the same reason.
const val API_BASE_URL = "https://keja-backend-uqzk.onrender.com/"

class AuthInterceptor(private val sessionStore: SessionStore) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val token = runBlocking { sessionStore.currentToken() }
        val request = chain.request().newBuilder().apply {
            if (!token.isNullOrBlank()) addHeader("Authorization", "Bearer $token")
        }.build()
        return chain.proceed(request)
    }
}

object ApiClient {
    @Volatile private var api: KejaApi? = null

    fun get(sessionStore: SessionStore): KejaApi {
        return api ?: synchronized(this) {
            api ?: build(sessionStore).also { api = it }
        }
    }

    private fun build(sessionStore: SessionStore): KejaApi {
        val client = OkHttpClient.Builder()
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .addInterceptor(AuthInterceptor(sessionStore))
            .build()

        return Retrofit.Builder()
            .baseUrl(API_BASE_URL)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(KejaApi::class.java)
    }
}
