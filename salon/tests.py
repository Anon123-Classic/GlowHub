from datetime import time, timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from .forms import AppointmentForm, RescheduleForm
from .models import Appointment, Service


class BookingDurationValidationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='customer',
            email='customer@example.com',
            password='password123',
        )
        self.other_user = User.objects.create_user(
            username='other_customer',
            email='other@example.com',
            password='password123',
        )
        self.short_service = Service.objects.create(
            name='Short Service',
            description='Short appointment',
            price=1000,
            duration=30,
            category='hair',
            is_active=True,
        )
        self.long_service = Service.objects.create(
            name='Long Service',
            description='Long appointment',
            price=3000,
            duration=120,
            category='hair',
            is_active=True,
        )
        self.booking_date = timezone.now().date() + timedelta(days=1)

    def test_model_rejects_overlapping_later_start_time(self):
        Appointment.objects.create(
            user=self.user,
            service=self.long_service,
            date=self.booking_date,
            time=time(9, 0),
            status='approved',
        )

        appointment = Appointment(
            user=self.other_user,
            service=self.short_service,
            date=self.booking_date,
            time=time(9, 30),
        )

        with self.assertRaisesMessage(ValidationError, 'This time slot is already booked.'):
            appointment.clean()

    def test_model_rejects_overlapping_earlier_start_time(self):
        Appointment.objects.create(
            user=self.user,
            service=self.short_service,
            date=self.booking_date,
            time=time(10, 0),
            status='approved',
        )

        appointment = Appointment(
            user=self.other_user,
            service=self.long_service,
            date=self.booking_date,
            time=time(9, 30),
        )

        with self.assertRaisesMessage(ValidationError, 'This time slot is already booked.'):
            appointment.clean()

    def test_model_allows_back_to_back_appointments(self):
        Appointment.objects.create(
            user=self.user,
            service=self.short_service,
            date=self.booking_date,
            time=time(9, 0),
            status='approved',
        )

        appointment = Appointment(
            user=self.other_user,
            service=self.short_service,
            date=self.booking_date,
            time=time(9, 30),
        )

        appointment.clean()

    def test_model_rejects_service_that_ends_after_business_hours(self):
        appointment = Appointment(
            user=self.user,
            service=self.long_service,
            date=self.booking_date,
            time=time(18, 0),
        )

        with self.assertRaisesMessage(ValidationError, 'Appointment duration exceeds business hours.'):
            appointment.clean()

    def test_appointment_form_rejects_overlapping_service_duration(self):
        Appointment.objects.create(
            user=self.user,
            service=self.long_service,
            date=self.booking_date,
            time=time(9, 0),
            status='approved',
        )

        form = AppointmentForm(data={
            'service': self.short_service.pk,
            'date': self.booking_date.isoformat(),
            'time': '09:30',
            'notes': '',
        })
        form.user = self.other_user
        form.instance.user = self.other_user

        self.assertFalse(form.is_valid())
        self.assertIn('This time slot is already booked.', form.errors['time'])

    def test_reschedule_form_rejects_duration_overlap(self):
        Appointment.objects.create(
            user=self.user,
            service=self.long_service,
            date=self.booking_date,
            time=time(9, 0),
            status='approved',
        )
        appointment = Appointment.objects.create(
            user=self.other_user,
            service=self.short_service,
            date=self.booking_date,
            time=time(12, 0),
            status='approved',
        )

        form = RescheduleForm(data={
            'date': self.booking_date.isoformat(),
            'time': '09:30',
        }, instance=appointment)

        self.assertFalse(form.is_valid())
        self.assertIn('This time slot is already booked.', form.errors['time'])

    def test_in_progress_appointments_block_overlaps(self):
        Appointment.objects.create(
            user=self.user,
            service=self.long_service,
            date=self.booking_date,
            time=time(9, 0),
            status='in_progress',
        )

        appointment = Appointment(
            user=self.other_user,
            service=self.short_service,
            date=self.booking_date,
            time=time(10, 0),
        )

        with self.assertRaisesMessage(ValidationError, 'This time slot is already booked.'):
            appointment.clean()
