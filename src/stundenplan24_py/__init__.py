from .client import *
from .crawler import *

from . import (
    indiware_mobil,
    substitution_plan,
)


def parse_creds_json(json_str: str) -> tuple[int, Stundenplan24Credentials]:
    import json

    out = json.loads(json_str)

    school_number = int(out["school_number"])
    credentials = Stundenplan24Credentials(
        out["username"],
        out["password"]
    )

    return school_number, credentials
