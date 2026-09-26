package com.keja.app.ui.screens

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.keja.app.data.AppContainer
import com.keja.app.data.model.NotificationDto
import com.keja.app.ui.components.KejaLoader
import com.keja.app.ui.components.relativeTime
import com.keja.app.ui.theme.LocalKejaPalette
import androidx.compose.ui.graphics.Color
import kotlinx.coroutines.launch

@Composable
fun AlertsScreen(isLoggedIn: Boolean, onRequireLogin: () -> Unit, onOpenProperty: (String) -> Unit, onRequestNotificationPermission: () -> Unit = {}) {
    val palette = LocalKejaPalette.current
    val context = LocalContext.current
    val repo = remember { AppContainer.repository(context) }
    val scope = rememberCoroutineScope()
    var items by remember { mutableStateOf<List<NotificationDto>?>(null) }

    LaunchedEffect(isLoggedIn) {
        if (!isLoggedIn) return@LaunchedEffect
        onRequestNotificationPermission()
        items = runCatching { repo.notifications() }.getOrDefault(emptyList())
        if (items?.any { !it.read } == true) runCatching { repo.readAllNotifications() }
    }

    if (!isLoggedIn) {
        Box(Modifier.fillMaxSize().background(palette.bg), contentAlignment = Alignment.Center) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text("🔔", fontSize = 36.sp)
                Spacer(Modifier.height(10.dp))
                Text("Log in to see your alerts", fontWeight = FontWeight.Bold, color = palette.text)
                Spacer(Modifier.height(14.dp))
                Button(onClick = onRequireLogin) { Text("Log in") }
            }
        }
        return
    }

    Column(Modifier.fillMaxSize().background(palette.bg)) {
        Column(Modifier.padding(20.dp)) {
            Text("MESSAGES FROM KEJA", color = palette.primary, fontWeight = FontWeight.Bold, fontSize = 11.sp)
            Text("Alerts", fontSize = 24.sp, fontWeight = FontWeight.ExtraBold, color = palette.text)
            Text("Landlord numbers and updates about the properties you asked about.", color = palette.muted, fontSize = 13.sp)
        }
        val list = items
        Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(horizontal = 20.dp)) {
            when {
                list == null -> Box(Modifier.fillMaxWidth().padding(top = 40.dp), contentAlignment = Alignment.Center) { KejaLoader() }
                list.isEmpty() -> Text("No alerts yet. When a landlord's number is ready, it shows up here.", color = palette.muted, modifier = Modifier.padding(top = 40.dp))
                else -> list.forEach { n ->
                    val phone = n.dataString("phone")
                    val propertyId = n.dataString("property_id")
                    Column(
                        Modifier
                            .fillMaxWidth()
                            .padding(bottom = 10.dp)
                            .clip(RoundedCornerShape(14.dp))
                            .background(palette.card)
                            .border(if (n.read) 0.dp else 1.5.dp, if (n.read) androidx.compose.ui.graphics.Color.Transparent else palette.primary, RoundedCornerShape(14.dp))
                            .padding(14.dp),
                    ) {
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Text(n.title, fontWeight = FontWeight.Bold, color = palette.text, fontSize = 14.sp, modifier = Modifier.weight(1f))
                            Text(relativeTime(n.created_at), color = palette.muted, fontSize = 11.sp)
                        }
                        n.body?.let { Text(it, color = palette.text, fontSize = 13.sp, modifier = Modifier.padding(top = 4.dp)) }
                        if (phone != null || propertyId != null) {
                            Spacer(Modifier.height(8.dp))
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                if (phone != null) {
                                    Button(onClick = { context.startActivity(Intent(Intent.ACTION_DIAL, Uri.parse("tel:$phone"))) }) { Text("Call", fontSize = 12.sp) }
                                    val wa = phone.filter { it.isDigit() }.let { if (it.startsWith("0")) "254" + it.substring(1) else it }
                                    OutlinedButton(onClick = {
                                        runCatching { context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("https://wa.me/$wa"))) }
                                    }) { Text("WhatsApp", fontSize = 12.sp) }
                                }
                                if (propertyId != null) {
                                    OutlinedButton(onClick = { onOpenProperty(propertyId) }) { Text("View property", fontSize = 12.sp) }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
