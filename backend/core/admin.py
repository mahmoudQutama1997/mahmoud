from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import *
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets=UserAdmin.fieldsets + (("Waselni",{"fields":("role","phone","identity_number","subscription_required","must_change_password","language","profile_image")}),)
admin.site.register([MerchantProfile,CaptainProfile,Product,Order,CashSettlement,DelayReport,Rating,SupportTicket,Subscription,SubscriptionPayment])
