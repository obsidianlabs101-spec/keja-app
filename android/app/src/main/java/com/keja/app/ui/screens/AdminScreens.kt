package com.keja.app.ui.screens

import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import coil.compose.AsyncImage
import com.keja.app.data.AppContainer
import com.keja.app.data.model.*
import com.keja.app.ui.components.*
import com.keja.app.ui.theme.LocalKejaPalette
import kotlinx.coroutines.launch

object AdminRoutes {
    const val HOME = "admin-home"
    const val NEW = "admin-new"
    const val LANDLORDS = "admin-landlords"
    const val PAYMENTS = "admin-payments"
    const val LISTINGS = "admin-listings"
    const val ADS = "admin-ads"
    val all = listOf(HOME, NEW, LANDLORDS, PAYMENTS, LISTINGS, ADS)
}

private val Red = Color(0xFFEF4444)

private fun toast(context: android.content.Context, msg: String) = Toast.makeText(context, msg, Toast.LENGTH_SHORT).show()

// ---------------------------------------------------------------- Overview

@Composable
fun AdminOverviewScreen(onOpen: (String) -> Unit) {
    val palette = LocalKejaPalette.current
    val context = LocalContext.current
    val repo = remember { AppContainer.repository(context) }
    var overview by remember { mutableStateOf<AdminOverview?>(null) }
    LaunchedEffect(Unit) { overview = runCatching { repo.adminOverview() }.getOrNull() }

    AdminPage("KEJA ADMIN", "Overview", "What needs your attention right now.") {
        val o = overview
        if (o == null) {
            KejaLoader(size = 48.dp)
        } else {
            val tiles = listOf(
                Triple("New listings", o.unreviewed_properties, AdminRoutes.NEW),
                Triple("Landlord applications", o.pending_landlords, AdminRoutes.LANDLORDS),
                Triple("Payment messages", o.pending_payments, AdminRoutes.PAYMENTS),
                Triple("All listings", o.total_properties, AdminRoutes.LISTINGS),
            )
            tiles.chunked(2).forEach { row ->
                Row(Modifier.fillMaxWidth().padding(bottom = 12.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    row.forEach { (label, count, route) ->
                        Column(
                            Modifier
                                .weight(1f)
                                .clip(RoundedCornerShape(16.dp))
                                .background(palette.card)
                                .clickable { onOpen(route) }
                                .padding(16.dp),
                        ) {
                            Text(label, color = palette.muted, fontSize = 12.sp)
                            Text("$count", fontSize = 26.sp, fontWeight = FontWeight.ExtraBold, color = palette.text)
                        }
                    }
                }
            }
            Text("Total users: ${o.total_users}", color = palette.muted, fontSize = 12.sp)
            Spacer(Modifier.height(12.dp))
            OutlinedButton(onClick = { onOpen(AdminRoutes.ADS) }, modifier = Modifier.fillMaxWidth()) { Text("Manage ads") }
        }
    }
}

// ---------------------------------------------------------------- Property card

@Composable
private fun AdminPropertyCard(p: AdminPropertyDto, actions: @Composable RowScope.() -> Unit) {
    val palette = LocalKejaPalette.current
    CardShell {
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            AsyncImage(
                model = resolveMediaUrl(p.main_image_url),
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier.size(84.dp).clip(RoundedCornerShape(12.dp)),
            )
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Row(horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
                    Text("${p.property_type ?: ""} · KES ${p.price.toLong()}", fontWeight = FontWeight.Bold, color = palette.text, fontSize = 14.sp, modifier = Modifier.weight(1f))
                    when {
                        p.review_status == "rejected" -> Pill("Rejected", Color(0xFFFEE2E2), Color(0xFFB91C1C))
                        p.is_booked -> Pill("Booked", Color(0xFFFEF3C7), Color(0xFFB45309))
                        p.review_status == "approved" -> Pill("Approved", Color(0xFFDCFCE7), Color(0xFF15803D))
                        else -> Pill("New", palette.border, palette.muted)
                    }
                }
                Text("${p.area ?: p.county ?: ""} · ${p.image_count} photos · ${relativeTime(p.created_at)}", color = palette.muted, fontSize = 11.sp)
                Text("Landlord: ${p.landlord_name ?: "—"}${p.landlord_phone?.let { " · $it" } ?: ""}", color = palette.muted, fontSize = 11.sp)
                if (p.review_status == "rejected" && !p.review_note.isNullOrBlank()) {
                    Text("Reason: ${p.review_note}", color = Red, fontSize = 11.sp)
                }
            }
        }
        Spacer(Modifier.height(6.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), content = actions)
    }
}

// ---------------------------------------------------------------- New listings

@Composable
fun AdminNewListingsScreen() {
    val context = LocalContext.current
    val repo = remember { AppContainer.repository(context) }
    val scope = rememberCoroutineScope()
    var items by remember { mutableStateOf<List<AdminPropertyDto>?>(null) }
    var rejecting by remember { mutableStateOf<AdminPropertyDto?>(null) }

    fun load() { scope.launch { items = runCatching { repo.adminProperties("unreviewed") }.getOrDefault(emptyList()) } }
    LaunchedEffect(Unit) { load() }

    rejecting?.let { p ->
        ReasonDialog("Reject this listing", "Reason for the landlord (e.g. photos unclear)", true, "Reject", { rejecting = null }) { note ->
            rejecting = null
            scope.launch {
                runCatching { repo.adminReviewProperty(p.id, "reject", note) }
                    .onSuccess { toast(context, "Rejected — landlord notified"); load() }
                    .onFailure { toast(context, it.message ?: "Couldn't reject") }
            }
        }
    }

    AdminPage("NEW LISTINGS", "New properties", "Newly posted listings you haven't reviewed. They stay live until you reject them.") {
        val list = items
        when {
            list == null -> KejaLoader(size = 48.dp)
            list.isEmpty() -> Text("Nothing new to review 🎉", color = LocalKejaPalette.current.muted)
            else -> list.forEach { p ->
                AdminPropertyCard(p) {
                    Button(onClick = {
                        scope.launch {
                            runCatching { repo.adminReviewProperty(p.id, "approve", null) }
                                .onSuccess { toast(context, "Approved"); load() }
                                .onFailure { toast(context, it.message ?: "Couldn't approve") }
                        }
                    }) { Text("Approve", fontSize = 12.sp) }
                    OutlinedButton(onClick = { rejecting = p }) { Text("Reject", fontSize = 12.sp, color = Red) }
                }
            }
        }
    }
}

// ---------------------------------------------------------------- Landlord applications

@Composable
fun AdminLandlordsScreen() {
    val palette = LocalKejaPalette.current
    val context = LocalContext.current
    val repo = remember { AppContainer.repository(context) }
    val scope = rememberCoroutineScope()
    var items by remember { mutableStateOf<List<PendingLandlordDto>?>(null) }
    var rejecting by remember { mutableStateOf<PendingLandlordDto?>(null) }
    var idBytes by remember { mutableStateOf<ByteArray?>(null) }
    var idLoading by remember { mutableStateOf(false) }

    fun load() { scope.launch { items = runCatching { repo.adminPendingLandlords() }.getOrDefault(emptyList()) } }
    LaunchedEffect(Unit) { load() }

    fun decide(u: PendingLandlordDto, approve: Boolean, note: String?) {
        scope.launch {
            runCatching { repo.adminVerifyLandlord(u.id, approve, note) }
                .onSuccess { toast(context, if (approve) "Landlord approved" else "Application rejected"); load() }
                .onFailure { toast(context, it.message ?: "Couldn't update") }
        }
    }

    rejecting?.let { u ->
        ReasonDialog("Reject application", "Reason (shown to the applicant)", true, "Reject", { rejecting = null }) { note ->
            rejecting = null; decide(u, false, note)
        }
    }
    idBytes?.let { bytes ->
        Dialog(onDismissRequest = { idBytes = null }) {
            Column(Modifier.clip(RoundedCornerShape(16.dp)).background(palette.card).padding(12.dp)) {
                AsyncImage(model = bytes, contentDescription = "ID photo", contentScale = ContentScale.Fit, modifier = Modifier.fillMaxWidth().heightIn(max = 480.dp))
                TextButton(onClick = { idBytes = null }, modifier = Modifier.align(Alignment.End)) { Text("Close") }
            }
        }
    }

    AdminPage("LANDLORDS", "Landlord applications", "Check the ID photo, then approve or reject.") {
        val list = items
        when {
            list == null -> KejaLoader(size = 48.dp)
            list.isEmpty() -> Text("No applications waiting", color = palette.muted)
            else -> list.forEach { u ->
                CardShell {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text(u.full_name ?: u.email ?: "Applicant", fontWeight = FontWeight.Bold, color = palette.text, modifier = Modifier.weight(1f))
                        Text(relativeTime(u.verification_requested_at), color = palette.muted, fontSize = 11.sp)
                    }
                    Text("${u.email ?: ""}${u.phone?.let { " · $it" } ?: ""}", color = palette.muted, fontSize = 12.sp)
                    Text("ID number: ${u.government_id ?: "—"}", color = palette.muted, fontSize = 12.sp)
                    Spacer(Modifier.height(6.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        if (u.government_id_image_url != null) {
                            OutlinedButton(enabled = !idLoading, onClick = {
                                idLoading = true
                                scope.launch {
                                    runCatching { repo.adminLandlordIdImage(u.id) }
                                        .onSuccess { idBytes = android.util.Base64.decode(it.data_base64, android.util.Base64.DEFAULT) }
                                        .onFailure { toast(context, it.message ?: "No ID photo on file") }
                                    idLoading = false
                                }
                            }) { Text("View ID", fontSize = 12.sp) }
                        } else {
                            Pill("No ID photo", Color(0xFFFEE2E2), Color(0xFFB91C1C))
                        }
                        Button(onClick = { decide(u, true, null) }) { Text("Approve", fontSize = 12.sp) }
                        OutlinedButton(onClick = { rejecting = u }) { Text("Reject", fontSize = 12.sp, color = Red) }
                    }
                }
            }
        }
    }
}

// ---------------------------------------------------------------- Payment messages

@Composable
fun AdminPaymentsScreen() {
    val palette = LocalKejaPalette.current
    val context = LocalContext.current
    val repo = remember { AppContainer.repository(context) }
    val scope = rememberCoroutineScope()
    var items by remember { mutableStateOf<List<PendingPaymentDto>?>(null) }
    var rejecting by remember { mutableStateOf<PendingPaymentDto?>(null) }

    fun load() { scope.launch { items = runCatching { repo.adminPendingPayments() }.getOrDefault(emptyList()) } }
    LaunchedEffect(Unit) { load() }

    rejecting?.let { r ->
        ReasonDialog("Reject payment message", "Reason for the renter (optional)", false, "Reject", { rejecting = null }) { note ->
            rejecting = null
            scope.launch {
                runCatching { repo.adminRejectPayment(r.id, note.ifBlank { null }) }
                    .onSuccess { toast(context, "Rejected — user notified"); load() }
                    .onFailure { toast(context, it.message ?: "Couldn't reject") }
            }
        }
    }

    AdminPage("PAYMENTS", "Payment messages", "Renters paste their M-Pesa message here. Check it against your till, then tap Show number to send the landlord's number to their Alerts.") {
        val list = items
        when {
            list == null -> KejaLoader(size = 48.dp)
            list.isEmpty() -> Text("No payment messages waiting", color = palette.muted)
            else -> list.forEach { r ->
                CardShell {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text(r.buyer_name ?: "Renter", fontWeight = FontWeight.Bold, color = palette.text, modifier = Modifier.weight(1f))
                        Text(relativeTime(r.buyer_claimed_at), color = palette.muted, fontSize = 11.sp)
                    }
                    Text("${r.buyer_phone?.let { "$it · " } ?: ""}for ${r.property_title ?: "a property"} · expected KES ${r.amount.toLong()}", color = palette.muted, fontSize = 12.sp)
                    Text(
                        r.buyer_claimed_raw_message ?: r.buyer_claimed_code ?: "(empty)",
                        color = palette.text,
                        fontSize = 13.sp,
                        modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp).clip(RoundedCornerShape(10.dp)).background(palette.bg).padding(10.dp),
                    )
                    Text("Will send: ${r.landlord_name ?: "landlord"} ${r.landlord_phone?.let { "· $it" } ?: "(no phone on file!)"}", color = palette.muted, fontSize = 12.sp)
                    Spacer(Modifier.height(6.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(onClick = {
                            scope.launch {
                                runCatching { repo.adminShowContact(r.id) }
                                    .onSuccess { toast(context, "Number sent to the user's Alerts"); load() }
                                    .onFailure { toast(context, it.message ?: "Couldn't send") }
                            }
                        }) { Text("Show number", fontSize = 12.sp) }
                        OutlinedButton(onClick = { rejecting = r }) { Text("Reject", fontSize = 12.sp, color = Red) }
                    }
                }
            }
        }
    }
}

// ---------------------------------------------------------------- All listings

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AdminListingsScreen() {
    val palette = LocalKejaPalette.current
    val context = LocalContext.current
    val repo = remember { AppContainer.repository(context) }
    val scope = rememberCoroutineScope()
    var all by remember { mutableStateOf<List<AdminPropertyDto>?>(null) }
    var filter by remember { mutableStateOf("all") }
    var rejecting by remember { mutableStateOf<AdminPropertyDto?>(null) }
    var booking by remember { mutableStateOf<AdminPropertyDto?>(null) }

    fun load() { scope.launch { all = runCatching { repo.adminProperties("all") }.getOrDefault(emptyList()) } }
    LaunchedEffect(Unit) { load() }

    rejecting?.let { p ->
        ReasonDialog("Reject this listing", "Reason for the landlord", true, "Reject", { rejecting = null }) { note ->
            rejecting = null
            scope.launch {
                runCatching { repo.adminReviewProperty(p.id, "reject", note) }
                    .onSuccess { toast(context, "Rejected — landlord notified"); load() }
                    .onFailure { toast(context, it.message ?: "Couldn't reject") }
            }
        }
    }
    booking?.let { p ->
        ConfirmDialog(
            title = if (p.is_booked) "Reopen listing?" else "Mark as booked?",
            text = if (p.is_booked) "It will show to renters again." else "It will disappear from renters' feeds and the landlord will be told.",
            confirmLabel = if (p.is_booked) "Reopen" else "Mark booked",
            onDismiss = { booking = null },
        ) {
            booking = null
            scope.launch {
                runCatching { repo.adminForceBooked(p.id, !p.is_booked) }
                    .onSuccess { toast(context, "Updated"); load() }
                    .onFailure { toast(context, it.message ?: "Couldn't update") }
            }
        }
    }

    AdminPage("LISTINGS", "All properties", "Reject a listing, or mark it as booked when you know it's taken.") {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(bottom = 12.dp)) {
            listOf("all" to "All", "live" to "Live", "booked" to "Booked", "rejected" to "Rejected").forEach { (key, label) ->
                FilterChip(selected = filter == key, onClick = { filter = key }, label = { Text(label, fontSize = 12.sp) })
            }
        }
        val list = all
        if (list == null) {
            KejaLoader(size = 48.dp)
        } else {
            val shown = list.filter {
                when (filter) {
                    "live" -> it.is_available
                    "booked" -> it.is_booked
                    "rejected" -> it.review_status == "rejected"
                    else -> true
                }
            }
            if (shown.isEmpty()) Text("Nothing here", color = palette.muted)
            shown.forEach { p ->
                AdminPropertyCard(p) {
                    OutlinedButton(onClick = { booking = p }) { Text(if (p.is_booked) "Reopen" else "Mark booked", fontSize = 12.sp) }
                    if (p.review_status == "rejected") {
                        Button(onClick = {
                            scope.launch {
                                runCatching { repo.adminReviewProperty(p.id, "approve", null) }
                                    .onSuccess { toast(context, "Approved"); load() }
                                    .onFailure { toast(context, it.message ?: "Couldn't approve") }
                            }
                        }) { Text("Approve", fontSize = 12.sp) }
                    } else {
                        OutlinedButton(onClick = { rejecting = p }) { Text("Reject", fontSize = 12.sp, color = Red) }
                    }
                }
            }
        }
    }
}

// ---------------------------------------------------------------- Ads

@Composable
fun AdminAdsScreen() {
    AdminPage("ADS", "Ad placement", "The banners shown on Home and on the Interested page.") {
        AdminAdsSection()
    }
}
