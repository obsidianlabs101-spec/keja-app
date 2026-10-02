package com.keja.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.ChatBubbleOutline
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
import com.keja.app.data.model.LandlordPropertiesResponse
import com.keja.app.ui.components.Avatar
import com.keja.app.ui.components.KejaPrimaryButton
import com.keja.app.ui.components.PropertyCard
import com.keja.app.ui.components.relativeTime
import com.keja.app.ui.theme.LocalKejaPalette
import kotlinx.coroutines.launch

@Composable
fun LandlordProfileScreen(landlordId: String, onBack: () -> Unit, onOpenProperty: (String) -> Unit) {
    val palette = LocalKejaPalette.current
    val context = LocalContext.current
    val repo = remember { AppContainer.repository(context) }

    var data by remember { mutableStateOf<LandlordPropertiesResponse?>(null) }
    var loading by remember { mutableStateOf(true) }

    LaunchedEffect(landlordId) {
        loading = true
        data = runCatching { repo.landlordProperties(landlordId) }.getOrNull()
        loading = false
    }

    Column(Modifier.fillMaxSize().background(palette.bg)) {
        Row(
            Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 12.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("LANDLORD", color = palette.primary, fontWeight = FontWeight.Bold, fontSize = 11.sp)
            TextButton(onClick = onBack) { Text("Back") }
        }

        val d = data
        when {
            loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { com.keja.app.ui.components.KejaLoader() }
            d == null -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("Couldn't load this profile", color = palette.muted)
            }
            else -> LazyColumn(
                contentPadding = PaddingValues(start = 18.dp, end = 18.dp, bottom = 24.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp),
            ) {
                item {
                    Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
                        Avatar(url = d.landlord.profile_picture, name = d.landlord.full_name, size = 96.dp)
                        Spacer(Modifier.height(10.dp))
                        Text(d.landlord.full_name, fontSize = 22.sp, fontWeight = FontWeight.ExtraBold, color = palette.text)
                        d.landlord.username?.let { Text("@$it", fontSize = 13.sp, color = palette.muted) }
                        d.landlord.bio?.takeIf { it.isNotBlank() }?.let {
                            Spacer(Modifier.height(8.dp))
                            Text(it, fontSize = 13.sp, color = palette.muted, lineHeight = 18.sp)
                        }
                        Spacer(Modifier.height(14.dp))
                        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                            ProfileStat("Properties uploaded", d.property_count.toString(), Modifier.weight(1f))
                            ProfileStat("Available now", d.properties.size.toString(), Modifier.weight(1f))
                        }
                        Spacer(Modifier.height(14.dp))
                        HostCommentsSection(landlordId = landlordId)
                        Spacer(Modifier.height(14.dp))
                        Text(
                            if (d.properties.isEmpty()) "No available listings right now" else "Available listings",
                            modifier = Modifier.fillMaxWidth(),
                            fontWeight = FontWeight.ExtraBold, fontSize = 16.sp, color = palette.text,
                        )
                    }
                }
                items(d.properties) { p -> PropertyCard(property = p, onClick = { onOpenProperty(p.id) }) }
            }
        }
    }
}

@Composable
private fun ProfileStat(label: String, value: String, modifier: Modifier = Modifier) {
    val palette = LocalKejaPalette.current
    com.keja.app.ui.components.ThemedCard(modifier = modifier.padding(end = 6.dp, bottom = 7.dp)) {
    Column(Modifier.fillMaxWidth().padding(14.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Text(value, fontSize = 26.sp, fontWeight = FontWeight.ExtraBold, color = palette.text)
        Text(label, fontSize = 11.sp, color = palette.muted)
    }    }
}

/** "What renters say" — a public comment thread on the landlord's profile.
 * One comment per renter per landlord; posting again edits it in place
 * (see /properties/landlord/{id}/comments on the backend). */
@Composable
private fun HostCommentsSection(landlordId: String) {
    val palette = LocalKejaPalette.current
    val context = LocalContext.current
    val repo = remember { AppContainer.repository(context) }
    val scope = rememberCoroutineScope()
    val currentUser by repo.currentUser.collectAsState()

    var comments by remember { mutableStateOf<List<com.keja.app.data.model.HostCommentDto>?>(null) }
    var draft by remember { mutableStateOf("") }
    var posting by remember { mutableStateOf(false) }

    fun load() {
        scope.launch {
            comments = runCatching { repo.hostComments(landlordId) }.getOrNull()
            comments?.find { it.is_mine }?.let { draft = it.body }
        }
    }
    LaunchedEffect(landlordId) { load() }

    val canWrite = currentUser != null && currentUser?.id != landlordId
    val mine = comments?.find { it.is_mine }
    val others = comments?.filterNot { it.is_mine } ?: emptyList()

    Column(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(20.dp)).background(palette.card).padding(16.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.size(36.dp).clip(CircleShape).background(palette.primaryLight), contentAlignment = Alignment.Center) {
                Icon(Icons.Outlined.ChatBubbleOutline, contentDescription = null, tint = palette.primary, modifier = Modifier.size(18.dp))
            }
            Spacer(Modifier.width(10.dp))
            Column {
                Text("What renters say", fontWeight = FontWeight.Bold, color = palette.text)
                Text("Comments about this host", fontSize = 11.sp, color = palette.muted)
            }
        }
        Spacer(Modifier.height(12.dp))

        when {
            comments == null -> com.keja.app.ui.components.KejaLoader(size = 28.dp)
            others.isEmpty() -> Text("No comments yet. Be the first to share how renting from this landlord went.", fontSize = 13.sp, color = palette.muted)
            else -> Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                others.forEach { c ->
                    Column {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Avatar(url = c.author_avatar, name = c.author_name, size = 26.dp)
                            Spacer(Modifier.width(8.dp))
                            Text(c.author_name, fontWeight = FontWeight.Bold, fontSize = 13.sp, color = palette.text)
                            Spacer(Modifier.width(6.dp))
                            Text(relativeTime(c.created_at), fontSize = 11.sp, color = palette.muted)
                        }
                        Spacer(Modifier.height(2.dp))
                        Text(c.body, fontSize = 13.sp, color = palette.text)
                    }
                }
            }
        }

        if (canWrite) {
            Spacer(Modifier.height(14.dp))
            HorizontalDivider(color = palette.border)
            Spacer(Modifier.height(12.dp))
            OutlinedTextField(
                value = draft,
                onValueChange = { if (it.length <= 500) draft = it },
                placeholder = { Text("Share how renting from this landlord went…") },
                minLines = 2,
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                KejaPrimaryButton(
                    text = if (posting) "Saving…" else if (mine != null) "Update comment" else "Post comment",
                    enabled = !posting && draft.isNotBlank(),
                    onClick = {
                        posting = true
                        scope.launch {
                            runCatching { repo.setHostComment(landlordId, draft.trim()) }
                                .onFailure { android.widget.Toast.makeText(context, it.message ?: "Couldn't post comment", android.widget.Toast.LENGTH_SHORT).show() }
                            posting = false
                            load()
                        }
                    },
                )
                if (mine != null) {
                    OutlinedButton(onClick = {
                        scope.launch {
                            runCatching { repo.deleteHostComment(landlordId) }
                            draft = ""
                            load()
                        }
                    }) { Text("Delete", color = Color(0xFFEF4444)) }
                }
            }
        } else if (currentUser == null) {
            Spacer(Modifier.height(10.dp))
            Text("Log in to leave a comment.", fontSize = 12.sp, color = palette.muted)
        }
    }
}
