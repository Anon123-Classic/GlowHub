from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='salon/password_reset.html'
    ), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='salon/password_reset_done.html'
    ), name='password_reset_done'),
    path('password-reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='salon/password_reset_confirm.html'
    ), name='password_reset_confirm'),
    path('password-reset/complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='salon/password_reset_complete.html'
    ), name='password_reset_complete'),

    path('services/', views.services_list, name='services'),
    path('services/<int:pk>/', views.service_detail, name='service_detail'),

    path('dashboard/', views.customer_dashboard, name='customer_dashboard'),
    path('book/', views.book_appointment, name='book_appointment'),
    path('get-slots/', views.get_slots, name='get_slots'),
    path('cancel/<int:pk>/', views.cancel_appointment, name='cancel_appointment'),
    path('reschedule/<int:pk>/', views.reschedule_appointment, name='reschedule_appointment'),

    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/bookings/', views.admin_bookings, name='admin_bookings'),
    path('admin/bookings/export/', views.export_bookings, name='export_bookings'),
    path('admin/bookings/<int:pk>/status/<str:status>/', views.update_booking_status, name='update_booking_status'),
    path('admin/bookings/<int:pk>/assign/', views.assign_staff, name='assign_staff'),
    path('admin/services/', views.admin_services, name='admin_services'),
    path('admin/services/<int:pk>/edit/', views.edit_service, name='edit_service'),
    path('admin/services/<int:pk>/delete/', views.delete_service, name='delete_service'),
    path('admin/customers/', views.admin_customers, name='admin_customers'),
    path('admin/block-slot/', views.block_slot, name='block_slot'),
    path('admin/notifications/', views.admin_notifications, name='admin_notifications'),
    path('admin/send-reminders/', views.send_reminders, name='send_reminders'),
    
    # Staff Management
    path('admin/staff/', views.admin_staff, name='admin_staff'),
    path('admin/staff/add/', views.add_staff, name='add_staff'),
    path('admin/staff/<int:pk>/edit/', views.edit_staff, name='edit_staff'),
    path('admin/staff/<int:pk>/delete/', views.delete_staff, name='delete_staff'),
    path('admin/staff/<int:pk>/toggle-availability/', views.toggle_staff_availability, name='toggle_staff_availability'),
    
    # Payments
    path('admin/payments/', views.admin_payments, name='admin_payments'),
    
    # Expenses
    path('admin/expenses/', views.admin_expenses, name='admin_expenses'),
    path('admin/expenses/add/', views.add_expense, name='add_expense'),
    path('admin/expenses/<int:pk>/edit/', views.edit_expense, name='edit_expense'),
    path('admin/expenses/<int:pk>/delete/', views.delete_expense, name='delete_expense'),
    
    # Finance Dashboard
    path('admin/finance/', views.finance_dashboard, name='finance_dashboard'),
    path('admin/finance/export/', views.export_finance_csv, name='export_finance_csv'),
    
    # Staff Dashboard
    path('staff/dashboard/', views.staff_dashboard, name='staff_dashboard'),
    path('staff/profile/', views.staff_profile, name='staff_profile'),
    path('staff/profile/edit/', views.staff_update_profile, name='staff_update_profile'),
    path('staff/change-password/', views.staff_change_password, name='staff_change_password'),
    path('staff/appointments/', views.staff_appointments, name='staff_appointments'),
    path('staff/appointment/<int:pk>/', views.staff_appointment_detail, name='staff_appointment_detail'),
    path('staff/appointment/<int:pk>/in-progress/', views.staff_mark_in_progress, name='staff_mark_in_progress'),
    path('staff/appointment/<int:pk>/completed/', views.staff_mark_completed, name='staff_mark_completed'),
    
    # Cashier Dashboard
    path('cashier/dashboard/', views.cashier_dashboard, name='cashier_dashboard'),
    path('cashier/walkin/', views.cashier_walkin, name='cashier_walkin'),
    path('cashier/payment/<int:pk>/', views.process_payment, name='process_payment'),
    path('cashier/receipt/<int:pk>/', views.cashier_receipt, name='cashier_receipt'),
    path('cashier/payments/', views.cashier_payment_history, name='cashier_payment_history'),
    
    # # M-Pesa (disabled)
    # path('mpesa/callback/', views.mpesa_callback, name='mpesa_callback'),
]
