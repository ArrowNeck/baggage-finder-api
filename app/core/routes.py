"""Route path constants. All are mounted under settings.API_PREFIX (default "/api")."""


class AuthRoutes:
    SIGN_UP = "/signUp"
    LOGIN = "/user/login"
    LOGOUT = "/user/logout"
    REFRESH = "/user/refresh"
    RESET_REQUEST = "/user/password/reset-request"
    RESET = "/user/password/reset"


class UserRoutes:
    PASSWORD = "/user/password"
    PREFIX = "/users"
    BY_ID = "/{user_id}"
    PUSH_TEST = "/user/push-test"


class DashboardRoutes:
    PREFIX = "/dashboard"
    STATS = "/stats"


class BaggageRoutes:
    PREFIX = "/baggage"
    BY_ID = "/{baggage_id}"
    STATUS = "/{baggage_id}/status"
    EVENTS = "/{baggage_id}/events"


class PublicRoutes:
    """Unauthenticated endpoints used by the QR web page."""

    PREFIX = "/public/qr"
    BY_TOKEN = "/{token_id}"
    SCAN = "/{token_id}/scan"
    FOUND = "/{token_id}/found"


class WebRoutes:
    QR = "/qr/{token_id}"  # the page itself, served at the site root (not under API_PREFIX)
