from typing import Annotated

from pydantic import StringConstraints

HexColor = Annotated[
    str,
    StringConstraints(
        pattern=r"^#[0-9A-Fa-f]{6}$",
        min_length=7,
        max_length=7,
    ),
]
