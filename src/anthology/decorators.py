from django.shortcuts import redirect
from functools import wraps

def role_required(allowed_roles):
    """Restrict access to certain roles."""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            role = request.session.get('USER_ROLE')
            if role not in allowed_roles:
                return redirect('anthology:login')
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator
