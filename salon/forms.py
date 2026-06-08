from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import password_validation
from .models import Service, Appointment, BlockedTimeSlot, Profile, Staff, Payment, Expense
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta, time, date
import re


PHONE_REGEX = r'^\+254\d{9}$'
PHONE_ERROR = "Use format: +2547XXXXXXXX"
PHONE_PLACEHOLDER = "+2547XXXXXXXX"
PHONE_HELP_TEXT = "Example: +254712345678"


def validate_phone(value):
    if value and not re.match(PHONE_REGEX, value):
        raise ValidationError(PHONE_ERROR)


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={
        'class': 'form-control', 'placeholder': 'Enter your email'
    }))
    first_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={
        'class': 'form-control', 'placeholder': 'First name'
    }))
    last_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={
        'class': 'form-control', 'placeholder': 'Last name'
    }))
    phone = forms.CharField(
        max_length=15,
        required=False,
        help_text=PHONE_HELP_TEXT,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 'placeholder': PHONE_PLACEHOLDER
        }),
        validators=[validate_phone],
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'phone', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': 'form-control', 'placeholder': 'Choose a username'
        })
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control', 'placeholder': 'Create a password'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control', 'placeholder': 'Confirm password'
        })

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("This email is already registered.")
        return email

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise ValidationError("This username is already taken.")
        if not re.match(r'^\w+$', username):
            raise ValidationError("Username can only contain letters, numbers, and underscores.")
        return username

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise ValidationError("Passwords do not match.")
        if password1:
            try:
                password_validation.validate_password(password1)
            except ValidationError as e:
                raise ValidationError("Password is too common." if 'common' in str(e).lower() else e.messages)
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
        phone = self.cleaned_data.get('phone', '')
        Profile.objects.update_or_create(user=user, defaults={'phone': phone})
        return user


class LoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'form-control', 'placeholder': 'Username'
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control', 'placeholder': 'Password'
    }))
    remember_me = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={
        'class': 'form-check-input'
    }))

    error_messages = {
        'invalid_login': "Please enter a correct username and password. Note that both fields may be case-sensitive.",
        'inactive': "This account is inactive.",
    }


class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ['service', 'date', 'time', 'notes']
        widgets = {
            'service': forms.Select(attrs={'class': 'form-select', 'id': 'id_service'}),
            'date': forms.DateInput(attrs={
                'type': 'date', 'class': 'form-control', 'id': 'id_date', 'min': date.today().isoformat()
            }),
            'time': forms.TimeInput(attrs={'type': 'hidden', 'id': 'id_time'}),
            'notes': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3, 'placeholder': 'Any special requests?'
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        appointment_date = cleaned_data.get('date')
        appointment_time = cleaned_data.get('time')
        user = None

        if self.instance and self.instance.pk:
            user = self.instance.user
        elif hasattr(self, 'user'):
            user = self.user

        if not appointment_date:
            self.add_error('date', "This field is required.")

        if not appointment_time:
            self.add_error('time', "Please select an available time slot.")

        if appointment_date and appointment_time:
            if appointment_date < date.today():
                self.add_error('date', "Cannot book appointments in the past.")

            if appointment_time < Appointment.BUSINESS_START or appointment_time >= Appointment.BUSINESS_END:
                self.add_error('time', "Appointments must be between 9:00 AM and 7:00 PM.")

            service = cleaned_data.get('service')
            if service:
                _, appointment_end = Appointment.get_interval(appointment_date, appointment_time, service)
                closing_dt = datetime.combine(appointment_date, Appointment.BUSINESS_END)
                if appointment_end and appointment_end > closing_dt:
                    self.add_error('time', "Appointment duration exceeds business hours.")
                elif Appointment.conflicts_with_existing(
                    appointment_date, appointment_time, service, exclude_pk=self.instance.pk if self.instance.pk else None
                ):
                    self.add_error('time', "This time slot is already booked.")

            blocked = BlockedTimeSlot.objects.filter(
                date=appointment_date,
                start_time__lte=appointment_time,
                end_time__gt=appointment_time
            )
            if blocked.exists():
                self.add_error('time', "This time slot is blocked by the admin.")

        if appointment_date and user:
            daily_count = Appointment.objects.filter(
                user=user, date=appointment_date
            ).exclude(status='cancelled').exclude(pk=self.instance.pk if self.instance.pk else None).count()
            if daily_count >= 2:
                self.add_error('date', "You can only book a maximum of 2 appointments per day.")

        return cleaned_data


class RescheduleForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ['date', 'time']
        widgets = {
            'date': forms.DateInput(attrs={
                'type': 'date', 'class': 'form-control', 'min': date.today().isoformat()
            }),
            'time': forms.TimeInput(attrs={'type': 'hidden'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        appointment_date = cleaned_data.get('date')
        appointment_time = cleaned_data.get('time')

        if not appointment_date:
            self.add_error('date', "This field is required.")

        if not appointment_time:
            self.add_error('time', "Please select an available time slot.")

        if appointment_date and appointment_time:
            if appointment_date < date.today():
                self.add_error('date', "Cannot book appointments in the past.")

            if appointment_time < Appointment.BUSINESS_START or appointment_time >= Appointment.BUSINESS_END:
                self.add_error('time', "Appointments must be between 9:00 AM and 7:00 PM.")

            service = self.instance.service if self.instance and self.instance.pk else None
            if service:
                _, appointment_end = Appointment.get_interval(appointment_date, appointment_time, service)
                closing_dt = datetime.combine(appointment_date, Appointment.BUSINESS_END)
                if appointment_end and appointment_end > closing_dt:
                    self.add_error('time', "Appointment duration exceeds business hours.")
                elif Appointment.conflicts_with_existing(
                    appointment_date, appointment_time, service, exclude_pk=self.instance.pk
                ):
                    self.add_error('time', "This time slot is already booked.")

            blocked = BlockedTimeSlot.objects.filter(
                date=appointment_date,
                start_time__lte=appointment_time,
                end_time__gt=appointment_time
            )
            if blocked.exists():
                self.add_error('time', "This time slot is blocked by the admin.")

        if appointment_date and self.instance and self.instance.user:
            daily_count = Appointment.objects.filter(
                user=self.instance.user, date=appointment_date
            ).exclude(status='cancelled').exclude(pk=self.instance.pk).count()
            if daily_count >= 2:
                self.add_error('date', "You can only book a maximum of 2 appointments per day.")

        return cleaned_data


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ['name', 'description', 'price', 'duration', 'image', 'category', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Service name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Describe the service'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00', 'step': '0.01'}),
            'duration': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Minutes'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            qs = Service.objects.filter(name__iexact=name)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError("A service with this name already exists.")
        return name

    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price is not None and price <= 0:
            raise ValidationError("Price must be greater than zero.")
        return price

    def clean_duration(self):
        duration = self.cleaned_data.get('duration')
        if duration is not None and duration <= 0:
            raise ValidationError("Duration must be greater than zero.")
        if duration is not None and duration > 480:
            raise ValidationError("Duration cannot exceed 480 minutes (8 hours).")
        return duration


class BlockTimeSlotForm(forms.ModelForm):
    class Meta:
        model = BlockedTimeSlot
        fields = ['date', 'start_time', 'end_time', 'reason']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'start_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'end_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'reason': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Reason for blocking'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start_time')
        end = cleaned_data.get('end_time')

        if not start:
            self.add_error('start_time', "This field is required.")

        if not end:
            self.add_error('end_time', "This field is required.")

        if start and end:
            if end <= start:
                self.add_error('end_time', "End time must be after start time.")
            work_start = time(9, 0)
            work_end = time(19, 0)
            if start < work_start:
                self.add_error('start_time', "Must be within operating hours (9:00 AM - 7:00 PM).")
            if end > work_end:
                self.add_error('end_time', "Must be within operating hours (9:00 AM - 7:00 PM).")

        return cleaned_data


class StaffForm(forms.ModelForm):
    """Form for editing existing staff members (admin)"""

    class Meta:
        model = Staff
        fields = ['role', 'specialization', 'phone', 'availability', 'bio', 'expertise_years']
        help_texts = {
            'phone': PHONE_HELP_TEXT,
        }
        widgets = {
            'role': forms.Select(attrs={'class': 'form-select'}),
            'specialization': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Bridal Hair, Beard Trimming'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': PHONE_PLACEHOLDER}),
            'availability': forms.Select(attrs={'class': 'form-select'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Brief biography'}),
            'expertise_years': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone and not re.match(PHONE_REGEX, phone):
            raise ValidationError(PHONE_ERROR)
        return phone

    def clean_expertise_years(self):
        years = self.cleaned_data.get('expertise_years')
        if years is not None and years < 0:
            raise ValidationError("Experience cannot be negative.")
        return years


class StaffProfileForm(forms.ModelForm):
    """Form for staff to update their own profile"""

    class Meta:
        model = Staff
        fields = ['phone', 'availability', 'bio', 'profile_photo']
        help_texts = {
            'phone': PHONE_HELP_TEXT,
        }
        widgets = {
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': PHONE_PLACEHOLDER}),
            'availability': forms.Select(attrs={'class': 'form-select'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Tell us about yourself'}),
            'profile_photo': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone and not re.match(PHONE_REGEX, phone):
            raise ValidationError(PHONE_ERROR)
        return phone


class CreateStaffForm(forms.Form):
    """Form for creating new staff members"""

    first_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={
        'class': 'form-control', 'placeholder': 'First name'
    }))
    last_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={
        'class': 'form-control', 'placeholder': 'Last name'
    }))
    email = forms.EmailField(widget=forms.EmailInput(attrs={
        'class': 'form-control', 'placeholder': 'Email address'
    }))
    username = forms.CharField(max_length=100, widget=forms.TextInput(attrs={
        'class': 'form-control', 'placeholder': 'Username'
    }))
    role = forms.ChoiceField(choices=Staff.ROLE_CHOICES, widget=forms.Select(attrs={
        'class': 'form-select'
    }))
    phone = forms.CharField(
        max_length=15,
        required=False,
        help_text=PHONE_HELP_TEXT,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 'placeholder': PHONE_PLACEHOLDER
        }),
        validators=[validate_phone],
    )
    specialization = forms.CharField(max_length=200, required=False, widget=forms.TextInput(attrs={
        'class': 'form-control', 'placeholder': 'e.g., Bridal Hair'
    }))
    bio = forms.CharField(required=False, widget=forms.Textarea(attrs={
        'class': 'form-control', 'rows': 3, 'placeholder': 'Brief biography'
    }))
    expertise_years = forms.IntegerField(initial=1, widget=forms.NumberInput(attrs={
        'class': 'form-control', 'min': 0
    }))
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control', 'placeholder': 'Leave blank to auto-generate'
        }),
        help_text="Leave blank to auto-generate a random password"
    )
    confirm_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control', 'placeholder': 'Confirm password'
        })
    )
    send_invite_email = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("This email is already registered.")
        return email

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise ValidationError("This username is already taken.")
        if not re.match(r'^\w+$', username):
            raise ValidationError("Username can only contain letters, numbers, and underscores.")
        return username

    def clean_expertise_years(self):
        years = self.cleaned_data.get('expertise_years')
        if years is not None and years < 0:
            raise ValidationError("Experience cannot be negative.")
        return years

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm = cleaned_data.get('confirm_password')
        if password:
            if password != confirm:
                raise ValidationError("Passwords do not match.")
            if len(password) < 6:
                raise ValidationError("Password too short.")
        return cleaned_data


class PaymentForm(forms.ModelForm):
    """Form for recording payments"""
    class Meta:
        model = Payment
        fields = ['payment_method', 'transaction_code', 'notes']
        widgets = {
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
            'transaction_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Reference number'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Payment notes (optional)'}),
        }

    def clean_transaction_code(self):
        code = self.cleaned_data.get('transaction_code')
        if code and len(code) < 3:
            raise ValidationError("Transaction code is too short.")
        return code


class ProcessPaymentForm(forms.Form):
    """Form for processing payments"""
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
    ]

    payment_method = forms.ChoiceField(choices=PAYMENT_METHOD_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}))
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={
        'class': 'form-control', 'rows': 3, 'placeholder': 'Payment notes'
    }))


class ExpenseForm(forms.ModelForm):
    """Form for recording expenses"""
    class Meta:
        model = Expense
        fields = ['title', 'category', 'amount', 'description', 'date']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Expense title'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00', 'step': '0.01'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Expense description'}),
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is not None and amount <= 0:
            raise ValidationError("Amount must be greater than zero.")
        return amount

    def clean_title(self):
        title = self.cleaned_data.get('title')
        if title and len(title.strip()) < 2:
            raise ValidationError("Title must be at least 2 characters.")
        return title


class WalkInForm(forms.Form):
    customer_name = forms.CharField(max_length=200, widget=forms.TextInput(attrs={
        'class': 'form-control', 'placeholder': 'Customer name'
    }))
    customer_phone = forms.CharField(
        max_length=15,
        required=False,
        help_text=PHONE_HELP_TEXT,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 'placeholder': PHONE_PLACEHOLDER
        }),
        validators=[validate_phone],
    )
    customer_email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={
        'class': 'form-control', 'placeholder': 'Email address'
    }))
    service = forms.ModelChoiceField(queryset=Service.objects.filter(is_active=True), widget=forms.Select(attrs={
        'class': 'form-select'
    }))
    staff = forms.ModelChoiceField(queryset=Staff.objects.filter(availability='available'), required=False,
                                   widget=forms.Select(attrs={'class': 'form-select'}))
