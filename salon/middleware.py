from django.utils import timezone
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse
from datetime import timedelta

class AdminSessionTimeoutMiddleware:
    """
    Middleware to enforce admin session timeout.
    Admin users are logged out after 15 minutes of inactivity.
    """
    ADMIN_IDLE_TIMEOUT = 900  # 15 minutes in seconds
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if request.user.is_authenticated and request.user.is_staff:
            last_activity = request.session.get('_admin_last_activity')
            now = timezone.now().timestamp()
            
            if last_activity is None:
                request.session['_admin_last_activity'] = now
            else:
                elapsed = now - last_activity
                if elapsed > self.ADMIN_IDLE_TIMEOUT:
                    # Session expired, log out the admin
                    from django.contrib.auth import logout
                    logout(request)
                    messages.warning(request, 'Your admin session has expired for security. Please log in again.')
                    return redirect(reverse('login'))
                else:
                    # Update last activity time
                    request.session['_admin_last_activity'] = now
        
        response = self.get_response(request)
        return response
