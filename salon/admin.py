from django.contrib import admin
from .models import Service, Appointment, NotificationLog, BlockedTimeSlot, Profile, Staff, Payment, Expense

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'price', 'duration', 'is_active', 'created_at']
    list_filter = ['is_active', 'category']
    search_fields = ['name']

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ['user', 'service', 'date', 'time', 'status', 'payment_status', 'assigned_staff', 'staff']
    list_filter = ['status', 'payment_status', 'date']
    search_fields = ['user__username', 'service__name']
    date_hierarchy = 'date'

@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ['appointment', 'notification_type', 'recipient_email', 'status', 'sent_at']
    list_filter = ['status', 'notification_type']

@admin.register(BlockedTimeSlot)
class BlockedTimeSlotAdmin(admin.ModelAdmin):
    list_display = ['date', 'start_time', 'end_time', 'reason']

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone']

@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'specialization', 'availability', 'phone']
    list_filter = ['role', 'availability']

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['receipt_number', 'appointment', 'amount', 'payment_method', 'payment_status', 'transaction_code', 'payment_date']
    list_filter = ['payment_status', 'payment_method']

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'amount', 'date']
    list_filter = ['category']
    date_hierarchy = 'date'
