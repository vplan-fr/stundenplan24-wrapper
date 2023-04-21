from .client import (
    Stundenplan24Client,
    Stundenplan24Credentials,
    Endpoints
)


def parse_creds_json(json_str: str) -> tuple[int, Stundenplan24Credentials]:
    import json

    out = json.loads(json_str)

    school_number = int(out["school_number"])
    credentials = Stundenplan24Credentials(
        out["user_name"],
        out["password"]
    )

    return school_number, credentials
