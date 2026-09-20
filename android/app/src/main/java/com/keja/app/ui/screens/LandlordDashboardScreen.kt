package com.keja.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
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
import com.keja.app.ui.components.KejaPrimaryButton
import com.keja.app.ui.components.KejaSecondaryButton
import com.keja.app.ui.components.KejaTextField
import com.keja.app.ui.components.formatKes
import com.keja.app.ui.theme.LocalKejaPalette
import kotlinx.coroutines.launch

@Composable
fun LandlordDashboardScreen(onBack: () -> Unit) {
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
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
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

        stats?.let { s ->
            Row(Modifier.fillMaxWidth().padding(horizontal = 20.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                StatTile("Listings", s.active_listings.toString(), Modifier.weight(1f))
                StatTile("Views", s.total_views.toString(), Modifier.weight(1f))
                StatTile("Interested", s.interested_count.toString(), Modifier.weight(1f))
                StatTile("Unlocks", s.contact_unlocks.toString(), Modifier.weight(1f))
            }
            Spacer(Modifier.height(16.dp))
        }

        LazyColumn(contentPadding = PaddingValues(horizontal = 20.dp, vertical = 4.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            if (listings.isEmpty()) {
                item { Text("No listings yet — tap + Add to publish your first property.", color = palette.muted) }
            }
            items(listings) { p ->
                LandlordListingRow(p, onToggleBooked = {
                    scope.launch {
                        runCatching { repo.updateProperty(p.id, PropertyUpdateRequest(is_booked = !p.is_booked)) }
                        refresh()
                    }
                })
            }
        }
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
private fun LandlordListingRow(p: Property, onToggleBooked: () -> Unit) {
    val palette = LocalKejaPalette.current
    Row(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(16.dp))
            .background(palette.card)
            .padding(12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text("${p.property_type} — ${formatKes(p.price)}", fontWeight = FontWeight.Bold, color = palette.text, fontSize = 14.sp)
            Text(p.area ?: p.county, fontSize = 12.sp, color = palette.muted)
        }
        KejaSecondaryButton(text = if (p.is_booked) "Mark available" else "Mark booked", onClick = onToggleBooked)
    }
}

@Composable
private fun BecomeLandlordForm(onDone: () -> Unit) {
    val context = LocalContext.current
    val repo = remember { AppContainer.repository(context) }
    val scope = rememberCoroutineScope()
    var govId by remember { mutableStateOf("") }
    var phone by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(false) }

    Column(Modifier.fillMaxWidth().padding(24.dp)) {
        Text("Become a landlord", fontWeight = FontWeight.Bold, fontSize = 18.sp)
        Spacer(Modifier.height(6.dp))
        Text("Verification is reviewed by our team to keep Keja trustworthy for renters.", fontSize = 12.sp)
        Spacer(Modifier.height(16.dp))
        KejaTextField(govId, { govId = it }, "Government ID number")
        Spacer(Modifier.height(12.dp))
        KejaTextField(phone, { phone = it }, "Phone for renter contact")
        error?.let { Spacer(Modifier.height(8.dp)); Text(it, color = Color(0xFFEF4444), fontSize = 12.sp) }
        Spacer(Modifier.height(16.dp))
        KejaPrimaryButton(text = if (loading) "Submitting…" else "Submit for review", enabled = !loading, modifier = Modifier.fillMaxWidth()) {
            loading = true
            scope.launch {
                try {
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

    Column(Modifier.fillMaxWidth().padding(20.dp)) {
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
        error?.let { Spacer(Modifier.height(8.dp)); Text(it, color = Color(0xFFEF4444), fontSize = 12.sp) }
        Spacer(Modifier.height(16.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            KejaSecondaryButton(text = "Cancel", onClick = onCancel, modifier = Modifier.weight(1f))
            KejaPrimaryButton(text = if (loading) "Publishing…" else "Publish", enabled = !loading, modifier = Modifier.weight(1f)) {
                val priceValue = price.toDoubleOrNull()
                if (priceValue == null || location.isBlank()) { error = "Price and location are required."; return@KejaPrimaryButton }
                loading = true
                scope.launch {
                    try {
                        repo.createProperty(
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
                            )
                        )
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
