from datetime import time, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .forms import AppointmentForm, RescheduleForm
from .models import Appointment, NotificationLog, Payment, Service, Staff
from .utils import (
    get_allowed_roles_for_service,
    get_available_slots,
    get_available_staff_for_slot,
    get_qualified_staff,
    staff_has_overlap,
    staff_matches_service,
)


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

class WalkInStaffAssignmentTests(TestCase):
    def setUp(self):
        self.cashier = User.objects.create_user(
            username='walkin_cashier',
            email='cashier@example.com',
            password='password123',
            is_staff=True,
        )
        self.staff_user = User.objects.create_user(
            username='walkin_staff',
            email='walkinstaff@example.com',
            password='password123',
            is_staff=True,
        )
        self.staff = Staff.objects.create(
            user=self.staff_user,
            role='hair_stylist',
            availability='available',
        )
        self.service = Service.objects.create(
            name='Walk-in Hair Service',
            description='Walk-in service',
            price=1500,
            duration=30,
            category='hair',
            is_active=True,
        )

    def create_walkin(self):
        self.client.force_login(self.cashier)
        return self.client.post(reverse('cashier_walkin'), {
            'customer_name': 'Walk In Customer',
            'customer_phone': '',
            'customer_email': 'walkin@example.com',
            'service': self.service.pk,
            'staff': self.staff.pk,
        })

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_walkin_sets_assigned_staff_and_legacy_staff(self):
        response = self.create_walkin()

        self.assertEqual(response.status_code, 302)
        appointment = Appointment.objects.get(service=self.service)
        self.assertEqual(appointment.staff, self.staff.user)
        self.assertEqual(appointment.assigned_staff, self.staff)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_walkin_appears_in_staff_completed_statistics(self):
        response = self.create_walkin()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.staff.get_completed_appointments(), 1)
        self.assertEqual(self.staff.get_total_appointments(), 1)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_walkin_is_not_counted_as_unassigned_when_staff_selected(self):
        response = self.create_walkin()

        self.assertEqual(response.status_code, 302)
        unassigned_count = Appointment.objects.filter(
            assigned_staff__isnull=True
        ).exclude(status='cancelled').count()
        self.assertEqual(unassigned_count, 0)

class StaffSchedulingHelperTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username='helper_customer',
            email='helpercustomer@example.com',
            password='password123',
        )
        self.hair_service = Service.objects.create(
            name='Helper Hair Service',
            description='Hair service',
            price=2000,
            duration=60,
            category='hair',
            is_active=True,
        )
        self.short_hair_service = Service.objects.create(
            name='Helper Short Hair Service',
            description='Short hair service',
            price=1000,
            duration=30,
            category='hair',
            is_active=True,
        )
        self.nail_service = Service.objects.create(
            name='Helper Nail Service',
            description='Nail service',
            price=1200,
            duration=30,
            category='nails',
            is_active=True,
        )
        self.booking_date = timezone.now().date() + timedelta(days=1)
        self.hair_staff_user = User.objects.create_user(
            username='helper_hair_staff',
            email='helperhair@example.com',
            password='password123',
            is_staff=True,
        )
        self.hair_staff = Staff.objects.create(
            user=self.hair_staff_user,
            role='hair_stylist',
            availability='available',
        )
        self.unavailable_hair_user = User.objects.create_user(
            username='helper_unavailable_hair_staff',
            email='helperunavailable@example.com',
            password='password123',
            is_staff=True,
        )
        self.unavailable_hair_staff = Staff.objects.create(
            user=self.unavailable_hair_user,
            role='hair_stylist',
            availability='unavailable',
        )
        self.nail_staff_user = User.objects.create_user(
            username='helper_nail_staff',
            email='helpernail@example.com',
            password='password123',
            is_staff=True,
        )
        self.nail_staff = Staff.objects.create(
            user=self.nail_staff_user,
            role='nail_technician',
            availability='available',
        )

    def test_allowed_roles_and_staff_match_service_category(self):
        self.assertEqual(get_allowed_roles_for_service(self.hair_service), ['hair_stylist'])
        self.assertTrue(staff_matches_service(self.hair_staff, self.hair_service))
        self.assertFalse(staff_matches_service(self.nail_staff, self.hair_service))

    def test_get_qualified_staff_includes_available_matching_staff_only(self):
        qualified_staff = list(get_qualified_staff(self.hair_service))

        self.assertIn(self.hair_staff, qualified_staff)
        self.assertNotIn(self.unavailable_hair_staff, qualified_staff)
        self.assertNotIn(self.nail_staff, qualified_staff)

    def test_staff_has_overlap_for_overlapping_active_assigned_appointment(self):
        Appointment.objects.create(
            user=self.customer,
            service=self.hair_service,
            assigned_staff=self.hair_staff,
            staff=self.hair_staff.user,
            date=self.booking_date,
            time=time(9, 0),
            status='approved',
        )

        self.assertTrue(staff_has_overlap(
            self.hair_staff,
            self.booking_date,
            time(9, 30),
            self.short_hair_service,
        ))

    def test_staff_has_overlap_allows_back_to_back_appointments(self):
        Appointment.objects.create(
            user=self.customer,
            service=self.short_hair_service,
            assigned_staff=self.hair_staff,
            staff=self.hair_staff.user,
            date=self.booking_date,
            time=time(9, 0),
            status='approved',
        )

        self.assertFalse(staff_has_overlap(
            self.hair_staff,
            self.booking_date,
            time(9, 30),
            self.short_hair_service,
        ))

    def test_get_available_staff_for_slot_returns_qualified_non_overlapping_staff(self):
        Appointment.objects.create(
            user=self.customer,
            service=self.hair_service,
            assigned_staff=self.hair_staff,
            staff=self.hair_staff.user,
            date=self.booking_date,
            time=time(9, 0),
            status='approved',
        )

        available_staff = get_available_staff_for_slot(
            self.hair_service,
            self.booking_date,
            time(9, 30),
        )

        self.assertNotIn(self.hair_staff, available_staff)
        self.assertNotIn(self.unavailable_hair_staff, available_staff)
        self.assertNotIn(self.nail_staff, available_staff)


class BookingNotificationQueueTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='queued_customer',
            email='queued@example.com',
            password='password123',
            first_name='Queued',
        )
        self.service = Service.objects.create(
            name='Queued Service',
            description='Service with asynchronous confirmation',
            price=1200,
            duration=30,
            category='hair',
            is_active=True,
        )
        self.booking_date = timezone.localdate() + timedelta(days=7)
        self.client.force_login(self.user)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_booking_queues_confirmation_without_sending_email(self):
        with patch('salon.utils.send_mail') as mocked_send_mail:
            response = self.client.post(reverse('book_appointment'), {
                'service': self.service.pk,
                'date': self.booking_date.isoformat(),
                'time': '10:00',
                'notes': '',
            })

        mocked_send_mail.assert_not_called()

        self.assertRedirects(
            response,
            reverse('customer_dashboard'),
            fetch_redirect_response=False,
        )
        appointment = Appointment.objects.get(user=self.user)
        notification = NotificationLog.objects.get(appointment=appointment)
        self.assertEqual(notification.status, 'pending')
        self.assertEqual(notification.notification_type, 'booking_confirmation')
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_worker_sends_queued_booking_confirmation(self):
        appointment = Appointment.objects.create(
            user=self.user,
            service=self.service,
            date=self.booking_date,
            time=time(10, 0),
        )
        notification = NotificationLog.objects.create(
            appointment=appointment,
            notification_type='booking_confirmation',
            recipient_email=self.user.email,
            status='pending',
        )

        call_command('process_notifications')

        notification.refresh_from_db()
        self.assertEqual(notification.status, 'sent')
        self.assertEqual(notification.attempts, 1)
        self.assertIsNotNone(notification.sent_at)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])


class CustomerDashboardQueryTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username='dashboard_customer',
            email='dashboard@example.com',
            password='password123',
        )
        self.staff_user = User.objects.create_user(
            username='dashboard_staff',
            email='dashboardstaff@example.com',
            password='password123',
            first_name='Dashboard Staff',
            is_staff=True,
        )
        self.service = Service.objects.create(
            name='Dashboard Service',
            description='Dashboard query test service',
            price=1500,
            duration=30,
            category='hair',
            is_active=True,
        )
        self.client.force_login(self.customer)

        statuses = ['pending', 'approved', 'completed', 'cancelled']
        for index, status in enumerate(statuses, start=1):
            Appointment.objects.create(
                user=self.customer,
                service=self.service,
                staff=self.staff_user,
                date=timezone.localdate() + timedelta(days=index),
                time=time(9 + index, 0),
                status=status,
            )

    def test_dashboard_uses_constant_query_count_with_related_objects(self):
        with self.assertNumQueries(5):
            response = self.client.get(reverse('customer_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.service.name)
        self.assertContains(response, self.staff_user.first_name)
        self.assertEqual(response.context['stats'], {
            'total': 4,
            'pending': 1,
            'approved': 1,
            'completed': 1,
            'cancelled': 1,
        })


class PaymentNotificationQueueTests(TestCase):
    def setUp(self):
        self.cashier = User.objects.create_user(
            username='payment_cashier',
            email='cashier@example.com',
            password='password123',
            is_staff=True,
        )
        self.customer = User.objects.create_user(
            username='payment_customer',
            email='paymentcustomer@example.com',
            password='password123',
            first_name='Payment Customer',
        )
        self.staff_user = User.objects.create_user(
            username='payment_staff',
            email='paymentstaff@example.com',
            password='password123',
            first_name='Payment Staff',
            is_staff=True,
        )
        self.staff = Staff.objects.create(
            user=self.staff_user,
            role='hair_stylist',
            availability='available',
        )
        self.service = Service.objects.create(
            name='Payment Service',
            description='Payment flow test service',
            price=2500,
            duration=60,
            category='hair',
            is_active=True,
        )
        self.appointment = Appointment.objects.create(
            user=self.customer,
            service=self.service,
            staff=self.staff_user,
            assigned_staff=self.staff,
            date=timezone.localdate(),
            time=time(11, 0),
            status='awaiting_payment',
            payment_status='unpaid',
        )
        self.client.force_login(self.cashier)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_process_payment_queues_notification_without_sending_email(self):
        with patch('salon.utils.send_mail') as mocked_send_mail:
            response = self.client.post(
                reverse('process_payment', args=[self.appointment.pk]),
                {'payment_method': 'cash', 'notes': 'Paid at till'},
            )

        mocked_send_mail.assert_not_called()
        payment = Payment.objects.get(appointment=self.appointment)
        self.assertRedirects(
            response,
            reverse('cashier_receipt', args=[payment.pk]),
            fetch_redirect_response=False,
        )
        payment.refresh_from_db()
        self.appointment.refresh_from_db()
        notification = NotificationLog.objects.get(
            appointment=self.appointment,
            notification_type='payment_successful',
        )
        self.assertEqual(payment.payment_status, 'paid')
        self.assertIsNotNone(payment.receipt_number)
        self.assertEqual(payment.received_by, self.cashier)
        self.assertEqual(self.appointment.payment_status, 'paid')
        self.assertEqual(self.appointment.status, 'completed')
        self.assertEqual(notification.status, 'pending')
        self.assertEqual(notification.recipient_email, self.customer.email)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_worker_sends_queued_payment_confirmation(self):
        notification = NotificationLog.objects.create(
            appointment=self.appointment,
            notification_type='payment_successful',
            recipient_email=self.customer.email,
            status='pending',
        )

        call_command('process_notifications')

        notification.refresh_from_db()
        self.assertEqual(notification.status, 'sent')
        self.assertEqual(notification.attempts, 1)
        self.assertIsNotNone(notification.sent_at)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.customer.email])
        self.assertEqual(
            mail.outbox[0].subject,
            f'Payment Confirmed - {self.service.name}',
        )
        self.assertIn('Amount: Ksh 2500', mail.outbox[0].body)

    def test_failed_payment_notification_is_retried(self):
        notification = NotificationLog.objects.create(
            appointment=self.appointment,
            notification_type='payment_successful',
            recipient_email=self.customer.email,
            status='pending',
        )

        with patch('salon.utils.send_mail', side_effect=RuntimeError('SMTP unavailable')):
            call_command('process_notifications')

        notification.refresh_from_db()
        self.assertEqual(notification.status, 'failed')
        self.assertEqual(notification.attempts, 1)
        self.assertIn('SMTP unavailable', notification.error_log)
        self.assertGreater(notification.available_at, timezone.now())

        NotificationLog.objects.filter(pk=notification.pk).update(
            available_at=timezone.now()
        )
        with patch('salon.utils.send_mail', return_value=1):
            call_command('process_notifications')

        notification.refresh_from_db()
        self.assertEqual(notification.status, 'sent')
        self.assertEqual(notification.attempts, 2)
        self.assertIsNone(notification.error_log)

    def test_already_paid_appointment_does_not_create_another_payment(self):
        payment = Payment.objects.create(
            appointment=self.appointment,
            amount=self.service.price,
            payment_method='cash',
            payment_status='paid',
            received_by=self.cashier,
            payment_date=timezone.now(),
        )
        self.appointment.payment_status = 'paid'
        self.appointment.status = 'completed'
        self.appointment.save(update_fields=['payment_status', 'status'])

        response = self.client.post(
            reverse('process_payment', args=[self.appointment.pk]),
            {'payment_method': 'cash', 'notes': ''},
        )

        self.assertRedirects(
            response,
            reverse('cashier_dashboard'),
            fetch_redirect_response=False,
        )
        self.assertEqual(Payment.objects.filter(appointment=self.appointment).count(), 1)
        self.assertEqual(Payment.objects.get(appointment=self.appointment), payment)
        self.assertFalse(NotificationLog.objects.filter(
            appointment=self.appointment,
            notification_type='payment_successful',
        ).exists())

    def test_receipt_renders_with_constant_related_object_query_count(self):
        payment = Payment.objects.create(
            appointment=self.appointment,
            amount=self.service.price,
            payment_method='cash',
            payment_status='paid',
            received_by=self.cashier,
            payment_date=timezone.now(),
        )
        payment.mark_as_paid(received_by=self.cashier)

        with self.assertNumQueries(7):
            response = self.client.get(reverse('cashier_receipt', args=[payment.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, payment.receipt_number)
        self.assertContains(response, self.customer.first_name)
        self.assertContains(response, self.service.name)
        self.assertContains(response, self.staff_user.first_name)
