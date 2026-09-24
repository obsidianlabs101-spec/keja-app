package com.keja.app.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.border
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.keja.app.ui.theme.LocalKejaPalette

/** One thing a landlord can tick on a listing. `key` is the value stored by
 * the backend (see ALLOWED_AMENITIES in backend/app/schemas/property.py) —
 * keep the two lists in sync. */
data class AmenityItem(val key: String, val label: String, val icon: ImageVector)

object Amenities {
    val all: List<AmenityItem> = listOf(
        AmenityItem("bathroom", "Own bathroom", Icons.Filled.Bathtub),
        AmenityItem("balcony", "Balcony", Icons.Filled.Balcony),
        AmenityItem("parking", "Parking", Icons.Filled.LocalParking),
        AmenityItem("wifi", "WiFi", Icons.Filled.Wifi),
        AmenityItem("water", "24/7 water", Icons.Filled.WaterDrop),
        AmenityItem("security", "Security", Icons.Filled.Security),
        AmenityItem("cctv", "CCTV", Icons.Filled.Videocam),
        AmenityItem("meter", "Own KPLC meter", Icons.Filled.Bolt),
        AmenityItem("gated", "Gated compound", Icons.Filled.Fence),
        AmenityItem("furnished", "Furnished", Icons.Filled.Chair),
        AmenityItem("pets", "Pets allowed", Icons.Filled.Pets),
        AmenityItem("lift", "Lift", Icons.Filled.Elevator),
        AmenityItem("generator", "Backup power", Icons.Filled.BatteryChargingFull),
        AmenityItem("kitchen", "Fitted kitchen", Icons.Filled.Kitchen),
        AmenityItem("laundry", "Laundry area", Icons.Filled.LocalLaundryService),
        AmenityItem("garden", "Garden", Icons.Filled.Yard),
    )

    fun find(key: String): AmenityItem? = all.firstOrNull { it.key == key }
}

/** Small icon card shown over the property photo. */
@Composable
fun AmenityCard(item: AmenityItem) {
    Column(
        Modifier
            .clip(RoundedCornerShape(14.dp))
            .background(Color.Black.copy(alpha = 0.5f))
            .border(1.dp, Color.White.copy(alpha = 0.22f), RoundedCornerShape(14.dp))
            .padding(horizontal = 12.dp, vertical = 8.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Icon(item.icon, contentDescription = null, tint = Color.White, modifier = Modifier.size(22.dp))
        Text(item.label, color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.SemiBold, maxLines = 1)
    }
}

/** Tick-list the landlord uses to choose what a property has. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun AmenityPicker(selected: Set<String>, onToggle: (String) -> Unit) {
    val palette = LocalKejaPalette.current
    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Amenities.all.forEach { item ->
            val on = item.key in selected
            androidx.compose.foundation.layout.Row(
                Modifier
                    .clip(RoundedCornerShape(50))
                    .background(if (on) palette.primary else palette.card)
                    .border(1.dp, if (on) palette.primary else palette.muted.copy(alpha = 0.35f), RoundedCornerShape(50))
                    .clickable { onToggle(item.key) }
                    .padding(horizontal = 12.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                Icon(item.icon, contentDescription = null, tint = if (on) Color.White else palette.text, modifier = Modifier.size(16.dp))
                Text(item.label, fontSize = 12.sp, color = if (on) Color.White else palette.text, fontWeight = FontWeight.SemiBold)
            }
        }
    }
}
