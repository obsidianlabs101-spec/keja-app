package com.keja.app.ui.nav

import androidx.compose.foundation.layout.*
import androidx.compose.material3.Scaffold
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import androidx.navigation.NavType
import com.keja.app.data.AppContainer
import com.keja.app.ui.components.KejaBottomNav
import com.keja.app.ui.components.bottomNavItems
import com.keja.app.ui.screens.*

private const val ROUTE_AUTH = "auth"
private const val ROUTE_HOME = "home"
private const val ROUTE_DISCOVER = "discover"
private const val ROUTE_INTERESTED = "interested"
private const val ROUTE_PROFILE = "profile"
private const val ROUTE_PROPERTY = "property/{id}"
private const val ROUTE_LANDLORD_PROFILE = "landlord-profile/{id}"
private const val ROUTE_LANDLORD_DASHBOARD = "landlord-dashboard"
private const val ROUTE_ADMIN_DASHBOARD = "admin-dashboard"

@Composable
fun KejaNavGraph() {
    val navController = rememberNavController()
    val context = LocalContext.current
    val repo = remember { AppContainer.repository(context) }
    val user by repo.currentUser.collectAsState()
    val backStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = backStackEntry?.destination?.route

    val showBottomBar = currentRoute in listOf(ROUTE_HOME, ROUTE_DISCOVER, ROUTE_INTERESTED, ROUTE_PROFILE)

    Scaffold(
        bottomBar = {
            if (showBottomBar) {
                KejaBottomNav(currentRoute = currentRoute) { route ->
                    navController.navigate(route) {
                        popUpTo(ROUTE_HOME) { saveState = true }
                        launchSingleTop = true
                        restoreState = true
                    }
                }
            }
        },
    ) { padding ->
        NavHost(
            navController = navController,
            startDestination = ROUTE_HOME,
            modifier = Modifier.padding(padding),
        ) {
            composable(ROUTE_AUTH) {
                AuthScreen(onAuthenticated = {
                    navController.popBackStack()
                })
            }
            composable(ROUTE_HOME) {
                HomeScreen(onOpenProperty = { id -> navController.navigate("property/$id") })
            }
            composable(ROUTE_DISCOVER) {
                DiscoverScreen(
                    isLoggedIn = user != null,
                    onRequireLogin = { navController.navigate(ROUTE_AUTH) },
                    onOpenProperty = { id -> navController.navigate("property/$id") },
                    onOpenLandlord = { id -> navController.navigate("landlord-profile/$id") },
                )
            }
            composable(ROUTE_INTERESTED) {
                InterestedScreen(
                    isLoggedIn = user != null,
                    onRequireLogin = { navController.navigate(ROUTE_AUTH) },
                    onOpenProperty = { id -> navController.navigate("property/$id") },
                )
            }
            composable(ROUTE_PROFILE) {
                ProfileScreen(
                    onRequireLogin = { navController.navigate(ROUTE_AUTH) },
                    onOpenLandlordDashboard = { navController.navigate(ROUTE_LANDLORD_DASHBOARD) },
                    onOpenAdminDashboard = { navController.navigate(ROUTE_ADMIN_DASHBOARD) },
                    onLoggedOut = {
                        navController.navigate(ROUTE_HOME) { popUpTo(0) }
                    },
                )
            }
            composable(
                ROUTE_PROPERTY,
                arguments = listOf(navArgument("id") { type = NavType.StringType }),
            ) { entry ->
                val id = entry.arguments?.getString("id") ?: return@composable
                PropertyDetailScreen(
                    propertyId = id,
                    onBack = { navController.popBackStack() },
                    onRequireLogin = { navController.navigate(ROUTE_AUTH) },
                )
            }
            composable(
                ROUTE_LANDLORD_PROFILE,
                arguments = listOf(navArgument("id") { type = NavType.StringType }),
            ) { entry ->
                val id = entry.arguments?.getString("id") ?: return@composable
                LandlordProfileScreen(
                    landlordId = id,
                    onBack = { navController.popBackStack() },
                    onOpenProperty = { pid -> navController.navigate("property/$pid") },
                )
            }
            composable(ROUTE_LANDLORD_DASHBOARD) {
                if (user == null) {
                    LaunchedEffect(Unit) { navController.navigate(ROUTE_AUTH) }
                } else {
                    LandlordDashboardScreen(onBack = { navController.popBackStack() })
                }
            }
            composable(ROUTE_ADMIN_DASHBOARD) {
                if (user?.is_admin != true) {
                    LaunchedEffect(Unit) { navController.popBackStack() }
                } else {
                    AdminDashboardScreen(onBack = { navController.popBackStack() })
                }
            }
        }
    }
}
