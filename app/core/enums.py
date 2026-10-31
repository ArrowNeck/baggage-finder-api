import enum


class Status(enum.StrEnum):
    active = "active"
    lost = "lost"
    recovered = "recovered"


class Category(enum.StrEnum):
    general = "general"
    luggage = "luggage"
    cargo = "cargo"
    camera = "camera"
    other = "other"
