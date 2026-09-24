package com.keja.app.ui.screens

import android.content.Intent
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.border
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
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
import coil.compose.AsyncImage
import com.keja.app.data.AppContainer
import com.keja.app.data.ApiException
import com.keja.app.data.model.ContactUnlockStatus
import com.keja.app.data.model.LandlordPropertiesResponse
import com.keja.app.data.model.Property
import com.keja.app.ui.components.AmenityCard
import com.keja.app.ui.components.Amenities
import com.keja.app.ui.components.Avatar
import com.keja.app.ui.components.KejaPrimaryButton
import com.keja.app.ui.components.KejaSecondaryButton
import com.keja.app.ui.components.StatusPill
import com.keja.app.ui.components.formatKes
import com.keja.app.ui.components.resolveMediaUrl
import com.keja.app.ui.theme.KejaColors
import com.keja.app.ui.theme.LocalKejaPalette
import kotlinx.coroutines.launch

// Real till number — see frontend/app.js's MPESA_TILL constant, kept in sync.
private const val MPESA_TILL = "4396353"
private const val MPESA_NAME = "Keja Kenya"
private const val MPESA_AMOUNT = 50

@OptIn(ExperimentalFoundationApi::class)
@Composable
fun PropertyDetailScreen(
    propertyId: String,
    onBack: () -> Unit,
    onRequireLogin: () -> Unit,
    onOpenLandlord: (String) -> Unit = {},
) {
    val palette = LocalKejaPalette.current
    val context = LocalContext.current
    val repo = remember { AppContainer.repository(context) }
    val scope = rememberCoroutineScope()
    val currentUser by repo.currentUser.collectAsState()

    var property by remember { mutableStateOf<Property?>(null) }
    var loading by remember { mutableStateOf(true) }
    var contactStatus by remember { mutableStateOf<ContactUnlockStatus?>(null) }
    var contactStep by remember { mutableStateOf(0) } // 0=not shown yet, 1=choice, 2=pay form
    var claimText by remember { mutableStateOf("") }
    var claimError by remember { mutableStateOf<String?>(null) }
    var claiming by remember { mutableStateOf(false) }
    var showViewer by remember { mutableStateOf(false) }
    var landlord by remember { mutableStateOf<LandlordPropertiesResponse?>(null) }

    LaunchedEffect(propertyId) {
        loading = true
        property = runCatching { repo.getProperty(propertyId) }.getOrNull()
        loading = false
    }

    LaunchedEffect(property?.landlord_id) {
        val lid = property?.landlord_id ?: return@LaunchedEffect
        landlord = runCatching { repo.landlordProperties(lid) }.getOrNull()
    }

    fun checkContact() {
        val isLoggedIn = currentUser != null
        if (!isLoggedIn) { onRequireLogin(); return }
        scope.launch {
            contactStatus = runCatching { repo.contactStatus(propertyId) }.getOrNull()
            contactStep = 1
        }
    }

    BoxWithConstraints(Modifier.fillMaxSize().background(palette.bg)) {
        if (loading || property == null) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
            return@BoxWithConstraints
        }
        val p = property!!
        val images = if (p.images.isNotEmpty()) p.images.sortedBy { it.sort_order }.map { it.url } else listOf(p.main_image_url)
        val galleryState = rememberPagerState(pageCount = { images.size })

        // The photo takes ALL the height the details below don't need, so the
        // last thing on screen is always the Get-contact area (no dead space).
        // When the details grow (e.g. the payment form) the photo shrinks to a
        // minimum and the page scrolls.
        val density = LocalDensity.current
        var detailsH by remember { mutableStateOf(300.dp) }
        val imageH = (maxHeight - detailsH).coerceAtLeast(300.dp)

        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
            Box(Modifier.fillMaxWidth().height(imageH)) {
                HorizontalPager(state = galleryState, modifier = Modifier.fillMaxSize()) { page ->
                    AsyncImage(
                        model = resolveMediaUrl(images[page]),
                        contentDescription = p.title,
                        contentScale = ContentScale.Crop,
                        modifier = Modifier.fillMaxSize(),
                    )
                }
                Box(
                    Modifier
                        .padding(16.dp)
                        .size(38.dp)
                        .clip(CircleShape)
                        .background(Color.Black.copy(alpha = 0.45f))
                        .align(Alignment.TopStart),
                    contentAlignment = Alignment.Center,
                ) {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Filled.ArrowBack, contentDescription = "Back", tint = Color.White)
                    }
                }
                Box(
                    Modifier
                        .align(Alignment.TopEnd)
                        .padding(16.dp)
                        .clip(RoundedCornerShape(50))
                        .background(Color.Black.copy(alpha = 0.55f))
                        .clickable { showViewer = true }
                        .padding(horizontal = 12.dp, vertical = 9.dp),
                ) {
                    Text(
                        "⤢ Photos" + if (images.size > 1) " (${images.size})" else "",
                        color = Color.White, fontSize = 12.sp, fontWeight = FontWeight.Bold,
                    )
                }

                // Bottom of the photo: landlord chip + amenity icon cards
                Column(
                    Modifier
                        .align(Alignment.BottomStart)
                        .fillMaxWidth()
                        .background(Brush.verticalGradient(listOf(Color.Transparent, Color.Black.copy(alpha = 0.8f))))
                        .padding(start = 14.dp, end = 14.dp, top = 40.dp, bottom = 12.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    val info = landlord
                    val count = info?.property_count ?: 0
                    Row(
                        Modifier
                            .clip(RoundedCornerShape(50))
                            .background(Color.Black.copy(alpha = 0.45f))
                            .clickable { onOpenLandlord(p.landlord_id) }
                            .padding(end = 14.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Avatar(
                            url = info?.landlord?.profile_picture,
                            name = info?.landlord?.full_name,
                            size = 42.dp,
                            modifier = Modifier.border(2.dp, Color.White, CircleShape),
                        )
                        Spacer(Modifier.width(10.dp))
                        Column {
                            Text(info?.landlord?.full_name ?: "Landlord", color = Color.White, fontWeight = FontWeight.Bold, fontSize = 13.sp)
                            Text(
                                (if (count > 0) "$count propert${if (count == 1) "y" else "ies"} · " else "") + "View profile",
                                color = Color.White.copy(alpha = 0.75f), fontSize = 11.sp,
                            )
                        }
                    }
                    val cards = p.amenities.mapNotNull { Amenities.find(it) }
                    if (cards.isNotEmpty()) {
                        LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            items(cards) { AmenityCard(it) }
                        }
                    }
                }
            }

            Column(Modifier.fillMaxWidth().onSizeChanged { detailsH = with(density) { it.height.toDp() } }.padding(20.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(formatKes(p.price), fontSize = 26.sp, fontWeight = FontWeight.ExtraBold, color = palette.text)
                    Spacer(Modifier.width(6.dp))
                    Text("/ month", fontSize = 13.sp, color = palette.muted)
                    Spacer(Modifier.weight(1f))
                    if (p.is_booked) StatusPill("Booked", KejaColors.BookedBg, KejaColors.BookedText)
                    else StatusPill("Available", KejaColors.AvailableBg, KejaColors.AvailableText)
                }
                Spacer(Modifier.height(6.dp))
                Text("${p.area ?: p.county}${p.proximity_note?.let { " · $it" } ?: ""}", fontWeight = FontWeight.SemiBold, color = palette.text)
                p.description?.let {
                    Spacer(Modifier.height(10.dp))
                    Text(it, color = palette.muted, fontSize = 14.sp, lineHeight = 20.sp)
                }

                Spacer(Modifier.height(18.dp))

                if (p.is_booked) {
                    KejaPrimaryButton(text = "This property is booked", enabled = false, modifier = Modifier.fillMaxWidth()) {}
                } else when (contactStep) {
                    0 -> KejaPrimaryButton(text = "Get contact", modifier = Modifier.fillMaxWidth(), onClick = { checkContact() })
                    1 -> {
                        val status = contactStatus
                        when {
                            status == null -> CircularProgressIndicator()
                            status.status == "unlocked" -> UnlockedContactCard(status)
                            status.status == "awaiting_admin_match" -> {
                                Text("We're verifying your M-Pesa payment — check back shortly.", color = palette.muted, fontSize = 13.sp)
                                Spacer(Modifier.height(10.dp))
                                OutlinedButton(onClick = { contactStep = 2 }, modifier = Modifier.fillMaxWidth()) { Text("Resend payment code") }
                            }
                            status.free_credits_available > 0 -> {
                                KejaPrimaryButton(text = "Get contact — Free credit available 🎁", modifier = Modifier.fillMaxWidth()) {
                                    scope.launch {
                                        runCatching { repo.useFreeCredit(propertyId) }.onSuccess { contactStatus = it }
                                    }
                                }
                            }
                            else -> {
                                val canEarnFree = currentUser?.referral_bonus_granted == false
                                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                                    if (canEarnFree) {
                                        OutlinedButton(
                                            onClick = {
                                                val code = currentUser?.referral_code
                                                if (code != null) {
                                                    val link = "https://keja-frontend.onrender.com/index.html?ref=$code"
                                                    val sendIntent = Intent(Intent.ACTION_SEND).apply {
                                                        type = "text/plain"
                                                        putExtra(Intent.EXTRA_TEXT, "Check out Keja — find your next home in Kenya! $link")
                                                    }
                                                    context.startActivity(Intent.createChooser(sendIntent, null))
                                                }
                                            },
                                            modifier = Modifier.weight(1f),
                                        ) { Text("Share & unlock free", fontSize = 12.sp) }
                                    }
                                    KejaPrimaryButton(text = "Pay KES $MPESA_AMOUNT", modifier = Modifier.weight(1f), onClick = { contactStep = 2 })
                                }
                            }
                        }
                    }
                    2 -> MpesaPayCard(
                        claimText = claimText,
                        onClaimChange = { claimText = it; claimError = null },
                        claimError = claimError,
                        claiming = claiming,
                        onBack = { contactStep = 1 },
                        onSubmit = {
                            if (claimText.isBlank()) { claimError = "Paste your M-Pesa code or message first."; return@MpesaPayCard }
                            claiming = true
                            scope.launch {
                                try {
                                    contactStatus = repo.submitClaim(propertyId, claimText)
                                    contactStep = 1
                                } catch (e: ApiException) {
                                    claimError = e.message
                                } finally {
                                    claiming = false
                                }
                            }
                        },
                    )
                }
            }
        }

        if (showViewer) {
            PhotoViewerOverlay(
                images = images,
                startPage = galleryState.currentPage,
                isBooked = p.is_booked,
                onBack = { showViewer = false },
                onContact = {
                    showViewer = false
                    if (contactStep == 0) checkContact()
                },
            )
        }
    }
}

/** Full-screen swipeable photos. Back (left) returns to the property screen;
 * Get contact (right) closes the viewer and starts the normal contact flow. */
@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun PhotoViewerOverlay(
    images: List<String?>,
    startPage: Int,
    isBooked: Boolean,
    onBack: () -> Unit,
    onContact: () -> Unit,
) {
    BackHandler(onBack = onBack)
    val state = rememberPagerState(initialPage = startPage.coerceIn(0, (images.size - 1).coerceAtLeast(0)), pageCount = { images.size })
    Box(Modifier.fillMaxSize().background(Color.Black).clickable(enabled = false) {}) {
        HorizontalPager(state = state, modifier = Modifier.fillMaxSize()) { page ->
            AsyncImage(
                model = resolveMediaUrl(images[page]),
                contentDescription = null,
                contentScale = ContentScale.Fit,
                modifier = Modifier.fillMaxSize(),
            )
        }
        Text(
            "${state.currentPage + 1} / ${images.size}",
            color = Color.White, fontSize = 12.sp, fontWeight = FontWeight.Bold,
            modifier = Modifier
                .align(Alignment.TopCenter)
                .statusBarsPadding()
                .padding(top = 12.dp)
                .clip(RoundedCornerShape(50))
                .background(Color.Black.copy(alpha = 0.55f))
                .padding(horizontal = 12.dp, vertical = 5.dp),
        )
        Row(
            Modifier
                .align(Alignment.BottomCenter)
                .fillMaxWidth()
                .navigationBarsPadding()
                .padding(16.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            KejaSecondaryButton(text = "← Back", onClick = onBack)
            KejaPrimaryButton(text = if (isBooked) "Booked" else "Get contact", enabled = !isBooked, onClick = onContact)
        }
    }
}

@Composable
private fun MpesaPayCard(
    claimText: String,
    onClaimChange: (String) -> Unit,
    claimError: String?,
    claiming: Boolean,
    onBack: () -> Unit,
    onSubmit: () -> Unit,
) {
    val palette = LocalKejaPalette.current
    val clipboard = LocalClipboardManager.current
    var copied by remember { mutableStateOf(false) }

    Column {
        TextButton(onClick = onBack) { Text("← Back") }
        Column(
            Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(18.dp))
                .background(palette.card)
                .padding(16.dp),
        ) {
            Text("Pay KES $MPESA_AMOUNT via M-Pesa", fontSize = 17.sp, fontWeight = FontWeight.ExtraBold, color = palette.text)
            Text("One-time payment to unlock this landlord's contact.", fontSize = 12.sp, color = palette.muted)
            Spacer(Modifier.height(14.dp))

            PayStep(1, "Open M-Pesa", "Go to Lipa na M-Pesa → Buy Goods and Services.")
            PayStep(2, "Enter the Till number", extra = {
                Row(
                    Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(12.dp))
                        .background(Color(0xFFFEF3C7))
                        .padding(horizontal = 12.dp, vertical = 10.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(Modifier.weight(1f)) {
                        Text(MPESA_TILL, fontSize = 22.sp, fontWeight = FontWeight.ExtraBold, color = Color(0xFF1F1B0E), letterSpacing = 2.sp)
                        Text("Business name: $MPESA_NAME", fontSize = 11.sp, color = Color(0xFF5B4E12))
                    }
                    TextButton(onClick = { clipboard.setText(AnnotatedString(MPESA_TILL)); copied = true }) {
                        Icon(Icons.Filled.ContentCopy, contentDescription = null, modifier = Modifier.size(16.dp))
                        Spacer(Modifier.width(4.dp))
                        Text(if (copied) "Copied ✓" else "Copy")
                    }
                }
            })
            PayStep(3, "Enter the amount", "KES $MPESA_AMOUNT — the exact amount, so we can match it.")
            PayStep(4, "Confirm and pay", "Check the name reads $MPESA_NAME, then enter your M-Pesa PIN.")
            PayStep(5, "Paste your confirmation", "Copy the M-Pesa SMS (it starts with a code like QGH7XXXXX) and paste it below.", isLast = true)

            Spacer(Modifier.height(12.dp))
            OutlinedTextField(
                value = claimText,
                onValueChange = onClaimChange,
                placeholder = { Text("e.g. QGH7XXXXX Confirmed. Ksh50.00 paid to Keja Kenya…") },
                modifier = Modifier.fillMaxWidth().height(110.dp),
            )
            claimError?.let {
                Spacer(Modifier.height(4.dp))
                Text(it, color = Color(0xFFEF4444), fontSize = 12.sp)
            }
            Spacer(Modifier.height(6.dp))
            Text(
                "We match your payment to your account, usually within a few minutes. Keep the SMS until your contact unlocks.",
                fontSize = 11.sp, color = palette.muted,
            )
            Spacer(Modifier.height(12.dp))
            KejaPrimaryButton(
                text = if (claiming) "Verifying…" else "I've paid — verify my code",
                enabled = !claiming,
                modifier = Modifier.fillMaxWidth(),
                onClick = onSubmit,
            )
        }
    }
}

@Composable
private fun PayStep(number: Int, title: String, detail: String? = null, isLast: Boolean = false, extra: (@Composable () -> Unit)? = null) {
    val palette = LocalKejaPalette.current
    Row(Modifier.fillMaxWidth().padding(bottom = if (isLast) 0.dp else 12.dp)) {
        Box(
            Modifier.size(24.dp).clip(CircleShape).background(palette.primary),
            contentAlignment = Alignment.Center,
        ) { Text("$number", color = Color.White, fontSize = 12.sp, fontWeight = FontWeight.Bold) }
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Text(title, fontWeight = FontWeight.Bold, fontSize = 14.sp, color = palette.text)
            if (detail != null) Text(detail, fontSize = 12.sp, color = palette.muted, lineHeight = 17.sp)
            if (extra != null) { Spacer(Modifier.height(6.dp)); extra() }
        }
    }
}


@Composable
private fun UnlockedContactCard(status: ContactUnlockStatus) {
    val context = LocalContext.current
    Column {
        Text("Contact unlocked", fontWeight = FontWeight.Bold)
        Text(status.phone ?: "", color = Color(0xFF6C4DFF), fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(10.dp))
        KejaPrimaryButton(text = "Message on WhatsApp", modifier = Modifier.fillMaxWidth()) {
            val digits = (status.whatsapp ?: "").filter { it.isDigit() }
            val formatted = if (digits.startsWith("0")) "254" + digits.drop(1) else digits
            val intent = Intent(Intent.ACTION_VIEW, android.net.Uri.parse("https://wa.me/$formatted"))
            context.startActivity(intent)
        }
    }
}
