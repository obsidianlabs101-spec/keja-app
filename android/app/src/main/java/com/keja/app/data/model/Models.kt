package com.keja.app.data.model

data class PropertyImage(
    val id: String,
    val url: String,
    val is_main: Boolean,
    val sort_order: Int,
)

data class Property(
    val id: String,
    val landlord_id: String,
    val title: String,
    val description: String?,
    val price: Double,
    val property_type: String,
    val bedrooms: Int?,
    val bathrooms: Int?,
    val county: String,
    val area: String?,
    val proximity_note: String?,
    val main_image_url: String?,
    val is_available: Boolean,
    val is_booked: Boolean,
    val view_count: Int,
    val created_at: String?,
    val images: List<PropertyImage> = emptyList(),
)

data class LandlordSummary(
    val id: String,
    val full_name: String,
    val username: String?,
)

data class LandlordPropertiesResponse(
    val landlord: LandlordSummary,
    val properties: List<Property>,
)

data class User(
    val id: String,
    val email: String?,
    val name: String?,
    val username: String?,
    val phone: String?,
    val profile_pic_url: String?,
    val is_host: Boolean = false,
    val is_admin: Boolean = false,
    val host_verification_status: String? = null,
    val free_contact_credits: Int = 0,
    val referral_bonus_granted: Boolean = false,
    val referral_code: String? = null,
)

data class LoginRequest(val email: String, val password: String)
data class RegisterRequest(
    val full_name: String,
    val username: String,
    val email: String,
    val phone: String,
    val password: String,
    val ref: String? = null,
)
data class TokenResponse(val access_token: String, val token_type: String? = null)

data class ContactUnlockStatus(
    val property_id: String,
    val status: String, // pending | awaiting_admin_match | unlocked
    val amount: Double,
    val phone: String?,
    val whatsapp: String?,
    val unlocked_at: String?,
    val free_credits_available: Int = 0,
)
data class ClaimRequest(val raw_text: String)

data class PropertyCreateRequest(
    val title: String,
    val description: String?,
    val price: Double,
    val property_type: String,
    val bedrooms: Int?,
    val bathrooms: Int?,
    val county: String,
    val area: String?,
    val proximity_note: String?,
)
data class PropertyUpdateRequest(
    val is_booked: Boolean? = null,
    val is_available: Boolean? = null,
)

data class LandlordStats(
    val active_listings: Int,
    val total_views: Int,
    val interested_count: Int,
    val contact_unlocks: Int,
    val contact_unlocks_revenue: Double,
)

data class AdminStats(
    val total_properties: Int,
    val active_landlords: Int,
    val total_users: Int,
    val pending_verifications: Int,
)

data class HostVerificationRequest(val government_id: String, val phone: String)
data class HostVerificationStatus(val host_verification_status: String?)

data class ApiError(val detail: String? = null, val message: String? = null)
