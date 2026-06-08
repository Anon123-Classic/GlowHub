import re
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone
from .models import NotificationLog, Appointment
import logging

logger = logging.getLogger(__name__)


def generate_walkin_username(name):
    if not name or not name.strip():
        name = 'walkin'
    base = re.sub(r'[^a-z0-9_]', '', name.strip().lower().replace(' ', '_'))
    if not base:
        base = 'walkin'
    if not User.objects.filter(username=base).exists():
        return base
    counter = 1
    while User.objects.filter(username=f"{base}_{counter}").exists():
        counter += 1
    return f"{base}_{counter}"


def _log_notification(appointment, notification_type, recipient, status, error_log=None):
    NotificationLog.objects.create(
        appointment=appointment,
        notification_type=notification_type,
        recipient_email=recipient,
        status=status,
        error_log=error_log
    )


def send_booking_confirmation(appointment):
    subject = f"Booking Confirmation - {appointment.service.name}"
    message = f"""
Hello {appointment.user.username}, your appointment has been booked successfully.

Dear {appointment.user.first_name},

Your appointment has been booked successfully!

Service: {appointment.service.name}
Date: {appointment.date.strftime('%A, %B %d, %Y')}
Time: {appointment.time.strftime('%I:%M %p')}
Status: {appointment.get_status_display()}

Thank you for choosing GlowHub!

Best regards,
GlowHub Management
"""
    html_message = f"""
<p>Dear {appointment.user.first_name},</p>
<p>Your appointment has been booked successfully!</p>
<ul>
<li><strong>Service:</strong> {appointment.service.name}</li>
<li><strong>Date:</strong> {appointment.date.strftime('%A, %B %d, %Y')}</li>
<li><strong>Time:</strong> {appointment.time.strftime('%I:%M %p')}</li>
<li><strong>Status:</strong> {appointment.get_status_display()}</li>
</ul>
<p>Thank you for choosing GlowHub!</p>
<p>Best regards,<br>GlowHub Management</p>
"""
    recipient = appointment.user.email
    try:
        send_mail(subject, message, settings.EMAIL_HOST_USER or settings.DEFAULT_FROM_EMAIL, [recipient], html_message=html_message, fail_silently=False)
        _log_notification(appointment, 'booking_confirmation', recipient, 'sent')
    except Exception as e:
        logger.error(f"Failed to send booking confirmation: {e}")
        _log_notification(appointment, 'booking_confirmation', recipient, 'failed', str(e))


def send_status_update(appointment):
    subject = f"Appointment Status Update - {appointment.service.name}"
    message = f"""
Dear {appointment.user.first_name},

Your appointment status has been updated.

Service: {appointment.service.name}
Date: {appointment.date.strftime('%A, %B %d, %Y')}
Time: {appointment.time.strftime('%I:%M %p')}
New Status: {appointment.get_status_display()}

Thank you for choosing GlowHub!

Best regards,
GlowHub Management
"""
    html_message = f"""
<p>Dear {appointment.user.first_name},</p>
<p>Your appointment status has been updated.</p>
<ul>
<li><strong>Service:</strong> {appointment.service.name}</li>
<li><strong>Date:</strong> {appointment.date.strftime('%A, %B %d, %Y')}</li>
<li><strong>Time:</strong> {appointment.time.strftime('%I:%M %p')}</li>
<li><strong>New Status:</strong> {appointment.get_status_display()}</li>
</ul>
<p>Thank you for choosing GlowHub!</p>
<p>Best regards,<br>GlowHub Management</p>
"""
    recipient = appointment.user.email
    try:
        send_mail(subject, message, settings.EMAIL_HOST_USER or settings.DEFAULT_FROM_EMAIL, [recipient], html_message=html_message, fail_silently=False)
        _log_notification(appointment, 'status_update', recipient, 'sent')
    except Exception as e:
        logger.error(f"Failed to send status update: {e}")
        _log_notification(appointment, 'status_update', recipient, 'failed', str(e))


def send_appointment_reminder(appointment):
    subject = f"Appointment Reminder - {appointment.service.name}"
    message = f"""
Dear {appointment.user.first_name},

This is a quick reminder for your upcoming appointment.

Service: {appointment.service.name}
Date: {appointment.date.strftime('%A, %B %d, %Y')}
Time: {appointment.time.strftime('%I:%M %p')}
Status: {appointment.get_status_display()}

Please arrive on time and contact us if you need to reschedule.

Best regards,
GlowHub Management
"""
    html_message = f"""
<p>Dear {appointment.user.first_name},</p>
<p>This is a quick reminder for your upcoming appointment.</p>
<ul>
<li><strong>Service:</strong> {appointment.service.name}</li>
<li><strong>Date:</strong> {appointment.date.strftime('%A, %B %d, %Y')}</li>
<li><strong>Time:</strong> {appointment.time.strftime('%I:%M %p')}</li>
<li><strong>Status:</strong> {appointment.get_status_display()}</li>
</ul>
<p>Please arrive on time and contact us if you need to reschedule.</p>
<p>Best regards,<br>GlowHub Management</p>
"""
    recipient = appointment.user.email
    try:
        send_mail(subject, message, settings.EMAIL_HOST_USER or settings.DEFAULT_FROM_EMAIL, [recipient], html_message=html_message, fail_silently=False)
        _log_notification(appointment, 'reminder', recipient, 'sent')
    except Exception as e:
        logger.error(f"Failed to send appointment reminder: {e}")
        _log_notification(appointment, 'reminder', recipient, 'failed', str(e))


def send_payment_confirmation(appointment):
    subject = f"Payment Confirmed - {appointment.service.name}"
    message = f"""
Dear {appointment.user.first_name},

Your payment has been received successfully!

Service: {appointment.service.name}
Date: {appointment.date.strftime('%A, %B %d, %Y')}
Time: {appointment.time.strftime('%I:%M %p')}
Amount: Ksh {appointment.service.price}
Status: Paid

Thank you for choosing GlowHub!

Best regards,
GlowHub Management
"""
    html_message = f"""
<p>Dear {appointment.user.first_name},</p>
<p>Your payment has been received successfully!</p>
<ul>
<li><strong>Service:</strong> {appointment.service.name}</li>
<li><strong>Date:</strong> {appointment.date.strftime('%A, %B %d, %Y')}</li>
<li><strong>Time:</strong> {appointment.time.strftime('%I:%M %p')}</li>
<li><strong>Amount:</strong> Ksh {appointment.service.price}</li>
<li><strong>Status:</strong> Paid</li>
</ul>
<p>Thank you for choosing GlowHub!</p>
<p>Best regards,<br>GlowHub Management</p>
"""
    recipient = appointment.user.email
    try:
        send_mail(subject, message, settings.EMAIL_HOST_USER or settings.DEFAULT_FROM_EMAIL, [recipient], html_message=html_message, fail_silently=False)
        _log_notification(appointment, 'payment_successful', recipient, 'sent')
    except Exception as e:
        logger.error(f"Failed to send payment confirmation: {e}")
        _log_notification(appointment, 'payment_successful', recipient, 'failed', str(e))


def send_staff_invite_email(user, password):
    login_url = f"{settings.HOST_URL}/login/"
    subject = "Welcome to GlowHub — Your Staff Account"
    message = f"""
Hello {user.first_name},

Your staff account has been created at GlowHub.

Login credentials:
  Username: {user.username}
  Password: {password}

Login here: {login_url}

Please change your password after your first login.

Best regards,
GlowHub Management
"""
    html_message = f"""
<p>Hello {user.first_name},</p>
<p>Your staff account has been created at <strong>GlowHub</strong>.</p>
<p><strong>Login credentials:</strong></p>
<ul>
<li><strong>Username:</strong> {user.username}</li>
<li><strong>Password:</strong> {password}</li>
</ul>
<p><a href="{login_url}" style="background:#7C3AED;color:#fff;padding:10px 24px;border-radius:8px;text-decoration:none;">Login to GlowHub</a></p>
<p>Please change your password after your first login.</p>
<p>Best regards,<br>GlowHub Management</p>
"""
    try:
        send_mail(subject, message, settings.EMAIL_HOST_USER or settings.DEFAULT_FROM_EMAIL, [user.email], html_message=html_message, fail_silently=False)
        logger.info(f"Staff invite email sent to {user.email}")
    except Exception as e:
        logger.error(f"Failed to send staff invite email to {user.email}: {e}")


def get_allowed_roles_for_service(service):
    from .models import Staff

    if not service:
        return []
    return [role for role, category in Staff.SERVICE_CATEGORY_MAP.items() if category == service.category]


def staff_matches_service(staff, service):
    allowed_roles = get_allowed_roles_for_service(service)
    return not allowed_roles or staff.role in allowed_roles


def get_qualified_staff(service):
    from .models import Staff

    staff = Staff.objects.filter(availability='available').select_related('user')
    allowed_roles = get_allowed_roles_for_service(service)
    if allowed_roles:
        staff = staff.filter(role__in=allowed_roles)
    return staff


def staff_has_overlap(staff, appointment_date, appointment_time, service, exclude_appointment_id=None):
    from .models import Appointment

    appointment_start, appointment_end = Appointment.get_interval(
        appointment_date, appointment_time, service
    )
    if not appointment_start or not appointment_end:
        return False

    appointments = Appointment.objects.filter(
        assigned_staff=staff,
        date=appointment_date,
        status__in=Appointment.ACTIVE_BOOKING_STATUSES,
    ).select_related('service')
    if exclude_appointment_id:
        appointments = appointments.exclude(pk=exclude_appointment_id)

    for appointment in appointments:
        existing_start, existing_end = Appointment.get_interval(
            appointment.date, appointment.time, appointment.service
        )
        if existing_start and existing_end and appointment_start < existing_end and appointment_end > existing_start:
            return True
    return False


def get_available_staff_for_slot(service, appointment_date, appointment_time, exclude_appointment_id=None):
    return [
        staff for staff in get_qualified_staff(service)
        if not staff_has_overlap(
            staff,
            appointment_date,
            appointment_time,
            service,
            exclude_appointment_id=exclude_appointment_id,
        )
    ]


def get_available_slots(service_date, service=None, exclude_appointment_id=None):
    from datetime import time, timedelta, datetime
    from .models import Appointment, BlockedTimeSlot

    start = datetime.combine(service_date, Appointment.BUSINESS_START)
    end = datetime.combine(service_date, Appointment.BUSINESS_END)
    slots = []
    current = start

    booked = Appointment.objects.filter(
        date=service_date, status__in=Appointment.ACTIVE_BOOKING_STATUSES
    )
    if exclude_appointment_id:
        booked = booked.exclude(pk=exclude_appointment_id)
    booked_times = booked.values_list('time', flat=True)

    blocked = BlockedTimeSlot.objects.filter(date=service_date)

    while current < end:
        t = current.time()
        if service:
            _, slot_end = Appointment.get_interval(service_date, t, service)
            is_booked = (
                slot_end > end or
                Appointment.conflicts_with_existing(
                    service_date, t, service, exclude_pk=exclude_appointment_id
                )
            )
        else:
            is_booked = t in booked_times
        is_blocked = any(
            b.start_time <= t < b.end_time for b in blocked
        )
        slots.append({
            'time': t.strftime('%H:%M'),
            'display': t.strftime('%I:%M %p'),
            'available': not is_booked and not is_blocked
        })
        current += timedelta(minutes=30)

    return slots
