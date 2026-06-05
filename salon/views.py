from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.db.models import Count, Sum, Q
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_protect
from django.utils.decorators import method_decorator
from django.core.paginator import Paginator
from django.conf import settings
from datetime import datetime, timedelta, date
import csv
import json
import secrets
import string
import logging
# import base64  # (was used by M-Pesa)
# import requests  # (was used by M-Pesa)

logger = logging.getLogger(__name__)

from .models import Service, Appointment, NotificationLog, BlockedTimeSlot, Staff, Payment, Expense, Profile
from .forms import RegistrationForm, LoginForm, AppointmentForm, ServiceForm, BlockTimeSlotForm, RescheduleForm, StaffForm, CreateStaffForm, StaffProfileForm, ProcessPaymentForm, ExpenseForm, WalkInForm
from .utils import send_booking_confirmation, send_status_update, send_staff_invite_email, send_payment_confirmation, get_available_slots, generate_walkin_username

def is_admin(user):
    """Pure admin = is_staff but no staff_profile"""
    if not user.is_staff:
        return False
    try:
        user.staff_profile
        return False
    except Exception:
        return True

def is_staff_member(user):
    """Staff member = is_staff with a staff_profile (excluding cashiers)"""
    if not user.is_staff:
        return False
    try:
        profile = user.staff_profile
        if profile.role == 'cashier':
            return False
        return True
    except Exception:
        return False

def is_cashier(user):
    """Cashier (role='cashier') or pure admin (no staff_profile)"""
    if not user.is_staff:
        return False
    try:
        profile = user.staff_profile
        return profile.role == 'cashier'
    except Exception:
        # Pure admin (no staff_profile) — allow access
        return True

def home(request):
    services = Service.objects.filter(is_active=True).order_by('-created_at')[:6]
    return render(request, 'salon/home.html', {'services': services})

@ensure_csrf_cookie
@csrf_protect
def register_view(request):
    if request.user.is_authenticated:
        return redirect('customer_dashboard')
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Welcome {user.first_name}! Your account has been created.')
            return redirect('customer_dashboard')
    else:
        form = RegistrationForm()
    return render(request, 'salon/register.html', {'form': form})

@ensure_csrf_cookie
@csrf_protect
def login_view(request):
    if request.user.is_authenticated:
        return redirect('customer_dashboard')
    if request.method == 'POST':
        form = LoginForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            remember_me = form.cleaned_data.get('remember_me', False)
            login(request, user)
            
            # Handle "Remember Me" functionality
            if remember_me:
                # Set session to expire in 30 days (2592000 seconds)
                request.session.set_expiry(2592000)
            else:
                # Expire at browser close for security
                request.session.set_expiry(0)
            
            messages.success(request, f'Welcome back, {user.first_name}!')
            if user.is_staff:
                try:
                    staff_profile = user.staff_profile
                except Exception:
                    staff_profile = None
                if staff_profile and staff_profile.must_change_password:
                    return redirect('staff_change_password')
                if staff_profile:
                    return redirect('staff_dashboard')
                return redirect('admin_dashboard')
            return redirect('customer_dashboard')
        else:
            messages.error(request, 'Invalid username or password.')
    else:
        form = LoginForm()
    return render(request, 'salon/login.html', {'form': form})

def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('login')

@login_required
def customer_dashboard(request):
    appointments = Appointment.objects.filter(user=request.user)
    services = Service.objects.filter(is_active=True)

    stats = {
        'total': appointments.count(),
        'pending': appointments.filter(status='pending').count(),
        'approved': appointments.filter(status='approved').count(),
        'completed': appointments.filter(status='completed').count(),
        'cancelled': appointments.filter(status='cancelled').count(),
    }

    upcoming = appointments.filter(
        Q(status='pending') | Q(status='approved'),
        date__gte=timezone.now().date()
    ).order_by('date', 'time')[:5]

    return render(request, 'salon/customer/dashboard.html', {
        'appointments': appointments,
        'services': services,
        'stats': stats,
        'upcoming': upcoming,
    })

@login_required
@ensure_csrf_cookie
@csrf_protect
def book_appointment(request):
    services = Service.objects.filter(is_active=True)
    selected_service_id = request.GET.get('service')
    initial = {}
    selected_service = None
    if selected_service_id:
        try:
            selected_service = services.get(pk=selected_service_id)
            initial['service'] = selected_service.pk
        except Service.DoesNotExist:
            pass

    if request.method == 'POST':
        form = AppointmentForm(request.POST)
        form.user = request.user
        form.instance.user = request.user
        if form.is_valid():
            appointment = form.save(commit=False)
            appointment.save()
            send_booking_confirmation(appointment)
            messages.success(request, 'Appointment booked successfully! Check your email for confirmation.')
            return redirect('customer_dashboard')
        else:
            for error in form.non_field_errors():
                messages.error(request, error)
    else:
        form = AppointmentForm(initial=initial)

    return render(request, 'salon/customer/book_appointment.html', {
        'form': form,
        'services': services,
        'selected_service_id': selected_service_id,
        'selected_service': selected_service,
    })

@login_required
def get_slots(request):
    date_str = request.GET.get('date')
    service_id = request.GET.get('service')
    appointment_id = request.GET.get('appointment')
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return JsonResponse({'slots': []})

    if selected_date < timezone.now().date():
        return JsonResponse({'slots': []})

    service = None
    if service_id:
        try:
            service = Service.objects.get(pk=service_id, is_active=True)
        except Service.DoesNotExist:
            service = None

    try:
        exclude_appointment_id = int(appointment_id) if appointment_id else None
    except (TypeError, ValueError):
        exclude_appointment_id = None

    slots = get_available_slots(
        selected_date,
        service=service,
        exclude_appointment_id=exclude_appointment_id
    )
    if selected_date == timezone.now().date():
        now = timezone.now()
        slots = [s for s in slots if s['time'] > now.strftime('%H:%M')]

    return JsonResponse({'slots': slots})

@login_required
def cancel_appointment(request, pk):
    appointment = get_object_or_404(Appointment, pk=pk, user=request.user)
    if appointment.cancel_allowed():
        appointment.status = 'cancelled'
        appointment.save()
        send_status_update(appointment)
        messages.success(request, 'Appointment cancelled successfully.')
    else:
        messages.error(request, 'Cancellation is only allowed at least 2 hours before the appointment.')
    return redirect('customer_dashboard')

@login_required
@csrf_protect
def reschedule_appointment(request, pk):
    appointment = get_object_or_404(Appointment, pk=pk, user=request.user)
    if not appointment.can_reschedule():
        messages.error(request, 'This appointment cannot be rescheduled.')
        return redirect('customer_dashboard')

    services = Service.objects.filter(is_active=True)
    if request.method == 'POST':
        form = RescheduleForm(request.POST, instance=appointment)
        if form.is_valid():
            new_date = form.cleaned_data['date']
            new_time = form.cleaned_data['time']
            appointment.date = new_date
            appointment.time = new_time
            appointment.status = 'pending'
            appointment.save()
            send_status_update(appointment)
            messages.success(request, 'Appointment rescheduled successfully! The customer has been notified.')
            return redirect('customer_dashboard')
    else:
        form = RescheduleForm(instance=appointment)
    return render(request, 'salon/customer/reschedule.html', {
        'form': form,
        'appointment': appointment,
        'services': services,
    })

@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    total_appointments = Appointment.objects.count()
    pending_appointments = Appointment.objects.filter(status='pending').count()
    approved_appointments = Appointment.objects.filter(status='approved').count()
    in_progress_appointments = Appointment.objects.filter(status='in_progress').count()
    completed_appointments = Appointment.objects.filter(status='completed').count()
    awaiting_payment_appointments = Appointment.objects.filter(status='awaiting_payment').count()
    cancelled_appointments = Appointment.objects.filter(status='cancelled').count()
    total_services = Service.objects.count()
    total_customers = Appointment.objects.values('user').distinct().count()
    assigned_bookings = Appointment.objects.filter(assigned_staff__isnull=False).count()
    unassigned_bookings = Appointment.objects.filter(assigned_staff__isnull=True).exclude(status='cancelled').count()

    today = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())

    weekly_data = Appointment.objects.filter(
        date__gte=week_start, date__lte=today
    ).values('date').annotate(
        count=Count('id')
    ).order_by('date')

    import calendar
    week_days = []
    week_counts = []
    for i in range(7):
        d = week_start + timedelta(days=i)
        week_days.append(calendar.day_abbr[d.weekday()])
        count = 0
        for wd in weekly_data:
            if wd['date'] == d:
                count = wd['count']
                break
        week_counts.append(count)

    recent_appointments = Appointment.objects.select_related('user', 'service').order_by('-created_at')[:10]

    failed_notifications = NotificationLog.objects.filter(status='failed').count()

    total_revenue = Payment.objects.filter(payment_status='paid').aggregate(total=Sum('amount'))['total'] or 0

    return render(request, 'salon/admin/dashboard.html', {
        'total_appointments': total_appointments,
        'pending_appointments': pending_appointments,
        'approved_appointments': approved_appointments,
        'in_progress_appointments': in_progress_appointments,
        'completed_appointments': completed_appointments,
        'awaiting_payment_appointments': awaiting_payment_appointments,
        'cancelled_appointments': cancelled_appointments,
        'total_services': total_services,
        'total_customers': total_customers,
        'total_revenue': total_revenue,
        'assigned_bookings': assigned_bookings,
        'unassigned_bookings': unassigned_bookings,
        'week_days': json.dumps(week_days),
        'week_counts': json.dumps(week_counts),
        'recent_appointments': recent_appointments,
        'failed_notifications': failed_notifications,
    })

@login_required
@user_passes_test(is_admin)
def admin_bookings(request):
    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('search', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    bookings = Appointment.objects.select_related('user', 'service', 'assigned_staff__user').all()

    if status_filter:
        bookings = bookings.filter(status=status_filter)
    if search_query:
        bookings = bookings.filter(
            Q(user__username__icontains=search_query) |
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(service__name__icontains=search_query)
        )
    if date_from:
        bookings = bookings.filter(date__gte=date_from)
    if date_to:
        bookings = bookings.filter(date__lte=date_to)

    bookings = bookings.order_by('-date', '-time')

    assigned_count = bookings.filter(assigned_staff__isnull=False).count()
    unassigned_count = bookings.filter(assigned_staff__isnull=True).exclude(status='cancelled').count()

    paginator = Paginator(bookings, 15)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    return render(request, 'salon/admin/bookings.html', {
        'bookings': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'status_filter': status_filter,
        'search_query': search_query,
        'date_from': date_from,
        'date_to': date_to,
        'assigned_count': assigned_count,
        'unassigned_count': unassigned_count,
    })

@login_required
@user_passes_test(is_admin)
def update_booking_status(request, pk, status):
    valid_statuses = ['approved', 'awaiting_payment', 'completed', 'cancelled']
    if status not in valid_statuses:
        messages.error(request, 'Invalid status.')
        return redirect('admin_bookings')

    appointment = get_object_or_404(Appointment, pk=pk)
    appointment.status = status
    appointment.save()

    send_status_update(appointment)

    messages.success(request, f'Booking status updated to {status}.')
    return redirect('admin_bookings')

@login_required
@user_passes_test(is_admin)
@csrf_protect
def admin_services(request):
    services = Service.objects.all()
    selected_category = request.GET.get('category', '')

    if selected_category:
        services = services.filter(category=selected_category)

    services = services.order_by('category', 'name')

    if request.method == 'POST':
        form = ServiceForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Service added successfully.')
            return redirect('admin_services')
    else:
        form = ServiceForm()

    return render(request, 'salon/admin/services.html', {
        'services': services,
        'form': form,
        'categories': Service.CATEGORY_CHOICES,
        'selected_category': selected_category,
    })

@login_required
@user_passes_test(is_admin)
@csrf_protect
def edit_service(request, pk):
    service = get_object_or_404(Service, pk=pk)
    if request.method == 'POST':
        form = ServiceForm(request.POST, request.FILES, instance=service)
        if form.is_valid():
            form.save()
            messages.success(request, 'Service updated successfully.')
            return redirect('admin_services')
    else:
        form = ServiceForm(instance=service)
    return render(request, 'salon/admin/edit_service.html', {
        'form': form,
        'service': service,
    })

@login_required
@user_passes_test(is_admin)
def delete_service(request, pk):
    service = get_object_or_404(Service, pk=pk)
    service.delete()
    messages.success(request, 'Service deleted successfully.')
    return redirect('admin_services')

@login_required
@user_passes_test(is_admin)
def admin_customers(request):
    from django.contrib.auth.models import User
    customers = User.objects.filter(is_staff=False).annotate(
        appointment_count=Count('appointments')
    ).order_by('-date_joined')
    paginator = Paginator(customers, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    return render(request, 'salon/admin/customers.html', {'customers': page_obj, 'page_obj': page_obj, 'paginator': paginator})

@login_required
@user_passes_test(is_admin)
@csrf_protect
def block_slot(request):
    if request.method == 'POST':
        form = BlockTimeSlotForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Time slot blocked successfully.')
            return redirect('admin_bookings')
    else:
        form = BlockTimeSlotForm()
    return render(request, 'salon/admin/block_slot.html', {'form': form})

@login_required
@user_passes_test(is_admin)
@csrf_protect
def assign_staff(request, pk):
    appointment = get_object_or_404(Appointment, pk=pk)
    if request.method == 'POST':
        staff_id = request.POST.get('staff_id')
        if staff_id:
            staff_member = get_object_or_404(Staff, id=staff_id)
            appointment.assigned_staff = staff_member
            appointment.staff = staff_member.user
            appointment.save()
            messages.success(request, f'Assigned {staff_member.user.get_full_name()} to this booking.')
        else:
            appointment.assigned_staff = None
            appointment.staff = None
            appointment.save()
            messages.success(request, 'Staff unassigned.')
        return redirect('admin_bookings')

    service_category = appointment.service.category if appointment.service else None
    allowed_roles = []
    if service_category:
        allowed_roles = [role for role, cat in Staff.SERVICE_CATEGORY_MAP.items() if cat == service_category]
    if allowed_roles:
        staff_list = Staff.objects.filter(availability='available', role__in=allowed_roles).select_related('user')
    else:
        staff_list = Staff.objects.filter(availability='available').select_related('user')
    role_display = dict(Staff.ROLE_CHOICES)
    allowed_role_names = [role_display.get(r, r) for r in allowed_roles]
    return render(request, 'salon/admin/assign_staff.html', {
        'appointment': appointment,
        'staff_list': staff_list,
        'allowed_role_names': allowed_role_names,
        'service_category': service_category,
    })

@login_required
@user_passes_test(is_admin)
def export_bookings(request):
    from django.http import HttpResponse

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="bookings.csv"'

    writer = csv.writer(response)
    writer.writerow(['ID', 'Customer', 'Service', 'Date', 'Time', 'Status', 'Staff', 'Created'])

    bookings = Appointment.objects.select_related('user', 'service', 'assigned_staff__user').all()
    for b in bookings:
        staff_name = ''
        if b.assigned_staff:
            staff_name = b.assigned_staff.user.get_full_name()
        writer.writerow([
            b.id, b.user.username, b.service.name, b.date, b.time.strftime('%H:%M'),
            b.status, staff_name, b.created_at
        ])

    return response

@login_required
@user_passes_test(is_admin)
def admin_notifications(request):
    logs = NotificationLog.objects.select_related('appointment').order_by('-sent_at')
    paginator = Paginator(logs, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    return render(request, 'salon/admin/notifications.html', {'logs': page_obj, 'page_obj': page_obj, 'paginator': paginator})

@login_required
@user_passes_test(is_admin)
def send_reminders(request):
    if request.method == 'POST':
        from django.core.management import call_command
        from io import StringIO
        output = StringIO()
        call_command('send_reminders', stdout=output)
        result = output.getvalue()
        messages.success(request, f'Reminders sent: {result.strip()}')
    return redirect('admin_notifications')

def services_list(request):
    services = Service.objects.filter(is_active=True).order_by('category', 'name')
    return render(request, 'salon/services.html', {'services': services})

def service_detail(request, pk):
    service = get_object_or_404(Service, pk=pk, is_active=True)
    return render(request, 'salon/service_detail.html', {'service': service})

# ============ STAFF MANAGEMENT VIEWS ============

@login_required
@user_passes_test(is_admin)
def admin_staff(request):
    """List all staff members"""
    staff_members = Staff.objects.select_related('user').all()
    stats = {
        'total': staff_members.count(),
        'available': staff_members.filter(availability='available').count(),
        'unavailable': staff_members.filter(availability='unavailable').count(),
        'on_leave': staff_members.filter(availability='on_leave').count(),
    }
    return render(request, 'salon/admin/staff.html', {'staff_members': staff_members, 'stats': stats})

@login_required
@user_passes_test(is_admin)
def add_staff(request):
    """Create a new staff member"""
    temp_password = None
    created_user = None
    if request.method == 'POST':
        form = CreateStaffForm(request.POST)
        if form.is_valid():
            password = form.cleaned_data.get('password')
            if not password:
                password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(10))
                temp_password = password
            
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                email=form.cleaned_data['email'],
                password=password,
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
                is_staff=True
            )
            
            role = form.cleaned_data['role']
            specialization = form.cleaned_data.get('specialization', '')
            if not specialization:
                specialization = Staff(specialization='', role=role).get_default_specialization()
            staff = Staff.objects.create(
                user=user,
                role=role,
                phone=form.cleaned_data.get('phone', ''),
                specialization=specialization,
                bio=form.cleaned_data.get('bio', ''),
                expertise_years=form.cleaned_data.get('expertise_years', 1),
                must_change_password=True,
            )
            
            created_user = user
            if form.cleaned_data.get('send_invite_email'):
                send_staff_invite_email(user, password)
            
            form = CreateStaffForm()
    else:
        form = CreateStaffForm()
    
    return render(request, 'salon/admin/add_staff.html', {
        'form': form,
        'created_user': created_user,
        'temp_password': temp_password,
    })

@login_required
@user_passes_test(is_admin)
def edit_staff(request, pk):
    """Edit a staff member"""
    staff = get_object_or_404(Staff, pk=pk)
    if request.method == 'POST':
        form = StaffForm(request.POST, instance=staff)
        if form.is_valid():
            form.save()
            messages.success(request, f'{staff.user.first_name}\'s profile has been updated.')
            return redirect('admin_staff')
    else:
        form = StaffForm(instance=staff)
    
    return render(request, 'salon/admin/edit_staff.html', {'form': form, 'staff': staff})

@login_required
@user_passes_test(is_admin)
def delete_staff(request, pk):
    """Delete a staff member"""
    staff = get_object_or_404(Staff, pk=pk)
    if request.method == 'POST':
        user = staff.user
        staff.delete()
        user.delete()
        messages.success(request, f'Staff member has been deleted.')
        return redirect('admin_staff')
    
    return render(request, 'salon/admin/confirm_delete_staff.html', {'staff': staff})

@login_required
@user_passes_test(is_admin)
def toggle_staff_availability(request, pk):
    """Cycle staff availability: available → on_leave → unavailable → available"""
    staff = get_object_or_404(Staff, pk=pk)
    cycle = {'available': 'on_leave', 'on_leave': 'unavailable', 'unavailable': 'available'}
    staff.availability = cycle.get(staff.availability, 'available')
    staff.save()
    messages.success(request, f'{staff.user.first_name} is now {staff.get_availability_display()}.')
    return redirect('admin_staff')

@login_required
@user_passes_test(is_staff_member)
def staff_dashboard(request):
    """Staff member's personal dashboard"""
    staff = request.user.staff_profile
    today = timezone.now().date()
    
    appointments = Appointment.objects.filter(assigned_staff=staff).select_related('user', 'service').order_by('-date', '-time')
    
    today_appointments = appointments.filter(date=today, status__in=['pending', 'approved', 'in_progress'])
    upcoming_appointments = appointments.filter(
        date__gt=today,
        status__in=['pending', 'approved']
    )[:10]
    completed_today = appointments.filter(date=today, status__in=['awaiting_payment', 'completed']).count()
    
    in_progress = appointments.filter(status='in_progress')
    in_progress_count = in_progress.count()
    
    stats = {
        'total_appointments': appointments.count(),
        'awaiting_payment': appointments.filter(status='awaiting_payment').count(),
        'completed': appointments.filter(status='completed').count(),
        'today': today_appointments.count(),
        'today_completed': completed_today,
        'in_progress': in_progress_count,
    }
    
    return render(request, 'salon/staff/dashboard.html', {
        'staff': staff,
        'appointments': today_appointments,
        'upcoming': upcoming_appointments,
        'stats': stats,
    })

@login_required
@user_passes_test(is_staff_member)
def staff_mark_in_progress(request, pk):
    """Mark an appointment as in progress"""
    appointment = get_object_or_404(Appointment, pk=pk, assigned_staff=request.user.staff_profile)
    if appointment.status != 'approved':
        messages.error(request, 'Only approved appointments can be started.')
        return redirect('staff_dashboard')
    appointment.status = 'in_progress'
    appointment.save()
    messages.success(request, 'Appointment marked as in progress.')
    return redirect('staff_dashboard')

@login_required
@user_passes_test(is_staff_member)
def staff_mark_completed(request, pk):
    """Mark an appointment as completed by staff"""
    appointment = get_object_or_404(Appointment, pk=pk, assigned_staff=request.user.staff_profile)
    if appointment.status not in ['approved', 'in_progress']:
        messages.error(request, 'This appointment cannot be completed at this stage.')
        return redirect('staff_dashboard')
    appointment.status = 'awaiting_payment'
    appointment.payment_status = 'unpaid'
    appointment.save()
    send_status_update(appointment)
    messages.success(request, 'Service completed. Appointment is now awaiting payment.')
    return redirect('staff_dashboard')

@login_required
@user_passes_test(is_staff_member)
def staff_appointment_detail(request, pk):
    """View appointment details"""
    appointment = get_object_or_404(Appointment, pk=pk, assigned_staff=request.user.staff_profile)
    return render(request, 'salon/staff/appointment_detail.html', {
        'appointment': appointment,
    })

@login_required
@user_passes_test(is_staff_member)
def staff_profile(request):
    """Staff profile page"""
    staff = request.user.staff_profile
    return render(request, 'salon/staff/profile.html', {
        'staff': staff,
    })

@login_required
@user_passes_test(is_staff_member)
@csrf_protect
def staff_change_password(request):
    """Change staff password"""
    staff = request.user.staff_profile
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            staff.must_change_password = False
            staff.save()
            messages.success(request, 'Password changed successfully.')
            return redirect('staff_dashboard')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'salon/staff/change_password.html', {
        'form': form,
        'staff': staff,
        'must_change': staff.must_change_password,
    })


@login_required
@user_passes_test(is_staff_member)
def staff_appointments(request):
    """All appointments assigned to the logged-in staff member"""
    staff = request.user.staff_profile
    appointments = Appointment.objects.filter(assigned_staff=staff).select_related('user', 'service').order_by('-date', '-time')
    
    status_filter = request.GET.get('status', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    if status_filter:
        appointments = appointments.filter(status=status_filter)
    if date_from:
        appointments = appointments.filter(date__gte=date_from)
    if date_to:
        appointments = appointments.filter(date__lte=date_to)
    
    paginator = Paginator(appointments, 15)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'salon/staff/appointments.html', {
        'staff': staff,
        'appointments': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'status_filter': status_filter,
        'date_from': date_from,
        'date_to': date_to,
    })


@login_required
@user_passes_test(is_staff_member)
@csrf_protect
def staff_update_profile(request):
    """Staff can edit their own profile"""
    staff = request.user.staff_profile
    if request.method == 'POST':
        form = StaffProfileForm(request.POST, request.FILES, instance=staff)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('staff_profile')
    else:
        form = StaffProfileForm(instance=staff)
    return render(request, 'salon/staff/edit_profile.html', {
        'form': form,
        'staff': staff,
    })


# ============ CASHIER & WALK-IN VIEWS ============

@login_required
@user_passes_test(is_cashier)
def cashier_dashboard(request):
    today = timezone.now().date()
    
    pending_payments = Appointment.objects.filter(
        status='awaiting_payment', payment_status='unpaid'
    ).select_related('user', 'service', 'assigned_staff__user').order_by('-date', '-time')
    
    from django.db.models import Sum
    paid_today = Payment.objects.filter(
        payment_date__date=today, payment_status='paid'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    total_today = Payment.objects.filter(
        payment_date__date=today, payment_status='paid'
    ).count()
    
    return render(request, 'salon/cashier/dashboard.html', {
        'pending_payments': pending_payments,
        'pending_count': pending_payments.count(),
        'paid_today': paid_today,
        'total_today': total_today,
        'today': today,
    })


@login_required
@user_passes_test(is_cashier)
@csrf_protect
def cashier_walkin(request):
    services = Service.objects.filter(is_active=True)
    staff_members = Staff.objects.filter(availability='available').select_related('user')
    
    if request.method == 'POST':
        form = WalkInForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            service = cd['service']
            customer_name = cd['customer_name']
            customer_phone = cd.get('customer_phone', '')
            customer_email = cd.get('customer_email', '')
            staff_member = cd.get('staff')
            
            username = generate_walkin_username(customer_name)
            user = User.objects.create(
                username=username,
                first_name=customer_name or 'Walk-in',
                email=customer_email,
            )
            
            appointment = Appointment.objects.create(
                user=user,
                service=service,
                date=timezone.now().date(),
                time=timezone.now().time().replace(second=0, microsecond=0),
                status='completed',
                notes=f"Walk-in customer: {customer_name}, Phone: {customer_phone}",
            )
            
            if staff_member:
                appointment.staff = staff_member.user
                appointment.save()
            
            payment = Payment.objects.create(
                appointment=appointment,
                amount=service.price,
                payment_method='cash',
                payment_status='paid',
                received_by=request.user,
                payment_date=timezone.now(),
                notes=f"Walk-in cash payment by {customer_name}",
            )
            payment.mark_as_paid(received_by=request.user)
            send_payment_confirmation(appointment)
            
            messages.success(request, f'Walk-in appointment created for {customer_name or "customer"}. Payment of Ksh {service.price} recorded.')
            return redirect('cashier_receipt', pk=payment.pk)
    else:
        form = WalkInForm()
    
    return render(request, 'salon/cashier/walkin.html', {
        'services': services,
        'staff_members': staff_members,
        'form': form,
    })


@login_required
@user_passes_test(is_cashier)
def process_payment(request, pk):
    appointment = get_object_or_404(Appointment, pk=pk)
    
    if appointment.payment_status == 'paid':
        messages.warning(request, 'Appointment already paid.')
        return redirect('cashier_dashboard')
    
    if request.method == 'POST':
        form = ProcessPaymentForm(request.POST)
        if form.is_valid():
            payment = Payment.objects.create(
                appointment=appointment,
                amount=appointment.service.price,
                payment_method='cash',
                received_by=request.user,
                notes=form.cleaned_data.get('notes', ''),
            )
            payment.mark_as_paid(received_by=request.user)
            send_payment_confirmation(appointment)
            messages.success(request, f'Cash payment of Ksh {appointment.service.price} recorded successfully.')
            return redirect('cashier_receipt', pk=payment.pk)
    else:
        form = ProcessPaymentForm()
    
    return render(request, 'salon/cashier/process_payment.html', {
        'appointment': appointment,
        'form': form,
    })


@login_required
@user_passes_test(is_cashier)
def cashier_receipt(request, pk):
    """Display receipt after successful payment"""
    payment = get_object_or_404(Payment, pk=pk, payment_status='paid')
    return render(request, 'salon/cashier/receipt.html', {
        'payment': payment,
        'appointment': payment.appointment,
    })


@login_required
@user_passes_test(is_cashier)
def cashier_payment_history(request):
    """Payment history with filters and export"""
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    method = request.GET.get('method', '')
    customer = request.GET.get('customer', '')

    payments = Payment.objects.filter(payment_status='paid').select_related(
        'appointment__user', 'appointment__service', 'appointment__assigned_staff__user'
    )

    if date_from:
        payments = payments.filter(payment_date__date__gte=date_from)
    if date_to:
        payments = payments.filter(payment_date__date__lte=date_to)
    if method:
        payments = payments.filter(payment_method=method)
    if customer:
        payments = payments.filter(
            Q(appointment__user__first_name__icontains=customer) |
            Q(appointment__user__last_name__icontains=customer) |
            Q(appointment__user__username__icontains=customer)
        )

    payments = payments.order_by('-payment_date')

    # Export handling
    if request.GET.get('export') == 'csv':
        import csv
        from django.http import HttpResponse
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="payment_history.csv"'
        writer = csv.writer(response)
        writer.writerow(['Receipt #', 'Customer', 'Service', 'Staff', 'Amount', 'Method', 'Transaction', 'Date'])
        for p in payments:
            staff_name = ''
            if p.appointment.assigned_staff:
                staff_name = p.appointment.assigned_staff.user.get_full_name()
            writer.writerow([
                p.receipt_number or '',
                p.appointment.user.get_full_name() or p.appointment.user.username,
                p.appointment.service.name,
                staff_name,
                p.amount,
                p.get_payment_method_display(),
                p.transaction_code or '',
                p.payment_date.strftime('%Y-%m-%d %H:%M') if p.payment_date else '',
            ])
        return response

    total_amount = payments.aggregate(total=Sum('amount'))['total'] or 0
    paginator = Paginator(payments, 15)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    return render(request, 'salon/cashier/payment_history.html', {
        'payments': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'total_amount': total_amount,
        'date_from': date_from,
        'date_to': date_to,
        'method_filter': method,
        'customer_search': customer,
    })


# ============ PAYMENT MANAGEMENT VIEWS ============

@login_required
@user_passes_test(is_admin)
def admin_payments(request):
    status_filter = request.GET.get('status', '')
    method_filter = request.GET.get('method', '')
    
    payments = Payment.objects.select_related(
        'appointment__user', 'appointment__service'
    ).all()
    
    if status_filter:
        payments = payments.filter(payment_status=status_filter)
    if method_filter:
        payments = payments.filter(payment_method=method_filter)
    
    payments = payments.order_by('-created_at')
    
    total_paid = payments.filter(payment_status='paid').aggregate(Sum('amount'))['amount__sum'] or 0
    total_pending = payments.filter(payment_status='pending').aggregate(Sum('amount'))['amount__sum'] or 0

    paginator = Paginator(payments, 15)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'salon/admin/payments.html', {
        'payments': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'total_paid': total_paid,
        'total_pending': total_pending,
        'status_filter': status_filter,
        'method_filter': method_filter,
    })


# ============ EXPENSE MANAGEMENT VIEWS ============

@login_required
@user_passes_test(is_admin)
def admin_expenses(request):
    category_filter = request.GET.get('category', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    expenses = Expense.objects.all()
    
    if category_filter:
        expenses = expenses.filter(category=category_filter)
    if date_from:
        expenses = expenses.filter(date__gte=date_from)
    if date_to:
        expenses = expenses.filter(date__lte=date_to)
    
    expenses = expenses.order_by('-date', '-created_at')
    
    total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or 0

    paginator = Paginator(expenses, 15)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'salon/admin/expenses.html', {
        'expenses': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'total_expenses': total_expenses,
        'category_filter': category_filter,
        'date_from': date_from,
        'date_to': date_to,
        'expense_categories': Expense.CATEGORY_CHOICES,
    })


@login_required
@user_passes_test(is_admin)
@csrf_protect
def add_expense(request):
    if request.method == 'POST':
        form = ExpenseForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Expense recorded successfully.')
            return redirect('admin_expenses')
    else:
        form = ExpenseForm()
    
    return render(request, 'salon/admin/add_expense.html', {'form': form})


@login_required
@user_passes_test(is_admin)
@csrf_protect
def edit_expense(request, pk):
    expense = get_object_or_404(Expense, pk=pk)
    if request.method == 'POST':
        form = ExpenseForm(request.POST, instance=expense)
        if form.is_valid():
            form.save()
            messages.success(request, 'Expense updated successfully.')
            return redirect('admin_expenses')
    else:
        form = ExpenseForm(instance=expense)
    
    return render(request, 'salon/admin/edit_expense.html', {'form': form, 'expense': expense})


@login_required
@user_passes_test(is_admin)
def delete_expense(request, pk):
    expense = get_object_or_404(Expense, pk=pk)
    expense.delete()
    messages.success(request, 'Expense deleted successfully.')
    return redirect('admin_expenses')


# ============ FINANCE DASHBOARD ============

@login_required
@user_passes_test(is_admin)
def finance_dashboard(request):
    from django.db.models.functions import TruncMonth
    
    today = timezone.now().date()
    first_of_month = today.replace(day=1)
    
    # Revenue
    monthly_revenue = Payment.objects.filter(
        payment_status='paid',
        payment_date__date__gte=first_of_month,
        payment_date__date__lte=today
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    total_revenue = Payment.objects.filter(
        payment_status='paid'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Revenue by method
    cash_revenue = Payment.objects.filter(
        payment_status='paid', payment_method='cash'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    pending_payments = Payment.objects.filter(
        payment_status='pending'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Expenses
    monthly_expenses = Expense.objects.filter(
        date__gte=first_of_month, date__lte=today
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    total_expenses = Expense.objects.aggregate(total=Sum('amount'))['total'] or 0
    
    # Profit/Loss
    monthly_profit = monthly_revenue - monthly_expenses
    total_profit = total_revenue - total_expenses
    
    # Monthly chart data
    monthly_data = Payment.objects.filter(
        payment_status='paid'
    ).annotate(
        month=TruncMonth('payment_date')
    ).values('month').annotate(
        revenue=Sum('amount')
    ).order_by('month')[:12]
    
    import calendar
    months = []
    revenue_data = []
    expense_data_list = []
    
    for i in range(11, -1, -1):
        m = today.month - i
        y = today.year
        while m < 1:
            m += 12
            y -= 1
        while m > 12:
            m -= 12
            y += 1
        months.append(calendar.month_abbr[m])
        
        rev = sum(d['revenue'] for d in monthly_data if d['month'] and d['month'].month == m and d['month'].year == y)
        exp = Expense.objects.filter(date__year=y, date__month=m).aggregate(total=Sum('amount'))['total'] or 0
        revenue_data.append(float(rev))
        expense_data_list.append(float(exp))
    
    # Expense breakdown
    expense_breakdown = Expense.objects.values('category').annotate(
        total=Sum('amount')
    ).order_by('-total')
    
    # Revenue by service category
    revenue_by_category_raw = Payment.objects.filter(
        payment_status='paid'
    ).values(
        'appointment__service__category'
    ).annotate(
        total=Sum('amount')
    ).order_by('-total')
    category_labels = dict(Service.CATEGORY_CHOICES)
    revenue_by_category = [
        {'label': category_labels.get(r['appointment__service__category'], r['appointment__service__category']), 'total': r['total']}
        for r in revenue_by_category_raw
    ]

    # Recent transactions
    recent_payments = Payment.objects.filter(
        payment_status='paid'
    ).select_related('appointment__user', 'appointment__service').order_by('-payment_date')[:10]
    
    return render(request, 'salon/admin/finance.html', {
        'monthly_revenue': monthly_revenue,
        'total_revenue': total_revenue,
        'cash_revenue': cash_revenue,
        'pending_payments': pending_payments,
        'monthly_expenses': monthly_expenses,
        'total_expenses': total_expenses,
        'monthly_profit': monthly_profit,
        'total_profit': total_profit,
        'months': json.dumps(months),
        'revenue_data': json.dumps(revenue_data),
        'expense_data': json.dumps(expense_data_list),
        'expense_breakdown': expense_breakdown,
        'revenue_by_category': revenue_by_category,
        'recent_payments': recent_payments,
    })



# # ============ M-PESA DARAJA INTEGRATION (DISABLED) ============
# 
# 
# def format_mpesa_phone(phone):
#     """Convert phone number to 254 format for M-Pesa"""
#     if not phone:
#         return None
#     cleaned = ''.join(filter(str.isdigit, phone))
#     if cleaned.startswith('0') and len(cleaned) == 10:
#         return '254' + cleaned[1:]
#     elif cleaned.startswith('254') and len(cleaned) == 12:
#         return cleaned
#     elif len(cleaned) == 9:
#         return '254' + cleaned
#     return None
# 
# 
# def get_mpesa_token():
#     """
#     Generate M-Pesa access token using consumer key/secret.
#     Returns (token, error_message) tuple.
#     On success: token is str, error_message is None.
#     On failure: token is None, error_message describes the issue.
#     """
#     consumer_key = settings.MPESA_CONSUMER_KEY
#     consumer_secret = settings.MPESA_CONSUMER_SECRET
#     
#     # Validate credentials exist
#     if not consumer_key or consumer_key == 'your-consumer-key':
#         error_msg = "M-Pesa consumer key not configured in .env"
#         logger.error(error_msg)
#         return None, error_msg
#     if not consumer_secret or consumer_secret == 'your-consumer-secret':
#         error_msg = "M-Pesa consumer secret not configured in .env"
#         logger.error(error_msg)
#         return None, error_msg
#     
#     auth_string = f"{consumer_key}:{consumer_secret}"
#     encoded_auth = base64.b64encode(auth_string.encode()).decode()
#     
#     env = getattr(settings, 'MPESA_ENV', 'sandbox')
#     if env == 'production':
#         url = 'https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'
#     else:
#         url = 'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'
#     
#     logger.info(f"Requesting M-Pesa token from {env} environment")
#     
#     try:
#         response = requests.get(url, headers={'Authorization': f'Basic {encoded_auth}'}, timeout=30)
#         response.raise_for_status()
#         data = response.json()
#         token = data.get('access_token')
#         if token:
#             logger.info(f"M-Pesa token generated successfully (env: {env})")
#             return token, None
#         else:
#             error_msg = f"M-Pesa API returned no access_token. Response: {data}"
#             logger.error(error_msg)
#             return None, error_msg
#     except requests.exceptions.Timeout:
#         error_msg = "M-Pesa token request timed out (API unreachable)"
#         logger.error(error_msg)
#         return None, error_msg
#     except requests.exceptions.RequestException as e:
#         status = ''
#         body = ''
#         if hasattr(e, 'response') and e.response is not None:
#             status = f" (HTTP {e.response.status_code})"
#             body = f": {e.response.text[:200]}"
#         error_msg = f"M-Pesa token request failed{status}{body}"
#         logger.error(f"M-Pesa token generation request failed: {e}")
#         logger.error(f"Response status: {e.response.status_code if hasattr(e, 'response') and e.response is not None else 'N/A'}")
#         logger.error(f"Response body: {e.response.text[:200] if hasattr(e, 'response') and e.response is not None else 'N/A'}")
#         return None, error_msg
#     except Exception as e:
#         error_msg = f"M-Pesa token generation error: {e}"
#         logger.error(error_msg)
#         return None, error_msg
# 
# 
# def mpesa_stk_push(phone_number, amount, account_reference, transaction_desc):
#     """
#     Initiate M-Pesa STK Push payment using Daraja API.
#     """
#     logger.info(f"STK Push initiated: Phone={phone_number}, Amount={amount}, Ref={account_reference}")
#     
#     consumer_key = getattr(settings, 'MPESA_CONSUMER_KEY', '')
#     consumer_secret = getattr(settings, 'MPESA_CONSUMER_SECRET', '')
#     
#     # Validate credentials
#     if not consumer_key or consumer_key == 'your-consumer-key':
#         logger.error("M-Pesa consumer key not configured")
#         return {'success': False, 'error': 'M-Pesa consumer key not configured'}
#     
#     if not consumer_secret or consumer_secret == 'your-consumer-secret':
#         logger.error("M-Pesa consumer secret not configured")
#         return {'success': False, 'error': 'M-Pesa consumer secret not configured'}
#     
#     # Get access token
#     token, token_error = get_mpesa_token()
#     if not token:
#         logger.error(f"Failed to obtain M-Pesa access token: {token_error}")
#         return {'success': False, 'error': token_error}
#     
#     shortcode = getattr(settings, 'MPESA_SHORTCODE', '174379')
#     passkey = getattr(settings, 'MPESA_PASSKEY', '')
#     
#     # Validate passkey
#     if not passkey:
#         logger.error("MPESA_PASSKEY not configured - password generation will fail")
#         logger.error(f"  settings.MPESA_PASSKEY: type={type(settings.MPESA_PASSKEY).__name__}, len={len(str(settings.MPESA_PASSKEY))}")
#         logger.error(f"  settings.MPESA_CONSUMER_KEY PRESENT: {bool(settings.MPESA_CONSUMER_KEY)}")
#         logger.error(f"  settings.MPESA_CONSUMER_SECRET PRESENT: {bool(settings.MPESA_CONSUMER_SECRET)}")
#         return {'success': False, 'error': 'MPESA_PASSKEY not configured'}
#     
#     timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
#     
#     # Generate password
#     password_str = f"{shortcode}{passkey}{timestamp}"
#     password = base64.b64encode(password_str.encode()).decode()
#     logger.info(f"Password generated: shortcode={shortcode}, timestamp={timestamp}")
#     
#     # Get callback URL
#     callback_url = getattr(settings, 'MPESA_CALLBACK_URL', '')
#     if not callback_url or 'your-ngrok-url' in callback_url:
#         logger.error(f"MPESA_CALLBACK_URL not properly configured: {callback_url}")
#         return {'success': False, 'error': 'MPESA_CALLBACK_URL not properly configured'}
#     
#     payload = {
#         "BusinessShortCode": shortcode,
#         "Password": password,
#         "Timestamp": timestamp,
#         "TransactionType": "CustomerPayBillOnline",
#         "Amount": int(amount),
#         "PartyA": phone_number,
#         "PartyB": shortcode,
#         "PhoneNumber": phone_number,
#         "CallBackURL": callback_url,
#         "AccountReference": account_reference[:12] if account_reference else "GlowHub",
#         "TransactionDesc": transaction_desc[:13] if transaction_desc else "Payment"
#     }
#     
#     logger.info(f"STK Push payload prepared: Amount={payload['Amount']}, Phone={payload['PhoneNumber']}, Callback={callback_url}")
#     
#     env = getattr(settings, 'MPESA_ENV', 'sandbox')
#     api_url = 'https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest' if env == 'production' \
#         else 'https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest'
#     
#     logger.info(f"Sending STK Push to: {api_url}")
#     
#     try:
#         response = requests.post(
#             api_url,
#             json=payload,
#             headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
#             timeout=30
#         )
#         response.raise_for_status()
#         result = response.json()
#         result['success'] = result.get('ResponseCode') == '0'
#         
#         if result['success']:
#             logger.info(f"STK Push successful: {result.get('CheckoutRequestID')}")
#         else:
#             logger.warning(f"STK Push failed: {result.get('ResponseDescription')}")
#         
#         return result
#     except requests.exceptions.Timeout:
#         logger.error("M-Pesa STK Push request timed out (30s)")
#         return {'success': False, 'error': 'STK Push request timed out. Please try again.'}
#     except requests.exceptions.RequestException as e:
#         logger.error(f"M-Pesa STK Push request failed: {e}")
#         if hasattr(e, 'response') and e.response is not None:
#             logger.error(f"Response status: {e.response.status_code}")
#             logger.error(f"Response body: {e.response.text[:500]}")
#         return {'success': False, 'error': f'STK Push request failed: {str(e)}'}
#     except Exception as e:
#         logger.error(f"M-Pesa STK Push error: {e}")
#         return {'success': False, 'error': f'Error: {str(e)}'}
# 
# 
# @csrf_exempt
# def mpesa_callback(request):
#     """
#     M-Pesa API callback endpoint.
#     Safaricom sends the STK Push result here as a POST request.
#     """
#     if request.method != 'POST':
#         return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Method not allowed'}, status=405)
#     
#     try:
#         data = json.loads(request.body.decode('utf-8'))
#         logger.info(f"M-Pesa callback received: {json.dumps(data)[:500]}")
#         
#         body = data.get('Body', {})
#         stk_callback = body.get('stkCallback', {})
#         checkout_request_id = stk_callback.get('CheckoutRequestID', '')
#         result_code = stk_callback.get('ResultCode', 1)
#         result_desc = stk_callback.get('ResultDesc', '')
#         
#         if not checkout_request_id:
#             return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Missing CheckoutRequestID'})
#         
#         try:
#             payment = Payment.objects.get(checkout_request_id=checkout_request_id)
#         except Payment.DoesNotExist:
#             logger.error(f"No payment found for CheckoutRequestID: {checkout_request_id}")
#             return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Payment not found'})
#         
#         if result_code == 0:
#             metadata = stk_callback.get('CallbackMetadata', {}).get('Item', [])
#             mpesa_receipt = ''
#             transaction_date = ''
#             phone_number = ''
#             amount = 0
#             
#             for item in metadata:
#                 name = item.get('Name', '')
#                 value = item.get('Value', '')
#                 if name == 'MpesaReceiptNumber':
#                     mpesa_receipt = str(value)
#                 elif name == 'TransactionDate':
#                     transaction_date = str(value)
#                 elif name == 'PhoneNumber':
#                     phone_number = str(value)
#                 elif name == 'Amount':
#                     amount = value
#             
#             payment.mpesa_receipt_number = mpesa_receipt
#             payment.transaction_date = transaction_date
#             payment.transaction_code = mpesa_receipt
#             payment.mark_as_paid()
#             
#             send_payment_confirmation(payment.appointment)
#             logger.info(f"Payment {payment.id} marked as paid via M-Pesa callback. Receipt: {mpesa_receipt}")
#         else:
#             payment.payment_status = 'failed'
#             payment.failure_reason = result_desc
#             payment.save()
#             logger.warning(f"M-Pesa payment failed for {checkout_request_id}: {result_desc}")
#         
#         return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Success'})
#     
#     except json.JSONDecodeError:
#         logger.error("M-Pesa callback: Invalid JSON payload")
#         return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Invalid JSON'}, status=400)
#     except Exception as e:
#         logger.error(f"M-Pesa callback error: {e}")
#         return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Internal error'}, status=500)


# ============ EXPORT FINANCE DATA ============

@login_required
@user_passes_test(is_admin)
def export_finance_csv(request):
    from django.http import HttpResponse
    
    report_type = request.GET.get('type', 'payments')
    
    if report_type == 'payments':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="payments.csv"'
        writer = csv.writer(response)
        writer.writerow(['ID', 'Customer', 'Service', 'Amount', 'Method', 'Status', 'Transaction Code', 'Date'])
        payments = Payment.objects.select_related('appointment__user', 'appointment__service').all()
        for p in payments:
            writer.writerow([
                p.id, p.appointment.user.username, p.appointment.service.name,
                p.amount, p.get_payment_method_display(), p.get_payment_status_display(),
                p.transaction_code or '', p.payment_date or ''
            ])
        return response
    
    elif report_type == 'expenses':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="expenses.csv"'
        writer = csv.writer(response)
        writer.writerow(['ID', 'Title', 'Category', 'Amount', 'Description', 'Date'])
        expenses = Expense.objects.all()
        for e in expenses:
            writer.writerow([e.id, e.title, e.get_category_display(), e.amount, e.description or '', e.date])
        return response
    
    elif report_type == 'finance':
        # Combined financial summary
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="finance_summary.csv"'
        writer = csv.writer(response)
        writer.writerow(['Metric', 'Value'])
        
        total_rev = Payment.objects.filter(payment_status='paid').aggregate(total=Sum('amount'))['total'] or 0
        total_exp = Expense.objects.aggregate(total=Sum('amount'))['total'] or 0
        
        writer.writerow(['Total Revenue', total_rev])
        writer.writerow(['Total Expenses', total_exp])
        writer.writerow(['Net Profit', total_rev - total_exp])
        writer.writerow([])
        writer.writerow(['Expense Category', 'Amount'])
        for cat in Expense.objects.values('category').annotate(total=Sum('amount')).order_by('-total'):
            writer.writerow([dict(Expense.CATEGORY_CHOICES).get(cat['category'], cat['category']), cat['total']])
        
        return response
    
    return redirect('finance_dashboard')
