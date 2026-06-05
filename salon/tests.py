from datetime import time, timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import AppointmentForm, RescheduleForm
from .models import Appointment, Service, Staff
from .utils import get_available_slots


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


    def test_available_slots_hide_duration_overlaps_for_selected_service(self):
        Appointment.objects.create(
            user=self.user,
            service=self.long_service,
            date=self.booking_date,
            time=time(9, 0),
            status='approved',
        )

        slots = get_available_slots(self.booking_date, service=self.short_service)
        availability = {slot['time']: slot['available'] for slot in slots}

        self.assertFalse(availability['09:00'])
        self.assertFalse(availability['09:30'])
        self.assertFalse(availability['10:00'])
        self.assertFalse(availability['10:30'])
        self.assertTrue(availability['11:00'])

    def test_available_slots_prevent_candidate_service_from_running_into_existing_booking(self):
        Appointment.objects.create(
            user=self.user,
            service=self.short_service,
            date=self.booking_date,
            time=time(10, 0),
            status='approved',
        )

        slots = get_available_slots(self.booking_date, service=self.long_service)
        availability = {slot['time']: slot['available'] for slot in slots}

        self.assertFalse(availability['09:00'])
        self.assertFalse(availability['09:30'])
        self.assertFalse(availability['10:00'])
        self.assertTrue(availability['10:30'])

    def test_get_slots_endpoint_uses_selected_service_duration(self):
        self.client.force_login(self.user)
        Appointment.objects.create(
            user=self.other_user,
            service=self.long_service,
            date=self.booking_date,
            time=time(9, 0),
            status='approved',
        )

        response = self.client.get(reverse('get_slots'), {
            'date': self.booking_date.isoformat(),
            'service': self.short_service.pk,
        })

        self.assertEqual(response.status_code, 200)
        availability = {slot['time']: slot['available'] for slot in response.json()['slots']}
        self.assertFalse(availability['09:30'])
        self.assertFalse(availability['10:00'])
        self.assertTrue(availability['11:00'])

    def test_get_slots_endpoint_can_exclude_rescheduled_appointment(self):
        self.client.force_login(self.user)
        appointment = Appointment.objects.create(
            user=self.user,
            service=self.short_service,
            date=self.booking_date,
            time=time(9, 0),
            status='approved',
        )

        response = self.client.get(reverse('get_slots'), {
            'date': self.booking_date.isoformat(),
            'service': self.short_service.pk,
            'appointment': appointment.pk,
        })

        self.assertEqual(response.status_code, 200)
        availability = {slot['time']: slot['available'] for slot in response.json()['slots']}
        self.assertTrue(availability['09:00'])

class AdminStaffAssignmentValidationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='password123',
            is_staff=True,
        )
        self.customer = User.objects.create_user(
            username='booking_customer',
            email='booking@example.com',
            password='password123',
        )
        self.other_customer = User.objects.create_user(
            username='other_booking_customer',
            email='otherbooking@example.com',
            password='password123',
        )
        self.hair_service = Service.objects.create(
            name='Hair Styling',
            description='Hair service',
            price=2000,
            duration=60,
            category='hair',
            is_active=True,
        )
        self.short_hair_service = Service.objects.create(
            name='Short Hair Service',
            description='Short hair service',
            price=1000,
            duration=30,
            category='hair',
            is_active=True,
        )
        self.booking_date = timezone.now().date() + timedelta(days=1)
        self.hair_staff_user = User.objects.create_user(
            username='hair_staff',
            email='hairstaff@example.com',
            password='password123',
            is_staff=True,
        )
        self.hair_staff = Staff.objects.create(
            user=self.hair_staff_user,
            role='hair_stylist',
            availability='available',
        )

    def make_appointment(self, service=None, appointment_time=time(9, 0), user=None, status='approved'):
        return Appointment.objects.create(
            user=user or self.customer,
            service=service or self.hair_service,
            date=self.booking_date,
            time=appointment_time,
            status=status,
        )

    def test_admin_cannot_assign_unavailable_staff(self):
        appointment = self.make_appointment()
        self.hair_staff.availability = 'unavailable'
        self.hair_staff.save()
        self.client.force_login(self.admin)

        response = self.client.post(reverse('assign_staff', args=[appointment.pk]), {
            'staff_id': self.hair_staff.pk,
        })

        self.assertEqual(response.status_code, 302)
        appointment.refresh_from_db()
        self.assertIsNone(appointment.assigned_staff)
        self.assertIsNone(appointment.staff)

    def test_admin_cannot_assign_wrong_role_for_service_category(self):
        appointment = self.make_appointment()
        barber_user = User.objects.create_user(
            username='barber_staff',
            email='barber@example.com',
            password='password123',
            is_staff=True,
        )
        barber = Staff.objects.create(
            user=barber_user,
            role='barber',
            availability='available',
        )
        self.client.force_login(self.admin)

        response = self.client.post(reverse('assign_staff', args=[appointment.pk]), {
            'staff_id': barber.pk,
        })

        self.assertEqual(response.status_code, 302)
        appointment.refresh_from_db()
        self.assertIsNone(appointment.assigned_staff)
        self.assertIsNone(appointment.staff)

    def test_admin_cannot_double_book_same_staff_with_overlapping_appointments(self):
        existing = self.make_appointment(appointment_time=time(9, 0), user=self.customer)
        existing.assigned_staff = self.hair_staff
        existing.staff = self.hair_staff.user
        existing.save()
        overlapping = self.make_appointment(appointment_time=time(9, 30), user=self.other_customer)
        self.client.force_login(self.admin)

        response = self.client.post(reverse('assign_staff', args=[overlapping.pk]), {
            'staff_id': self.hair_staff.pk,
        })

        self.assertEqual(response.status_code, 302)
        overlapping.refresh_from_db()
        self.assertIsNone(overlapping.assigned_staff)
        self.assertIsNone(overlapping.staff)

    def test_admin_can_assign_same_staff_to_back_to_back_appointments(self):
        existing = self.make_appointment(
            service=self.short_hair_service,
            appointment_time=time(9, 0),
            user=self.customer,
        )
        existing.assigned_staff = self.hair_staff
        existing.staff = self.hair_staff.user
        existing.save()
        next_appointment = self.make_appointment(
            service=self.short_hair_service,
            appointment_time=time(9, 30),
            user=self.other_customer,
        )
        self.client.force_login(self.admin)

        response = self.client.post(reverse('assign_staff', args=[next_appointment.pk]), {
            'staff_id': self.hair_staff.pk,
        })

        self.assertEqual(response.status_code, 302)
        next_appointment.refresh_from_db()
        self.assertEqual(next_appointment.assigned_staff, self.hair_staff)
        self.assertEqual(next_appointment.staff, self.hair_staff.user)

    def test_admin_can_unassign_staff(self):
        appointment = self.make_appointment()
        appointment.assigned_staff = self.hair_staff
        appointment.staff = self.hair_staff.user
        appointment.save()
        self.client.force_login(self.admin)

        response = self.client.post(reverse('assign_staff', args=[appointment.pk]), {
            'staff_id': '',
        })

        self.assertEqual(response.status_code, 302)
        appointment.refresh_from_db()
        self.assertIsNone(appointment.assigned_staff)
        self.assertIsNone(appointment.staff)
