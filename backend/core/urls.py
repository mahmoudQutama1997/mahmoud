from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (ProductViewSet, OrderViewSet, SettlementViewSet, DelayReportViewSet,
                    SupportTicketViewSet, DashboardSummaryView, MerchantViewSet, MerchantProfileSelfView, CaptainSelfView, AdminOperationsView, AdminUsersView, AdminUserDetailView, AdminUserSubscriptionView, AdminSubscriptionPaymentView, AdminSubscriptionsView, AdminCaptainApprovalView, ChangePasswordView, AccountProfileView, AdminStoresView, MerchantReportsView)
router = DefaultRouter()
router.register("merchants", MerchantViewSet, basename="merchant")
router.register("products", ProductViewSet, basename="product")
router.register("orders", OrderViewSet, basename="order")
router.register("settlements", SettlementViewSet, basename="settlement")
router.register("delay-reports", DelayReportViewSet, basename="delay-report")
router.register("support-tickets", SupportTicketViewSet, basename="support-ticket")
urlpatterns = [path("merchant/profile/", MerchantProfileSelfView.as_view()), path("merchant/reports/", MerchantReportsView.as_view()), path("account/change-password/", ChangePasswordView.as_view()), path("account/profile/", AccountProfileView.as_view()), path("admin/users/", AdminUsersView.as_view()), path("admin/stores/", AdminStoresView.as_view()), path("admin/stores/<int:store_id>/", AdminStoresView.as_view()), path("admin/users/<int:user_id>/", AdminUserDetailView.as_view()), path("admin/users/<int:user_id>/subscription/", AdminUserSubscriptionView.as_view()), path("admin/subscriptions/", AdminSubscriptionsView.as_view()), path("admin/subscriptions/<int:subscription_id>/", AdminSubscriptionsView.as_view()), path("admin/subscriptions/<int:subscription_id>/payments/", AdminSubscriptionPaymentView.as_view()), path("captains/me/", CaptainSelfView.as_view()), path("admin/captains/<int:captain_profile_id>/approval/", AdminCaptainApprovalView.as_view()), path("", include(router.urls)), path("dashboard/summary/", DashboardSummaryView.as_view()), path("admin/operations/", AdminOperationsView.as_view())]
