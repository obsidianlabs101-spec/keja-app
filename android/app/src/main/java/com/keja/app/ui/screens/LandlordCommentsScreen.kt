package com.keja.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
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
import com.keja.app.data.model.HostCommentDto
import com.keja.app.ui.components.Avatar
import com.keja.app.ui.components.relativeTime
import com.keja.app.ui.theme.LocalKejaPalette

/** A landlord's private-feeling inbox of what renters have said about them.
 * Same data as the public "What renters say" section on their profile
 * (GET /properties/landlord/{id}/comments), just laid out as its own page. */
@Composable
fun LandlordCommentsScreen(onBack: () -> Unit) {
    val palette = LocalKejaPalette.current
    val context = LocalContext.current
    val repo = remember { AppContainer.repository(context) }
    val user by repo.currentUser.collectAsState()

    var comments by remember { mutableStateOf<List<HostCommentDto>?>(null) }
    var failed by remember { mutableStateOf(false) }
    var reloadKey by remember { mutableStateOf(0) }

    LaunchedEffect(user?.id, reloadKey) {
        val id = user?.id
        if (id.isNullOrBlank()) return@LaunchedEffect
        failed = false
        comments = null
        runCatching { repo.hostComments(id) }
            .onSuccess { comments = it }
            .onFailure { failed = true }
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

        val list = comments
        when {
            failed -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text("Couldn't load your comments", color = palette.text, fontWeight = FontWeight.Bold)
                    Spacer(Modifier.height(8.dp))
                    TextButton(onClick = { reloadKey++ }) { Text("Retry") }
                }
            }
            list == null -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { com.keja.app.ui.components.KejaLoader() }
            else -> LazyColumn(
                contentPadding = PaddingValues(start = 18.dp, end = 18.dp, bottom = 24.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                item {
                    Text("Comments", fontSize = 26.sp, fontWeight = FontWeight.ExtraBold, color = palette.text)
                    Text(
                        if (list.isEmpty()) "What renters say about you will appear here."
                        else "${list.size} ${if (list.size == 1) "renter has" else "renters have"} commented on your profile.",
                        fontSize = 13.sp, color = palette.muted,
                    )
                    Spacer(Modifier.height(6.dp))
                }
                if (list.isEmpty()) {
                    item {
                        com.keja.app.ui.components.ThemedCard(Modifier.fillMaxWidth().padding(end = 6.dp, bottom = 7.dp)) {
                        Column(
                            Modifier.fillMaxWidth().padding(24.dp),
                            horizontalAlignment = Alignment.CenterHorizontally,
                        ) {
                            Text("No comments yet", fontWeight = FontWeight.Bold, color = palette.text)
                            Spacer(Modifier.height(4.dp))
                            Text(
                                "Any signed-in renter can leave one comment on your profile (they can edit or delete it later).",
                                fontSize = 12.sp, color = palette.muted,
                            )
                        }
                        }
                    }
                } else {
                    items(list, key = { it.id }) { c ->
                        com.keja.app.ui.components.ThemedCard(Modifier.fillMaxWidth().padding(end = 6.dp, bottom = 7.dp)) {
                        Column(Modifier.fillMaxWidth().padding(14.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Avatar(url = c.author_avatar, name = c.author_name, size = 34.dp)
                                Spacer(Modifier.width(10.dp))
                                Column {
                                    Text(c.author_name, fontWeight = FontWeight.Bold, fontSize = 14.sp, color = palette.text)
                                    Text(relativeTime(c.created_at), fontSize = 11.sp, color = palette.muted)
                                }
                            }
                            Spacer(Modifier.height(8.dp))
                            Text(c.body, fontSize = 14.sp, color = palette.text, lineHeight = 20.sp)
                        }
                        }
                    }
                }
            }
        }
    }
}
