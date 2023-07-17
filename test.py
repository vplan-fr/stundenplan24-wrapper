import asyncio
import datetime
from pathlib import Path

from stundenplan24_py import *


def parse_creds_json(json_str: str) -> tuple[str, Credentials]:
    import json

    out = json.loads(json_str)

    school_number = out["school_number"]
    credentials = Credentials(
        out["username"],
        out["password"]
    )

    return school_number, credentials


async def main():
    with open("creds.json") as f:
        school_nr, creds = parse_creds_json(f.read())

    endpoints = Stundenplan24StudentsEndpointCollection(school_nr)

    client = IndiwareStundenplanerClient(endpoints, creds)

    crawler = IndiwareMobilCrawler(client, Path("cache"))

    await crawler.update_days()

    for result in crawler.all():
        # print(result.data)
        print(result.timestamp)


if __name__ == '__main__':
    asyncio.run(main())
