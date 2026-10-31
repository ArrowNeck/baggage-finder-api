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


class BaggageRoutes:
    PREFIX = "/baggage"
    BY_ID = "/{baggage_id}"
    STATUS = "/{baggage_id}/status"
