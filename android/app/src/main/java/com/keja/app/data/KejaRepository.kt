package com.keja.app.data

import com.google.gson.Gson
import com.keja.app.data.model.*
import com.keja.app.data.network.ApiClient
import com.keja.app.data.network.KejaApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import retrofit2.Response
import java.io.File

/** Thrown with a message that's already the clean, user-facing string
 * (mirrors app.js's api() helper, which always throws Error(detail)). */
class ApiException(message: String) : Exception(message)

class KejaRepository(private val sessionStore: SessionStore) {
    private val api: KejaApi by lazy { ApiClient.get(sessionStore) }
    private val gson = Gson()

    private val _currentUser = MutableStateFlow<User?>(null)
    val currentUser: StateFlow<User?> = _currentUser.asStateFlow()

    suspend fun restoreSession() {
        // userFlow is a Flow; take the latest snapshot once at startup.
        // The UI re-fetches /users/me right after anyway, so this is
        // just to avoid a flash of "logged out" while that call is in flight.
    }

    fun setCurrentUser(user: User?) { _currentUser.value = user }

    private fun <T> unwrap(response: Response<T>): T {
        if (response.isSuccessful) {
            return response.body() ?: throw ApiException("Empty response from server")
        }
        val errorBody = response.errorBody()?.string()
        val message = errorBody?.let {
            runCatching { gson.fromJson(it, ApiError::class.java) }.getOrNull()
        }?.let { it.detail ?: it.message }
        throw ApiException(message ?: "Something went wrong (${response.code()})")
    }

    suspend fun register(body: RegisterRequest) = unwrap(api.register(body))

    suspend fun login(email: String, password: String): TokenResponse {
        val token = unwrap(api.login(LoginRequest(email, password)))
        // Save token first so the immediate /users/me call below can use it.
        sessionStore.save(token.access_token, User(id = "", email = email, name = null, username = null, phone = null, profile_pic_url = null))
        val user = unwrap(api.me())
        sessionStore.save(token.access_token, user)
        _currentUser.value = user
        return token
    }

    suspend fun logout() {
        sessionStore.clear()
        _currentUser.value = null
    }

    suspend fun refreshMe(): User {
        val user = unwrap(api.me())
        sessionStore.updateUser(user)
        _currentUser.value = user
        return user
    }

    suspend fun hostVerificationStatus() = unwrap(api.hostVerificationStatus())
    suspend fun requestHostVerification(governmentId: String, phone: String) =
        unwrap(api.requestHostVerification(HostVerificationRequest(governmentId, phone)))

    suspend fun listProperties(limit: Int = 50, q: String? = null, propertyType: String? = null) =
        unwrap(api.listProperties(limit, q, propertyType))

    suspend fun discover(limit: Int = 30) = unwrap(api.discover(limit))
    suspend fun interested() = unwrap(api.interested())
    suspend fun myListings() = unwrap(api.myListings())
    suspend fun myStats() = unwrap(api.myStats())
    suspend fun getProperty(id: String) = unwrap(api.getProperty(id))
    suspend fun createProperty(body: PropertyCreateRequest) = unwrap(api.createProperty(body))
    suspend fun updateProperty(id: String, body: PropertyUpdateRequest) = unwrap(api.updateProperty(id, body))
    suspend fun swipe(id: String, direction: String) = unwrap(api.swipe(id, direction))
    suspend fun removeInterested(id: String) = unwrap(api.removeInterested(id))
    suspend fun landlordProperties(id: String) = unwrap(api.landlordProperties(id))
    suspend fun contactStatus(id: String) = unwrap(api.contactStatus(id))
    suspend fun submitClaim(id: String, rawText: String) = unwrap(api.submitClaim(id, ClaimRequest(rawText)))
    suspend fun useFreeCredit(id: String) = unwrap(api.useFreeCredit(id))
    suspend fun adminStats() = unwrap(api.adminStats())

    suspend fun uploadImage(propertyId: String, file: File, isMain: Boolean) {
        val requestFile = file.asRequestBody("image/*".toMediaTypeOrNull())
        val part = MultipartBody.Part.createFormData("file", file.name, requestFile)
        unwrap(api.uploadImage(propertyId, isMain, part))
    }

    suspend fun uploadAvatar(file: File, mime: String): String {
        val body = file.asRequestBody(mime.toMediaTypeOrNull())
        val part = MultipartBody.Part.createFormData("file", file.name, body)
        return unwrap(api.uploadAvatar(part)).profile_pic_url
    }

    suspend fun activeAd(placement: String): AdSlotDto? = unwrap(api.activeAd(placement)).ad
    suspend fun adminAds(): List<AdSlotDto> = unwrap(api.adminAds()).ads

    suspend fun adminUploadAd(placement: String, file: File, mime: String, linkUrl: String?): AdSlotDto {
        val body = file.asRequestBody(mime.toMediaTypeOrNull())
        val part = MultipartBody.Part.createFormData("file", file.name, body)
        val text = "text/plain".toMediaTypeOrNull()
        return unwrap(
            api.adminCreateAd(
                placement.toRequestBody(text),
                linkUrl?.takeIf { it.isNotBlank() }?.toRequestBody(text),
                part,
            ),
        )
    }

    suspend fun adminUpdateAd(id: String, linkUrl: String? = null, isActive: Boolean? = null): AdSlotDto =
        unwrap(api.adminUpdateAd(id, AdUpdateRequest(linkUrl, isActive)))

    // ---- Alerts ----
    suspend fun notifications(): List<NotificationDto> = unwrap(api.notifications())
    suspend fun readAllNotifications() { unwrap(api.readAllNotifications()) }

    // ---- Landlord ----
    suspend fun uploadIdImage(file: File, mime: String) {
        val body = file.asRequestBody(mime.toMediaTypeOrNull())
        unwrap(api.uploadIdImage(MultipartBody.Part.createFormData("file", file.name, body)))
    }
    suspend fun deleteProperty(id: String) { unwrap(api.deleteProperty(id)) }
    suspend fun requestReferral(id: String) = unwrap(api.requestReferral(id))

    // ---- Admin ----
    suspend fun adminOverview() = unwrap(api.adminOverview())
    suspend fun adminProperties(review: String = "all") = unwrap(api.adminProperties(review))
    suspend fun adminReviewProperty(id: String, action: String, note: String?) { unwrap(api.adminReviewProperty(id, ReviewPropertyRequest(action, note))) }
    suspend fun adminForceBooked(id: String, booked: Boolean) { unwrap(api.adminForceBooked(id, ForceBookedRequest(booked))) }
    suspend fun adminLandlordIdImage(id: String) = unwrap(api.adminLandlordIdImage(id))
    suspend fun adminPendingLandlords() = unwrap(api.adminPendingLandlords())
    suspend fun adminVerifyLandlord(id: String, approve: Boolean, note: String?) { unwrap(api.adminVerifyLandlord(id, VerifyHostRequest(approve, note))) }
    suspend fun adminPendingPayments() = unwrap(api.adminPendingPayments())
    suspend fun adminShowContact(id: String) { unwrap(api.adminShowContact(id)) }
    suspend fun adminRejectPayment(id: String, reason: String?) { unwrap(api.adminRejectPayment(id, RejectPaymentRequest(reason))) }
}
