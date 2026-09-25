package com.keja.app.data.network

import com.keja.app.data.model.*
import okhttp3.MultipartBody
import okhttp3.RequestBody
import okhttp3.ResponseBody
import retrofit2.Response
import retrofit2.http.*

interface KejaApi {
    @POST("register")
    suspend fun register(@Body body: RegisterRequest): Response<ResponseBody>

    @POST("login")
    suspend fun login(@Body body: LoginRequest): Response<TokenResponse>

    @GET("users/me")
    suspend fun me(): Response<User>

    @GET("users/host-verification/me")
    suspend fun hostVerificationStatus(): Response<HostVerificationStatus>

    @POST("users/host-verification/request")
    suspend fun requestHostVerification(@Body body: HostVerificationRequest): Response<ResponseBody>

    @GET("properties/")
    suspend fun listProperties(
        @Query("limit") limit: Int = 50,
        @Query("q") q: String? = null,
        @Query("property_type") propertyType: String? = null,
    ): Response<List<Property>>

    @GET("properties/discover")
    suspend fun discover(@Query("limit") limit: Int = 30): Response<List<Property>>

    @GET("properties/interested")
    suspend fun interested(): Response<List<Property>>

    @GET("properties/mine")
    suspend fun myListings(): Response<List<Property>>

    @GET("properties/mine/stats")
    suspend fun myStats(): Response<LandlordStats>

    @GET("properties/{id}")
    suspend fun getProperty(@Path("id") id: String): Response<Property>

    @POST("properties/create")
    suspend fun createProperty(@Body body: PropertyCreateRequest): Response<Property>

    @PATCH("properties/{id}")
    suspend fun updateProperty(@Path("id") id: String, @Body body: PropertyUpdateRequest): Response<Property>

    @Multipart
    @POST("properties/{id}/images")
    suspend fun uploadImage(
        @Path("id") id: String,
        @Query("is_main") isMain: Boolean,
        @Part file: MultipartBody.Part,
    ): Response<ResponseBody>

    @POST("properties/{id}/swipe")
    suspend fun swipe(@Path("id") id: String, @Query("direction") direction: String): Response<ResponseBody>

    @DELETE("properties/{id}/interested")
    suspend fun removeInterested(@Path("id") id: String): Response<ResponseBody>

    @Multipart
    @POST("users/me/avatar")
    suspend fun uploadAvatar(@Part file: MultipartBody.Part): Response<AvatarResponse>

    @GET("properties/landlord/{id}")
    suspend fun landlordProperties(@Path("id") id: String): Response<LandlordPropertiesResponse>

    @GET("contact-unlock/{id}")
    suspend fun contactStatus(@Path("id") id: String): Response<ContactUnlockStatus>

    @POST("contact-unlock/{id}/claim")
    suspend fun submitClaim(@Path("id") id: String, @Body body: ClaimRequest): Response<ContactUnlockStatus>

    @POST("contact-unlock/{id}/use-free-credit")
    suspend fun useFreeCredit(@Path("id") id: String): Response<ContactUnlockStatus>

    @GET("admin/platform-stats")
    suspend fun adminStats(): Response<AdminStats>

    @GET("ads/{placement}")
    suspend fun activeAd(@Path("placement") placement: String): Response<ActiveAdResponse>

    @GET("admin/ads")
    suspend fun adminAds(): Response<AdListResponse>

    @Multipart
    @POST("admin/ads")
    suspend fun adminCreateAd(
        @Part("placement") placement: RequestBody,
        @Part("link_url") linkUrl: RequestBody?,
        @Part file: MultipartBody.Part,
    ): Response<AdSlotDto>

    @PATCH("admin/ads/{id}")
    suspend fun adminUpdateAd(@Path("id") id: String, @Body body: AdUpdateRequest): Response<AdSlotDto>

    // ---- Alerts ----
    @GET("users/notifications")
    suspend fun notifications(@Query("context") context: String = "user"): Response<List<NotificationDto>>

    @POST("users/notifications/read-all")
    suspend fun readAllNotifications(): Response<ResponseBody>

    // ---- Landlord ID photo + deleting a listing ----
    @Multipart
    @POST("users/me/id-image")
    suspend fun uploadIdImage(@Part file: MultipartBody.Part): Response<ResponseBody>

    @DELETE("properties/{id}")
    suspend fun deleteProperty(@Path("id") id: String): Response<ResponseBody>

    @POST("contact-unlock/{id}/request-referral")
    suspend fun requestReferral(@Path("id") id: String): Response<ContactUnlockStatus>

    // ---- Admin ----
    @GET("admin/keja/overview")
    suspend fun adminOverview(): Response<AdminOverview>

    @GET("admin/keja/properties")
    suspend fun adminProperties(@Query("review") review: String = "all"): Response<List<AdminPropertyDto>>

    @POST("admin/keja/properties/{id}/review")
    suspend fun adminReviewProperty(@Path("id") id: String, @Body body: ReviewPropertyRequest): Response<ResponseBody>

    @POST("admin/keja/properties/{id}/force-booked")
    suspend fun adminForceBooked(@Path("id") id: String, @Body body: ForceBookedRequest): Response<ResponseBody>

    @GET("admin/keja/landlords/{id}/id-image")
    suspend fun adminLandlordIdImage(@Path("id") id: String): Response<IdImageDto>

    @GET("admin/hosts/pending")
    suspend fun adminPendingLandlords(): Response<List<PendingLandlordDto>>

    @POST("admin/hosts/{id}/verify")
    suspend fun adminVerifyLandlord(@Path("id") id: String, @Body body: VerifyHostRequest): Response<ResponseBody>

    @GET("contact-unlock/admin/pending")
    suspend fun adminPendingPayments(): Response<List<PendingPaymentDto>>

    @POST("contact-unlock/admin/{id}/show")
    suspend fun adminShowContact(@Path("id") id: String): Response<ResponseBody>

    @POST("contact-unlock/admin/{id}/reject")
    suspend fun adminRejectPayment(@Path("id") id: String, @Body body: RejectPaymentRequest): Response<ResponseBody>
}
