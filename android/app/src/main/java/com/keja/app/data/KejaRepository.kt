package com.keja.app.data

import com.google.gson.Gson
import com.keja.app.data.model.*
import com.keja.app.data.network.ApiClient
import com.keja.app.data.network.KejaApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.first
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
class ApiException(message: String, val code: Int = 0) : Exception(message)

class KejaRepository(private val sessionStore: SessionStore) {
    private val api: KejaApi by lazy { ApiClient.get(sessionStore) }
    private val gson = Gson()

    private val _currentUser = MutableStateFlow<User?>(null)
    val currentUser: StateFlow<User?> = _currentUser.asStateFlow()

    /**
     * Opens the app already signed in. The saved user is read from the phone BEFORE the first
     * screen is drawn, so a slow or sleeping server (or no signal) can never make a signed-in
     * person look logged out.
     */
    suspend fun restoreSession() {
        val token = sessionStore.currentToken()
        if (token.isNullOrBlank()) return
        val saved = sessionStore.userFlow.first()
        if (saved != null && saved.id.isNotBlank()) _currentUser.value = saved
    }

    /**
     * Re-checks the login in the background (and refreshes the profile). Only a definite
     * "this token is not valid" answer from the server (HTTP 401: account removed, or "log out
     * all devices" was used) ends the session. Timeouts, being offline or a server that is
     * still waking up just retry — they never log anyone out.
     */
    suspend fun refreshMeQuietly() {
        for (wait in listOf(0L, 4_000L, 12_000L)) {
            if (wait > 0) kotlinx.coroutines.delay(wait)
            try {
                refreshMe()
                return
            } catch (e: ApiException) {
                if (e.code == 401) { logout(); return }
            } catch (e: Exception) {
                // offline / timed out: keep the saved session and try again
            }
        }
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
        throw ApiException(message ?: "Something went wrong (${response.code()})", response.code())
    }

    suspend fun register(body: RegisterRequest) = unwrap(api.register(body))

    suspend fun resendVerification(email: String) = unwrap(api.resendVerification(ResendVerificationRequest(email)))

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

    suspend fun categoryCounts(listingType: String? = null) = unwrap(api.categoryCounts(listingType))

    suspend fun discover(limit: Int = 30, offset: Int = 0, seed: String? = null, listingType: String? = null) =
        unwrap(api.discover(limit, offset, seed, listingType))
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

    // ---- Catalog: admin-managed categories + keyword locations
    /** Fetches the lists and stores them in [Catalog] so any screen can use them synchronously. */
    suspend fun refreshCatalog() {
        runCatching { unwrap(api.catalogCategories()) }.onSuccess { Catalog.categories = it }
        runCatching { unwrap(api.catalogLocations()) }.onSuccess { Catalog.locations = it }
    }
    suspend fun adminCatalog() = unwrap(api.adminCatalog())
    suspend fun adminAddCategory(name: String, group: String) = unwrap(api.adminAddCategory(CategoryBody(name, group)))
    suspend fun adminRenameCategory(id: String, name: String) = unwrap(api.adminPatchCategory(id, CategoryPatchBody(name = name)))
    suspend fun adminSetCategoryActive(id: String, active: Boolean) = unwrap(api.adminPatchCategory(id, CategoryPatchBody(active = active)))
    suspend fun adminDeleteCategory(id: String) { unwrap(api.adminDeleteCategory(id)) }
    suspend fun adminAddLocation(name: String) = unwrap(api.adminAddLocation(LocationBody(name)))
    suspend fun adminSetLocationActive(id: String, active: Boolean) = unwrap(api.adminPatchLocation(id, LocationPatchBody(active = active)))
    suspend fun adminDeleteLocation(id: String) { unwrap(api.adminDeleteLocation(id)) }
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

    suspend fun getMyAlert(): PropertyAlertDto? = try { unwrap(api.getMyAlert()) } catch (e: Exception) { null }
    suspend fun setMyAlert(alert: PropertyAlertDto): PropertyAlertDto = unwrap(api.setMyAlert(alert))
    suspend fun clearMyAlert() { unwrap(api.clearMyAlert()) }

    suspend fun hostComments(landlordId: String) = unwrap(api.hostComments(landlordId))
    suspend fun setHostComment(landlordId: String, body: String) = unwrap(api.setHostComment(landlordId, HostCommentCreateRequest(body)))
    suspend fun deleteHostComment(landlordId: String) { unwrap(api.deleteHostComment(landlordId)) }
}
