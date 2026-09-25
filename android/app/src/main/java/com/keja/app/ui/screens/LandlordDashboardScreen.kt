package com.keja.app.ui.screens

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.keja.app.data.AppContainer
import com.keja.app.data.ApiException
import com.keja.app.data.model.LandlordStats
import com.keja.app.data.model.Property
import com.keja.app.data.model.PropertyCreateRequest
import com.keja.app.data.model.PropertyUpdateRequest
import com.keja.app.ui.components.AmenityPicker
import com.keja.app.ui.components.Amenities
import com.keja.app.ui.components.Avatar
import com.keja.app.ui.components.StatusPill
import com.keja.app.ui.components.resolveMediaUrl
import com.keja.app.ui.theme.KejaColors
import com.keja.app.ui.components.KejaPrimaryButton
import com.keja.app.ui.components.KejaSecondaryButton
import com.keja.app.ui.components.KejaTextField
import com.keja.app.ui.components.formatKes
import com.keja.app.ui.theme.LocalKejaPalette
import kotlinx.coroutines.launch

@Composable
fun LandlordDashboardScreen(onBack: () -> Unit, onOpenPublicProfile: (String) -> Unit = {}) {
    val palette = LocalKejaPalette.current
    val context = LocalContext.current
    val repo = remember { AppContainer.repository(context) }
    val scope = rememberCoroutineScope()
    val user by repo.currentUser.collectAsState()

    var verificationStatus by remember { mutableStateOf<String?>(null) }
    var checked by remember { mutableStateOf(false) }
    var listings by remember { mutableStateOf<List<Property>>(emptyList()) }
    var stats by remember { mutableStateOf<LandlordStats?>(null) }
    var showAddForm by remember { mutableStateOf(false) }
    var showBecomeForm by remember { mutableStateOf(false) }
    var editingAmenities by remember { mutableStateOf<Property?>(null) }
    var avatarUrl by remember { mutableStateOf<String?>(null) }
    var avatarMsg by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(user?.profile_pic_url) { if (avatarUrl == null) avatarUrl = user?.profile_pic_url }

    val avatarPicker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        if (uri != null) scope.launch {
            avatarMsg = "Uploading photo…"
            val file = copyUriToTempFile(context, uri)
            if (file == null) { avatarMsg = "Couldn't read that image"; return@launch }
            val mime = context.contentResolver.getType(uri) ?: "image/jpeg"
            avatarMsg = try {
                avatarUrl = repo.uploadAvatar(file, mime)
                runCatching { repo.refreshMe() }
                "Profile photo updated"
            } catch (e: Exception) { e.message ?: "Upload failed" }
            file.delete()
        }
    }

    fun refresh() {
        scope.launch {
            listings = runCatching { repo.myListings() }.getOrDefault(emptyList())
            stats = runCatching { repo.myStats() }.getOrNull()
        }
    }

    LaunchedEffect(user?.is_host) {
        if (user?.is_host == true) {
            refresh()
        } else {
            verificationStatus = runCatching { repo.hostVerificationStatus().host_verification_status }.getOrNull() ?: "none"
        }
        checked = true
    }

    Column(Modifier.fillMaxSize().background(palette.bg)) {
        Row(
            Modifier.fillMaxWidth().padding(20.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column {
                Text("LANDLORD", color = palette.primary, fontWeight = FontWeight.Bold, fontSize = 11.sp)
                Text("Dashboard", fontSize = 24.sp, fontWeight = FontWeight.ExtraBold, color = palette.text)
            }
            if (user?.is_host == true) {
                KejaPrimaryButton(text = "＋ Add", onClick = { showAddForm = true })
            } else {
                TextButton(onClick = onBack) { Text("Back") }
            }
        }

        if (!checked) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { com.keja.app.ui.components.KejaLoader() }
            return@Column
        }

        if (user?.is_host != true) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                if (verificationStatus == "pending") {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text("⏳", fontSize = 36.sp)
                        Spacer(Modifier.height(10.dp))
                        Text("Verification pending", fontWeight = FontWeight.Bold)
                        Text("We're reviewing your landlord application.", color = palette.muted, fontSize = 13.sp)
                    }
                } else if (showBecomeForm) {
                    BecomeLandlordForm(onDone = { showBecomeForm = false; verificationStatus = "pending" })
                } else {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text("⌂", fontSize = 36.sp)
                        Spacer(Modifier.height(10.dp))
                        Text("Become a landlord", fontWeight = FontWeight.Bold)
                        Text("List your property on Keja.", color = palette.muted, fontSize = 13.sp)
                        Spacer(Modifier.height(14.dp))
                        KejaPrimaryButton(text = "Get started", onClick = { showBecomeForm = true })
                    }
                }
            }
            return@Column
        }

        if (showAddForm) {
            AddPropertyForm(onPublished = { showAddForm = false; refresh() }, onCancel = { showAddForm = false })
            return@Column
        }

        // Profile strip: the landlord's photo (shown on every listing) + public profile shortcut
        Row(
            Modifier
                .fillMaxWidth()
                .padding(horizontal = 20.dp)
                .clip(RoundedCornerShape(16.dp))
                .background(palette.card)
                .padding(14.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Avatar(
                url = avatarUrl, name = user?.name, size = 60.dp,
                modifier = Modifier.clickable { avatarPicker.launch("image/*") },
            )
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(user?.name ?: "Your profile", fontWeight = FontWeight.Bold, color = palette.text)
                Text(avatarMsg ?: "Tap your photo to change it", fontSize = 11.sp, color = palette.muted)
            }
            KejaSecondaryButton(text = "View profile", onClick = { user?.id?.let(onOpenPublicProfile) })
        }
        Spacer(Modifier.height(14.dp))

        stats?.let { s ->
            Row(Modifier.fillMaxWidth().padding(horizontal = 20.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                StatTile("Listings", s.active_listings.toString(), Modifier.weight(1f))
                StatTile("Views", s.total_views.toString(), Modifier.weight(1f))
                StatTile("Interested", s.interested_count.toString(), Modifier.weight(1f))
                StatTile("Unlocks", s.contact_unlocks.toString(), Modifier.weight(1f))
            }
            Spacer(Modifier.height(16.dp))
        }

        Text(
            "My properties (${listings.size})",
            modifier = Modifier.padding(horizontal = 20.dp),
            fontWeight = FontWeight.ExtraBold, fontSize = 16.sp, color = palette.text,
        )
        Spacer(Modifier.height(8.dp))

        LazyColumn(
            Modifier.weight(1f),
            contentPadding = PaddingValues(start = 20.dp, end = 20.dp, top = 4.dp, bottom = 24.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (listings.isEmpty()) {
                item { Text("No listings yet — tap ＋ Add to publish your first property.", color = palette.muted) }
            }
            items(listings) { p ->
                LandlordListingRow(
                    p,
                    onToggleBooked = {
                        scope.launch {
                            runCatching { repo.updateProperty(p.id, PropertyUpdateRequest(is_booked = !p.is_booked)) }
                            refresh()
                        }
                    },
                    onEditAmenities = { editingAmenities = p },
                )
            }
        }
    }

    editingAmenities?.let { target ->
        var picked by remember(target.id) { mutableStateOf(target.amenities.toSet()) }
        AlertDialog(
            onDismissRequest = { editingAmenities = null },
            title = { Text("What does it have?") },
            text = {
                Column(Modifier.verticalScroll(rememberScrollState())) {
                    AmenityPicker(picked) { k -> picked = if (k in picked) picked - k else picked + k }
                }
            },
            confirmButton = {
                TextButton(onClick = {
                    scope.launch {
                        runCatching { repo.updateProperty(target.id, PropertyUpdateRequest(amenities = Amenities.all.map { it.key }.filter { it in picked })) }
                        editingAmenities = null
                        refresh()
                    }
                }) { Text("Save") }
            },
            dismissButton = { TextButton(onClick = { editingAmenities = null }) { Text("Cancel") } },
        )
    }
}

@Composable
private fun StatTile(label: String, value: String, modifier: Modifier = Modifier) {
    val palette = LocalKejaPalette.current
    Column(
        modifier
            .clip(RoundedCornerShape(14.dp))
            .background(palette.card)
            .padding(12.dp),
    ) {
        Text(label, fontSize = 11.sp, color = palette.muted)
        Text(value, fontSize = 20.sp, fontWeight = FontWeight.ExtraBold, color = palette.text)
    }
}

@Composable
private fun LandlordListingRow(p: Property, onToggleBooked: () -> Unit, onEditAmenities: () -> Unit) {
    val palette = LocalKejaPalette.current
    Column(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(16.dp))
            .background(palette.card)
            .padding(12.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            coil.compose.AsyncImage(
                model = resolveMediaUrl(p.main_image_url),
                contentDescription = null,
                contentScale = androidx.compose.ui.layout.ContentScale.Crop,
                modifier = Modifier.size(84.dp).clip(RoundedCornerShape(12.dp)),
            )
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(p.property_type, fontWeight = FontWeight.Bold, color = palette.text, fontSize = 15.sp)
                Text(formatKes(p.price) + " / month", fontWeight = FontWeight.SemiBold, color = palette.primary, fontSize = 13.sp)
                Text(p.area ?: p.county, fontSize = 12.sp, color = palette.muted)
                Spacer(Modifier.height(4.dp))
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    if (p.is_booked) StatusPill("Booked", KejaColors.BookedBg, KejaColors.BookedText)
                    else StatusPill("Available", KejaColors.AvailableBg, KejaColors.AvailableText)
                    Text("👁 ${p.view_count}", fontSize = 11.sp, color = palette.muted)
                    Text("✦ ${p.amenities.size}", fontSize = 11.sp, color = palette.muted)
                }
            }
        }
        Spacer(Modifier.height(10.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            KejaSecondaryButton(text = if (p.is_booked) "Mark available" else "Mark booked", onClick = onToggleBooked, modifier = Modifier.weight(1f))
            KejaSecondaryButton(text = "Amenities", onClick = onEditAmenities, modifier = Modifier.weight(1f))
        }
    }
}

@Composable
private fun BecomeLandlordForm(onDone: () -> Unit) {
    val context = LocalContext.current
    val repo = remember { AppContainer.repository(context) }
    val scope = rememberCoroutineScope()
    var govId by remember { mutableStateOf("") }
    var phone by remember { mutableStateOf("") }
    var idUri by remember { mutableStateOf<android.net.Uri?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(false) }

    val idPicker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri -> if (uri != null) idUri = uri }

    Column(Modifier.fillMaxWidth().padding(24.dp)) {
        Text("Become a landlord", fontWeight = FontWeight.Bold, fontSize = 18.sp)
        Spacer(Modifier.height(6.dp))
        Text("Verification is reviewed by our team to keep Keja trustworthy for renters.", fontSize = 12.sp)
        Spacer(Modifier.height(16.dp))
        KejaTextField(govId, { govId = it }, "Government ID number")
        Spacer(Modifier.height(12.dp))
        KejaTextField(phone, { phone = it }, "Phone for renter contact")
        Spacer(Modifier.height(12.dp))
        KejaSecondaryButton(text = if (idUri != null) "ID photo selected ✓ (tap to change)" else "Add a photo of your ID", onClick = { idPicker.launch("image/*") })
        Text("Only our admins can see this. It isn't shown to renters.", fontSize = 11.sp, color = Color.Gray)
        error?.let { Spacer(Modifier.height(8.dp)); Text(it, color = Color(0xFFEF4444), fontSize = 12.sp) }
        Spacer(Modifier.height(16.dp))
        KejaPrimaryButton(text = if (loading) "Submitting…" else "Submit for review", enabled = !loading, modifier = Modifier.fillMaxWidth()) {
            val uri = idUri
            if (uri == null) { error = "Please add a clear photo of your ID."; return@KejaPrimaryButton }
            loading = true
            scope.launch {
                try {
                    val temp = copyUriToTempFile(context, uri)
                    if (temp == null) { error = "Couldn't read that image"; loading = false; return@launch }
                    val mime = context.contentResolver.getType(uri) ?: "image/jpeg"
                    repo.uploadIdImage(temp, mime)
                    temp.delete()
                    repo.requestHostVerification(govId, phone)
                    onDone()
                } catch (e: ApiException) {
                    error = e.message
                } finally {
                    loading = false
                }
            }
        }
    }
}

private fun copyUriToTempFile(context: android.content.Context, uri: android.net.Uri): java.io.File? {
    return try {
        val ext = when (context.contentResolver.getType(uri)) {
            "image/png" -> ".png"
            "image/webp" -> ".webp"
            else -> ".jpg"
        }
        val temp = java.io.File.createTempFile("keja_upload_", ext, context.cacheDir)
        context.contentResolver.openInputStream(uri)?.use { input ->
            temp.outputStream().use { output -> input.copyTo(output) }
        }
        temp
    } catch (e: Exception) {
        null
    }
}

@Composable
private fun AddPropertyForm(onPublished: () -> Unit, onCancel: () -> Unit) {
    val context = LocalContext.current
    val repo = remember { AppContainer.repository(context) }
    val scope = rememberCoroutineScope()

    var type by remember { mutableStateOf("Bedsitter") }
    var price by remember { mutableStateOf("") }
    var location by remember { mutableStateOf("") }
    var landmark by remember { mutableStateOf("") }
    var desc by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(false) }
    var publishStatus by remember { mutableStateOf<String?>(null) }
    var selectedImages by remember { mutableStateOf<List<android.net.Uri>>(emptyList()) }
    var amenities by remember { mutableStateOf(setOf<String>()) }

    val imagePicker = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.GetMultipleContents(),
    ) { uris -> if (uris.isNotEmpty()) selectedImages = uris }

    Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(20.dp)) {
        Text("New listing", fontWeight = FontWeight.Bold, fontSize = 18.sp)
        Spacer(Modifier.height(14.dp))
        KejaTextField(type, { type = it }, "Property type (e.g. Bedsitter, 1 Bedroom, Airbnb)")
        Spacer(Modifier.height(12.dp))
        KejaTextField(price, { price = it }, "Monthly rent (KES)")
        Spacer(Modifier.height(12.dp))
        KejaTextField(location, { location = it }, "Location / area")
        Spacer(Modifier.height(12.dp))
        KejaTextField(landmark, { landmark = it }, "Nearby landmark")
        Spacer(Modifier.height(12.dp))
        KejaTextField(desc, { desc = it }, "Description")

        Spacer(Modifier.height(14.dp))
        Text("Photos", fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
        Spacer(Modifier.height(8.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            selectedImages.forEach { uri ->
                coil.compose.AsyncImage(
                    model = uri,
                    contentDescription = null,
                    contentScale = androidx.compose.ui.layout.ContentScale.Crop,
                    modifier = Modifier.size(64.dp).clip(androidx.compose.foundation.shape.RoundedCornerShape(10.dp)),
                )
            }
            Box(
                Modifier
                    .size(64.dp)
                    .clip(androidx.compose.foundation.shape.RoundedCornerShape(10.dp))
                    .border(1.dp, Color.Gray.copy(alpha = 0.4f), androidx.compose.foundation.shape.RoundedCornerShape(10.dp))
                    .clickable { imagePicker.launch("image/*") },
                contentAlignment = Alignment.Center,
            ) { Text("+", fontSize = 24.sp, color = Color.Gray) }
        }

        Spacer(Modifier.height(16.dp))
        Text("What does it have?", fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
        Text("Tick everything that applies — renters see these as icons on your listing.", fontSize = 11.sp, color = Color.Gray)
        Spacer(Modifier.height(8.dp))
        AmenityPicker(amenities) { k -> amenities = if (k in amenities) amenities - k else amenities + k }

        error?.let { Spacer(Modifier.height(8.dp)); Text(it, color = Color(0xFFEF4444), fontSize = 12.sp) }
        publishStatus?.let { Spacer(Modifier.height(8.dp)); Text(it, fontSize = 12.sp) }
        Spacer(Modifier.height(16.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            KejaSecondaryButton(text = "Cancel", onClick = onCancel, modifier = Modifier.weight(1f))
            KejaPrimaryButton(text = if (loading) "Publishing…" else "Publish", enabled = !loading, modifier = Modifier.weight(1f)) {
                val priceValue = price.toDoubleOrNull()
                if (priceValue == null || location.isBlank()) { error = "Price and location are required."; return@KejaPrimaryButton }
                loading = true
                error = null
                scope.launch {
                    try {
                        val prop = repo.createProperty(
                            PropertyCreateRequest(
                                title = "$type in $location",
                                description = desc.ifBlank { null },
                                price = priceValue,
                                property_type = type,
                                bedrooms = null,
                                bathrooms = null,
                                county = location,
                                area = location,
                                proximity_note = landmark.ifBlank { null },
                                amenities = Amenities.all.map { it.key }.filter { it in amenities },
                            )
                        )
                        selectedImages.forEachIndexed { index, uri ->
                            publishStatus = "Uploading photo ${index + 1} of ${selectedImages.size}…"
                            val file = copyUriToTempFile(context, uri)
                            if (file != null) {
                                runCatching { repo.uploadImage(prop.id, file, isMain = index == 0) }
                                file.delete()
                            }
                        }
                        onPublished()
                    } catch (e: ApiException) {
                        error = e.message
                    } finally {
                        loading = false
                    }
                }
            }
        }
    }
}
