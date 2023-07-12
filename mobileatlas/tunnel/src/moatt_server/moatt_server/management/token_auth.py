import re

# TODO require token as decorator
# def require_token(func):
#     """Make sure token exists in headers"""
#     @functools.wraps(func)
#     def wrapper_require_token(*args, **kwargs):
#         if not get_token(request):
#             return "", 403
#         return func(*args, **kwargs)
#     return wrapper_require_token()


def get_token(request):
    try:
        token = request.headers.get("Authorization").split(" ")[1]
        if not re.match("[a-zA-Z0-9]{32}$", token):
            return None
        return token
    except (IndexError, AttributeError):
        return None
