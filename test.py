import asyncio
import datetime
from pathlib import Path
import xml.etree.ElementTree as ET

from stundenplan24_py import *


async def main():
    with open("creds.json") as f:
        school_nr, creds = parse_creds_json(f.read())

    client = Stundenplan24Client(school_nr, creds)

    async def get(date):
        data = await client.fetch_indiware_mobil(date)

        return Result(
            data=data,
            timestamp=indiware_mobil.FormPlan.from_xml(ET.fromstring(data)).timestamp
        )

    # noinspection PyTypeChecker
    crawler = Crawler(Path("cache"), get)
    await crawler.update_days()

    async for revision in crawler.get(datetime.date.today()):
        print(revision.data)
        print(revision.timestamp)
        print(revision.from_cache)


if __name__ == '__main__':
    asyncio.run(main())
