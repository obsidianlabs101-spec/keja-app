package com.keja.app.ui.screens

import android.content.Intent
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
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
import com.keja.app.data.model.Property
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
fun PropertyDetailScreen(propertyId: String, onBack: () -> Unit, onRequireLogin: () -> Unit) {
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

    LaunchedEffect(propertyId) {
        loading = true
        property = runCatching { repo.getProperty(propertyId) }.getOrNull()
        loading = false
    }

    fun checkContact() {
        val isLoggedIn = currentUser != null
        if (!isLoggedIn) { onRequireLogin(); return }
        scope.launch {
            contactStatus = runCatching { repo.contactStatus(propertyId) }.getOrNull()
            contactStep = 1
        }
    }

    Box(Modifier.fillMaxSize().background(palette.bg)) {
        if (loading || property == null) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
            return@Box
        }
        val p = property!!
        val images = if (p.images.isNotEmpty()) p.images.sortedBy { it.sort_order }.map { it.url } else listOf(p.main_image_url)
        val galleryState = rememberPagerState(pageCount = { images.size })

        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(bottom = 24.dp)) {
            Box {
                HorizontalPager(state = galleryState, modifier = Modifier.fillMaxWidth().height(320.dp)) { page ->
                    AsyncImage(
                        model = resolveMediaUrl(images[page]),
                        contentDescription = p.title,
                        contentScale = ContentScale.Crop,
                        modifier = Modifier.fillMaxSize(),
                    )
                }
                Box(
                    Modifier
                        .align(Alignment.BottomEnd)
                        .padding(12.dp)
                        .clip(RoundedCornerShape(50))
                        .background(Color.Black.copy(alpha = 0.65f))
                        .clickable { showViewer = true }
                        .padding(horizontal = 12.dp, vertical = 7.dp),
                ) {
                    Text(
                        "⤢ Photos" + if (images.size > 1) " (${images.size})" else "",
                        color = Color.White, fontSize = 12.sp, fontWeight = FontWeight.Bold,
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
            }

            Column(Modifier.padding(20.dp)) {
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
                    2 -> {
                        Column {
                            TextButton(onClick = { contactStep = 1 }) { Text("← Back") }
                            Box(Modifier.fillMaxWidth().background(Color(0xFFFEF3C7), RoundedCornerShape(14.dp)).padding(14.dp)) {
                                Column {
                                    Text("Go to M-Pesa → Lipa na M-Pesa → Buy Goods and Services", fontSize = 12.sp)
                                    Text("Till Number: $MPESA_TILL ($MPESA_NAME)", fontSize = 12.sp, fontWeight = FontWeight.Bold)
                                    Text("Amount: KES $MPESA_AMOUNT", fontSize = 12.sp, fontWeight = FontWeight.Bold)
                                }
                            }
                            Spacer(Modifier.height(12.dp))
                            OutlinedTextField(
                                value = claimText,
                                onValueChange = { claimText = it },
                                placeholder = { Text("e.g. QGH7XXXXX Confirmed. Ksh50.00 sent...") },
                                modifier = Modifier.fillMaxWidth().height(100.dp),
                            )
                            claimError?.let { Text(it, color = Color(0xFFEF4444), fontSize = 12.sp) }
                            Spacer(Modifier.height(10.dp))
                            KejaPrimaryButton(
                                text = if (claiming) "Verifying…" else "I've paid — verify my code",
                                enabled = !claiming,
                                modifier = Modifier.fillMaxWidth(),
                            ) {
                                if (claimText.isBlank()) { claimError = "Paste your M-Pesa code or message first."; return@KejaPrimaryButton }
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
                            }
                        }
                    }
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
