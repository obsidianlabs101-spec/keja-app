package com.keja.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Home
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.composed
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.keja.app.data.AppContainer
import com.keja.app.data.ApiException
import com.keja.app.data.model.RegisterRequest
import com.keja.app.ui.components.KejaPrimaryButton
import com.keja.app.ui.components.KejaTextField
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

    fun submit() {
        if (identifier.isBlank() || password.isBlank()) {
            error = "Enter your details to continue"
            return
        }
        error = null
        loading = true
        scope.launch {
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
                error = e.message
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
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 24.dp, vertical = 48.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Filled.Home, contentDescription = null, tint = palette.primary, modifier = Modifier.size(26.dp))
            Spacer(Modifier.width(8.dp))
            Text("keja.", fontSize = 26.sp, fontWeight = FontWeight.ExtraBold, color = palette.text)
        }
        Spacer(Modifier.height(10.dp))
        Text(
            "Find a place to call home — swipe through verified rentals across Kenya.",
            color = palette.muted, fontSize = 14.sp,
        )
        Spacer(Modifier.height(28.dp))

        Row(
            Modifier
                .fillMaxWidth()
                .background(palette.card, shape = androidx.compose.foundation.shape.RoundedCornerShape(999.dp))
                .padding(4.dp),
        ) {
            listOf("Log in" to true, "Sign up" to false).forEach { (label, mode) ->
                val active = isLoginMode == mode
                Box(
                    Modifier
                        .weight(1f)
                        .background(
                            if (active) palette.primary else Color.Transparent,
                            shape = androidx.compose.foundation.shape.RoundedCornerShape(999.dp),
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
        Spacer(Modifier.height(22.dp))

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

        Spacer(Modifier.height(20.dp))
        KejaPrimaryButton(
            text = if (loading) "Please wait…" else if (isLoginMode) "Log in" else "Create account",
            enabled = !loading,
            modifier = Modifier.fillMaxWidth(),
            onClick = ::submit,
        )

        Spacer(Modifier.height(18.dp))
        Text(
            "By continuing, you agree to Keja's terms and privacy policy.",
            fontSize = 11.sp, color = palette.muted, textAlign = androidx.compose.ui.text.style.TextAlign.Center,
            modifier = Modifier.fillMaxWidth(),
        )
    }
}

// Small helper so the tab labels are clickable without triggering the
// default ripple stretching oddly across the pill-shaped tab background.
private fun Modifier.clickableNoRipple(onClick: () -> Unit): Modifier = composed {
    clickable(
        indication = null,
        interactionSource = remember { MutableInteractionSource() },
        onClick = onClick,
    )
}
