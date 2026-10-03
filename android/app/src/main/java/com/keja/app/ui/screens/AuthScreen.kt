package com.keja.app.ui.screens

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.keja.app.R
import com.keja.app.data.AppContainer
import com.keja.app.data.ApiException
import com.keja.app.data.model.RegisterRequest
import com.keja.app.ui.components.KejaPrimaryButton
import com.keja.app.ui.components.KejaTextField
import com.keja.app.ui.theme.KejaShapes
import com.keja.app.ui.theme.LocalKejaPalette
import kotlinx.coroutines.launch

@Composable
fun AuthScreen(onAuthenticated: () -> Unit) {
    val palette = LocalKejaPalette.current
    val context = LocalContext.current
    val repo = remember { AppContainer.repository(context) }
    val scope = rememberCoroutineScope()

    var isLoginMode by remember { mutableStateOf(true) }
    var fullName by remember { mutableStateOf("") }
    var identifier by remember { mutableStateOf("") } // email or phone
    var password by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(false) }
    var info by remember { mutableStateOf<String?>(null) }
    var needsVerify by remember { mutableStateOf(false) }

    fun submit() {
        if (identifier.isBlank() || password.isBlank()) {
            error = "Enter your details to continue"
            return
        }
        if (!isLoginMode && !identifier.contains("@")) {
            error = "Please use a real email address — we'll send you a verification link."
            return
        }
        error = null
        info = null
        needsVerify = false
        loading = true
        scope.launch {
            val wasSignup = !isLoginMode
            try {
                val isEmail = identifier.contains("@")
                val emailToUse = if (isEmail) identifier else identifier.filter { it.isDigit() } + "@keja.local"
                if (!isLoginMode) {
                    repo.register(
                        RegisterRequest(
                            full_name = fullName.ifBlank { identifier },
                            username = identifier.substringBefore("@").filter { it.isLetterOrDigit() }.lowercase() + (0..999).random(),
                            email = emailToUse,
                            phone = if (isEmail) "" else identifier,
                            password = password,
                        )
                    )
                }
                repo.login(emailToUse, password)
                onAuthenticated()
            } catch (e: ApiException) {
                if ((e.message ?: "").contains("verify your email", ignoreCase = true)) {
                    // Not an error: the account exists, it just needs the email link clicked.
                    needsVerify = true
                    isLoginMode = true
                    info = if (wasSignup) "Account created! We emailed you a verification link — tap it, then log in here. (Check spam too.)" else e.message
                } else {
                    error = e.message
                }
            } catch (e: Exception) {
                error = "Couldn't connect — check your internet connection"
            } finally {
                loading = false
            }
        }
    }

    Column(
        Modifier
            .fillMaxSize()
            .background(palette.bg)
            .verticalScroll(rememberScrollState()),
    ) {
        // Gradient cover banner with the real brand mark — sets the tone
        // before any form fields, instead of a small icon + wordmark buried
        // in the body.
        Column(
            Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(bottomStart = 36.dp, bottomEnd = 36.dp))
                .background(Brush.linearGradient(listOf(palette.primary, palette.coral)))
                .padding(top = 56.dp, bottom = 32.dp, start = 28.dp, end = 28.dp),
        ) {
            Image(
                painter = painterResource(R.drawable.keja_logo_white),
                contentDescription = "Keja",
                modifier = Modifier.height(28.dp),
            )
            Spacer(Modifier.height(16.dp))
            Text(
                "Find a place\nyou'll love.",
                color = Color.White,
                fontSize = 28.sp,
                fontWeight = FontWeight.ExtraBold,
                lineHeight = 32.sp,
            )
            Spacer(Modifier.height(8.dp))
            Text(
                "Swipe through verified apartments, Airbnb stays and shops across Kenya.",
                color = Color.White.copy(alpha = 0.88f),
                fontSize = 13.sp,
                lineHeight = 18.sp,
            )
        }

        Column(Modifier.fillMaxWidth().padding(horizontal = 24.dp).offset(y = (-22).dp)) {
            // A card that overlaps the gradient slightly, so the form reads
            // as one deliberate surface rather than starting flush at the
            // banner's edge.
            com.keja.app.ui.components.KejaSurface(Modifier.fillMaxWidth(), contentPadding = PaddingValues(20.dp)) {
                Row(
                    Modifier
                        .fillMaxWidth()
                        .background(palette.bg, shape = RoundedCornerShape(999.dp))
                        .padding(4.dp),
                ) {
                    listOf("Log in" to true, "Sign up" to false).forEach { (label, mode) ->
                        val active = isLoginMode == mode
                        Box(
                            Modifier
                                .weight(1f)
                                .background(
                                    if (active) palette.primary else Color.Transparent,
                                    shape = RoundedCornerShape(999.dp),
                                )
                                .padding(vertical = 10.dp)
                                .clickableNoRipple { isLoginMode = mode },
                            contentAlignment = Alignment.Center,
                        ) {
                            Text(
                                label,
                                color = if (active) Color.White else palette.muted,
                                fontWeight = FontWeight.Bold,
                                fontSize = 14.sp,
                            )
                        }
                    }
                }
                Spacer(Modifier.height(20.dp))

                if (!isLoginMode) {
                    KejaTextField(fullName, { fullName = it }, "Full name")
                    Spacer(Modifier.height(14.dp))
                }
                KejaTextField(identifier, { identifier = it }, "Email or phone", keyboardType = KeyboardType.Email)
                Spacer(Modifier.height(14.dp))
                KejaTextField(password, { password = it }, "Password", isPassword = true)

                error?.let {
                    Spacer(Modifier.height(10.dp))
                    Text(it, color = Color(0xFFEF4444), fontSize = 13.sp)
                }
                info?.let {
                    Spacer(Modifier.height(10.dp))
                    Text(it, color = palette.primary, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
                }
                if (needsVerify && identifier.contains("@")) {
                    TextButton(onClick = {
                        scope.launch {
                            runCatching { repo.resendVerification(identifier.trim()) }
                                .onSuccess { info = "New link sent — check your inbox (and spam)." }
                                .onFailure { error = "Couldn't resend right now. Try again in a minute." }
                        }
                    }) { Text("Resend link") }
                }

                Spacer(Modifier.height(20.dp))
                KejaPrimaryButton(
                    text = if (loading) "Please wait…" else if (isLoginMode) "Log in" else "Create account",
                    enabled = !loading,
                    modifier = Modifier.fillMaxWidth(),
                    onClick = ::submit,
                )
            }

            Spacer(Modifier.height(18.dp))
            val uriHandler = androidx.compose.ui.platform.LocalUriHandler.current
            Text(
                "By continuing, you agree to Keja's",
                fontSize = 11.sp, color = palette.muted, textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                modifier = Modifier.fillMaxWidth(),
            )
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Center, verticalAlignment = Alignment.CenterVertically) {
                TextButton(onClick = { runCatching { uriHandler.openUri("https://keja-frontend.onrender.com/terms.html") } }) { Text("Terms & Conditions", fontSize = 12.sp, fontWeight = FontWeight.Bold) }
                Text("and", fontSize = 11.sp, color = palette.muted)
                TextButton(onClick = { runCatching { uriHandler.openUri("https://keja-frontend.onrender.com/privacy.html") } }) { Text("Privacy Policy", fontSize = 12.sp, fontWeight = FontWeight.Bold) }
            }
            Spacer(Modifier.height(24.dp))
        }
    }
}

// Small helper so the tab labels are clickable without triggering the
// default ripple stretching oddly across the pill-shaped tab background.
@Composable
private fun Modifier.clickableNoRipple(onClick: () -> Unit): Modifier {
    val interactionSource = remember { MutableInteractionSource() }
    return this.clickable(indication = null, interactionSource = interactionSource, onClick = onClick)
}
