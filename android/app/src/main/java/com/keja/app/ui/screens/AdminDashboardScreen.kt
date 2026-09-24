package com.keja.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.shape.RoundedCornerShape
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
import com.keja.app.data.model.AdminStats
import com.keja.app.ui.theme.LocalKejaPalette

@Composable
fun AdminDashboardScreen(onBack: () -> Unit) {
    val palette = LocalKejaPalette.current
    val context = LocalContext.current
    val repo = remember { AppContainer.repository(context) }

    var stats by remember { mutableStateOf<AdminStats?>(null) }
    var loading by remember { mutableStateOf(true) }

    LaunchedEffect(Unit) {
        stats = runCatching { repo.adminStats() }.getOrNull()
        loading = false
    }

    Column(Modifier.fillMaxSize().background(palette.bg).verticalScroll(rememberScrollState()).padding(20.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            Column {
                Text("KEJA ADMIN", color = palette.primary, fontWeight = FontWeight.Bold, fontSize = 11.sp)
                Text("Admin dashboard", fontSize = 22.sp, fontWeight = FontWeight.ExtraBold, color = palette.text)
            }
            TextButton(onClick = onBack) { Text("Back") }
        }
        Spacer(Modifier.height(18.dp))

        if (loading) {
            com.keja.app.ui.components.KejaLoader()
        } else if (stats == null) {
            Text("Couldn't load admin stats.", color = palette.muted)
        } else {
            val s = stats!!
            val cells = listOf(
                "Total properties" to s.total_properties.toString(),
                "Active landlords" to s.active_landlords.toString(),
                "Total users" to s.total_users.toString(),
                "Pending verifications" to s.pending_verifications.toString(),
            )
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                cells.chunked(2).forEach { row ->
                    Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        row.forEach { (label, value) ->
                            Column(
                                Modifier
                                    .weight(1f)
                                    .clip(RoundedCornerShape(14.dp))
                                    .background(palette.card)
                                    .padding(14.dp),
                            ) {
                                Text(label, fontSize = 11.sp, color = palette.muted)
                                Text(value, fontSize = 22.sp, fontWeight = FontWeight.ExtraBold, color = palette.text)
                            }
                        }
                    }
                }
            }
        }
        Spacer(Modifier.height(24.dp))
        AdminAdsSection()
        Spacer(Modifier.height(24.dp))
    }
}
