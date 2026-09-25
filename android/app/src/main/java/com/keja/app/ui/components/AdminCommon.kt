package com.keja.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.keja.app.ui.theme.LocalKejaPalette
import java.text.SimpleDateFormat
import java.util.Locale
import java.util.TimeZone

/** "3 min ago" from a backend ISO timestamp (UTC). Avoids java.time (minSdk 24). */
fun relativeTime(iso: String?): String {
    if (iso.isNullOrBlank() || iso.length < 19) return ""
    return try {
        val fmt = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.US)
        fmt.timeZone = TimeZone.getTimeZone("UTC")
        val then = fmt.parse(iso.substring(0, 19))?.time ?: return ""
        val s = ((System.currentTimeMillis() - then) / 1000).coerceAtLeast(0)
        when {
            s < 60 -> "just now"
            s < 3600 -> "${s / 60} min ago"
            s < 86400 -> "${s / 3600} h ago"
            else -> "${s / 86400} d ago"
        }
    } catch (e: Exception) {
        ""
    }
}

@Composable
fun Pill(text: String, bg: Color, fg: Color) {
    Text(
        text,
        color = fg,
        fontSize = 10.sp,
        fontWeight = FontWeight.ExtraBold,
        modifier = Modifier.clip(RoundedCornerShape(50)).background(bg).padding(horizontal = 9.dp, vertical = 3.dp),
    )
}

/** Page shell used by every admin screen: eyebrow + title + short explanation, scrollable. */
@Composable
fun AdminPage(eyebrow: String, title: String, subtitle: String, content: @Composable ColumnScope.() -> Unit) {
    val palette = LocalKejaPalette.current
    Column(
        Modifier
            .fillMaxSize()
            .background(palette.bg)
            .verticalScroll(rememberScrollState())
            .padding(20.dp),
    ) {
        Text(eyebrow, color = palette.primary, fontWeight = FontWeight.Bold, fontSize = 11.sp)
        Text(title, fontSize = 24.sp, fontWeight = FontWeight.ExtraBold, color = palette.text)
        Spacer(Modifier.height(4.dp))
        Text(subtitle, color = palette.muted, fontSize = 13.sp)
        Spacer(Modifier.height(16.dp))
        content()
        Spacer(Modifier.height(24.dp))
    }
}

@Composable
fun CardShell(content: @Composable ColumnScope.() -> Unit) {
    val palette = LocalKejaPalette.current
    Column(
        Modifier
            .fillMaxWidth()
            .padding(bottom = 12.dp)
            .clip(RoundedCornerShape(16.dp))
            .background(palette.card)
            .padding(14.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
        content = content,
    )
}

@Composable
fun ReasonDialog(
    title: String,
    hint: String,
    required: Boolean,
    confirmLabel: String,
    onDismiss: () -> Unit,
    onConfirm: (String) -> Unit,
) {
    var text by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = {
            Column {
                OutlinedTextField(value = text, onValueChange = { text = it; error = null }, placeholder = { Text(hint) }, minLines = 2, modifier = Modifier.fillMaxWidth())
                error?.let { Text(it, color = Color(0xFFEF4444), fontSize = 12.sp) }
            }
        },
        confirmButton = {
            TextButton(onClick = {
                if (required && text.isBlank()) error = "Please add a short reason." else onConfirm(text.trim())
            }) { Text(confirmLabel) }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}

@Composable
fun ConfirmDialog(title: String, text: String, confirmLabel: String, onDismiss: () -> Unit, onConfirm: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = { Text(text) },
        confirmButton = { TextButton(onClick = onConfirm) { Text(confirmLabel, color = Color(0xFFEF4444)) } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}
