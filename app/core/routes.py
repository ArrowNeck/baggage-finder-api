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
    PUSH_TEST = "/user/push-test"
    REALTIME_TOKEN = "/user/realtime-token"  # owner: Firebase sign-in for live updates
    PREFIX = "/users"
    BY_ID = "/{user_id}"


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
    CHAT_MESSAGES = "/{token_id}/chat/messages"  # finder side; header X-Chat-Token
    CHAT_REALTIME = "/{token_id}/chat/realtime"  # finder: Firebase sign-in for live updates


class WebRoutes:
    QR = "/qr/{token_id}"  # the page itself, served at the site root (not under API_PREFIX)


class ChatRoutes:
    """Owner side of the finder chat (authenticated)."""

    PREFIX = "/conversations"
    MESSAGES = "/{conversation_id}/messages"
    READ = "/{conversation_id}/read"
    CLOSE = "/{conversation_id}/close"
