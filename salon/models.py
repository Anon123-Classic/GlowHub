from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import time, timedelta, datetime, date


class Staff(models.Model):
    ROLE_CHOICES = [
        ('barber', 'Barber'),
        ('hair_stylist', 'Hair Stylist'),
        ('nail_technician', 'Nail Technician'),
        ('makeup_artist', 'Makeup Artist'),
        ('beautician', 'Beautician'),
        ('spa_therapist', 'Spa Therapist'),
        ('cashier', 'Cashier'),
        ('receptionist', 'Receptionist'),
    ]

    SERVICE_CATEGORY_MAP = {
        'barber': 'barber',
        'hair_stylist': 'hair',
        'nail_technician': 'nails',
        'makeup_artist': 'makeup',
        'beautician': 'facial',
        'spa_therapist': 'spa',
    }

    SPECIALIZATION_MAP = {
        'barber': 'Haircuts, Fades, Beard Grooming, Eyebrow Shaping',
        'hair_stylist': 'Haircuts, Blow-dry, Coloring, Styling, Treatments',
        'nail_technician': 'Manicure, Pedicure, Nail Art, Gel Nails',
        'makeup_artist': 'Bridal Makeup, Evening Makeup, Airbrush, HD Makeup',
        'beautician': 'Facials, Waxing, Threading, Skin Treatments',
        'spa_therapist': 'Massage, Body Scrub, Aromatherapy, Steam Bath',
        'cashier': 'Payment Processing, Billing, POS Operations',
        'receptionist': 'Booking Management, Customer Service, Front Desk',
    }

    AVAILABILITY_CHOICES = [
        ('available', 'Available'),
        ('unavailable', 'Unavailable'),
        ('on_leave', 'On Leave'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='staff_profile')
    role = models.CharField(max_length=50, choices=ROLE_CHOICES)
    specialization = models.CharField(max_length=200, blank=True, help_text="e.g., Bridal Hair, Beard Trimming")
    phone = models.CharField(max_length=15, blank=True, null=True)
    availability = models.CharField(max_length=20, choices=AVAILABILITY_CHOICES, default='available')
    bio = models.TextField(blank=True, null=True)
    expertise_years = models.IntegerField(default=1, help_text="Years of experience")
    profile_photo = models.ImageField(upload_to='staff_photos/', blank=True, null=True)
    must_change_password = models.BooleanField(default=True, help_text="Force password change on next login")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['role', 'user__first_name']

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} ({self.get_role_display()})"

    @property
    def is_available(self):
        return self.availability == 'available'

    def get_default_specialization(self):
        return self.SPECIALIZATION_MAP.get(self.role, '')

    def get_total_appointments(self):
        return Appointment.objects.filter(assigned_staff=self).count()

    def get_completed_appointments(self):
        return Appointment.objects.filter(assigned_staff=self, status='completed').count()

    def get_today_appointments(self):
        today = timezone.now().date()
        return Appointment.objects.filter(assigned_staff=self, date=today, status__in=['pending', 'approved', 'in_progress']).count()

    def get_in_progress_appointments(self):
        return Appointment.objects.filter(assigned_staff=self, status='in_progress').count()

    def get_upcoming_appointments(self):
        today = timezone.now().date()
        return Appointment.objects.filter(assigned_staff=self, date__gt=today, status__in=['pending', 'approved']).count()

class Service(models.Model):
    CATEGORY_CHOICES = [
        ('hair', 'Hair Services'),
        ('barber', 'Barber Services'),
        ('makeup', 'Makeup Services'),
        ('nails', 'Nail Services'),
        ('facial', 'Facial & Beauty'),
        ('spa', 'Spa & Wellness'),
    ]
    
    name = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration = models.IntegerField(help_text="Duration in minutes")
    image = models.ImageField(upload_to='services/', blank=True, null=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='hair')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']

class Appointment(models.Model):
    ACTIVE_BOOKING_STATUSES = ['pending', 'approved', 'in_progress']
    BUSINESS_START = time(9, 0)
    BUSINESS_END = time(19, 0)

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('in_progress', 'In Progress'),
        ('awaiting_payment', 'Awaiting Payment'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='appointments')
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='appointments')
    staff = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='staff_appointments')
    assigned_staff = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='appointments')
    date = models.DateField()
    time = models.TimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_status = models.CharField(max_length=20, choices=[
        ('unpaid', 'Unpaid'),
        ('paid', 'Paid'),
        ('refunded', 'Refunded'),
    ], default='unpaid')
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.service.name} - {self.date}"

    @classmethod
    def get_interval(cls, appointment_date, appointment_time, service):
        if not appointment_date or not appointment_time or not service:
            return None, None
        start_dt = datetime.combine(appointment_date, appointment_time)
        end_dt = start_dt + timedelta(minutes=service.duration)
        return start_dt, end_dt

    @classmethod
    def conflicts_with_existing(cls, appointment_date, appointment_time, service, exclude_pk=None, statuses=None):
        start_dt, end_dt = cls.get_interval(appointment_date, appointment_time, service)
        if not start_dt or not end_dt:
            return False

        appointments = cls.objects.filter(
            date=appointment_date,
            status__in=statuses or cls.ACTIVE_BOOKING_STATUSES
        ).select_related('service')
        if exclude_pk:
            appointments = appointments.exclude(pk=exclude_pk)

        for appointment in appointments:
            existing_start, existing_end = cls.get_interval(
                appointment.date, appointment.time, appointment.service
            )
            if existing_start and existing_end and start_dt < existing_end and end_dt > existing_start:
                return True
        return False

    def clean(self):
        if self.date and self.date < timezone.now().date():
            raise ValidationError("Cannot book appointments in the past.")

        if self.time:
            if self.time < self.BUSINESS_START or self.time >= self.BUSINESS_END:
                raise ValidationError("Appointments must be between 9:00 AM and 7:00 PM.")

        if self.time and self.date == timezone.now().date() and self.time <= timezone.now().time():
            raise ValidationError("Cannot book appointments in the past.")

        if self.date and self.time and self.service_id:
            start_dt, end_dt = self.get_interval(self.date, self.time, self.service)
            closing_dt = datetime.combine(self.date, self.BUSINESS_END)
            if end_dt and end_dt > closing_dt:
                raise ValidationError("Appointment duration exceeds business hours.")

        # Check for maximum 2 appointments per customer per day
        if self.user and self.date:
            daily_appointments = Appointment.objects.filter(
                user=self.user, date=self.date, status__in=self.ACTIVE_BOOKING_STATUSES
            ).exclude(pk=self.pk)
            if daily_appointments.count() >= 2:
                raise ValidationError("You can only book a maximum of 2 appointments per day.")

        if self.date and self.time and self.service_id:
            if self.conflicts_with_existing(self.date, self.time, self.service, exclude_pk=self.pk):
                raise ValidationError("This time slot is already booked.")

    def cancel_allowed(self):
        if self.status == 'cancelled':
            return False
        appointment_dt = datetime.combine(self.date, self.time)
        if timezone.is_naive(appointment_dt):
            from django.utils import timezone as tz
            appointment_dt = tz.make_aware(appointment_dt)
        now = timezone.now()
        return (appointment_dt - now) >= timedelta(hours=2)

    def can_reschedule(self):
        return self.cancel_allowed() and self.status != 'cancelled'

    class Meta:
        ordering = ['-date', '-time']

class BlockedTimeSlot(models.Model):
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    reason = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.date} {self.start_time}-{self.end_time}"

class NotificationLog(models.Model):
    NOTIFICATION_TYPES = [
        ('booking_confirmation', 'Booking Confirmation'),
        ('status_update', 'Status Update'),
        ('reminder', 'Reminder'),
        ('payment_successful', 'Payment Successful'),
    ]

    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    recipient_email = models.EmailField()
    status = models.CharField(max_length=20, choices=[
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    ], default='sent')
    error_log = models.TextField(blank=True, null=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.notification_type} - {self.recipient_email} - {self.status}"

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=15, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}'s profile"

class Payment(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    appointment = models.OneToOneField(Appointment, on_delete=models.CASCADE, related_name='payment')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHOD_CHOICES, default='cash')
    receipt_number = models.CharField(max_length=50, unique=True, blank=True, null=True)
    transaction_code = models.CharField(max_length=100, blank=True, null=True, help_text="STK/Receipt/Reference number")
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments_received')
    payment_date = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    
    # M-Pesa specific fields
    phone_number = models.CharField(max_length=15, blank=True, null=True, help_text="Customer phone for M-Pesa")
    checkout_request_id = models.CharField(max_length=100, blank=True, null=True)
    merchant_request_id = models.CharField(max_length=100, blank=True, null=True)
    mpesa_receipt_number = models.CharField(max_length=50, blank=True, null=True)
    transaction_date = models.CharField(max_length=20, blank=True, null=True)
    failure_reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Payment {self.id} - {self.appointment.user.username} - {self.get_payment_status_display()}"
    
    def mark_as_paid(self, received_by=None):
        self.payment_status = 'paid'
        self.payment_date = timezone.now()
        if received_by:
            self.received_by = received_by
        if not self.receipt_number:
            self.receipt_number = f"RCP-{timezone.now().strftime('%Y%m%d')}-{self.id or 'NEW'}"
        self.save()
        self.appointment.payment_status = 'paid'
        self.appointment.status = 'completed'
        self.appointment.save(update_fields=['payment_status', 'status'])
        return self

    def save(self, *args, **kwargs):
        if not self.receipt_number and self.pk:
            self.receipt_number = f"RCP-{timezone.now().strftime('%Y%m%d')}-{self.pk}"
        super().save(*args, **kwargs)

class Expense(models.Model):
    CATEGORY_CHOICES = [
        ('rent', 'Rent'),
        ('salaries', 'Salaries'),
        ('utilities', 'Utilities'),
        ('internet', 'Internet'),
        ('hair_products', 'Hair Products'),
        ('nail_products', 'Nail Products'),
        ('makeup_products', 'Makeup Products'),
        ('cleaning_supplies', 'Cleaning Supplies'),
        ('marketing', 'Marketing'),
        ('equipment', 'Equipment'),
        ('miscellaneous', 'Miscellaneous'),
    ]
    
    title = models.CharField(max_length=200)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True, null=True)
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date', '-created_at']
    
    def __str__(self):
        return f"{self.title} - ${self.amount} ({self.get_category_display()})"
