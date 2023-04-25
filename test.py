import asyncio
import datetime
from pathlib import Path

from stundenplan24_py import *


async def main():
    with open("creds.json") as f:
        school_nr, creds = parse_creds_json(f.read())

    client = Stundenplan24Client(school_nr, creds)

    crawler = IndiwareMobilCrawler(client, Path("cache"))

    await crawler.update_days()

    async for revision in crawler.get(datetime.date.today()):
        print(revision.data)
        print(revision.timestamp)


if __name__ == '__main__':
    asyncio.run(main())
