package com.keja.app.data.network

import com.keja.app.data.model.*
import okhttp3.MultipartBody
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
}
