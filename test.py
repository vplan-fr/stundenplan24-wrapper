import asyncio
import xml.etree.ElementTree

import aiohttp

from stundeplan24_py import *
from stundeplan24_py import vp_mobil


async def main():
    with open("creds.json") as f:
        school_nr, creds = parse_creds_json(f.read())

    client = Stundenplan24Client(school_nr, creds)

    async with aiohttp.ClientSession() as session:
        vpmobile_xml = await client.fetch_indiware_mobile(session)

    day = vp_mobil.Day.from_xml(xml.etree.ElementTree.fromstring(vpmobile_xml))

    breakpoint()


if __name__ == '__main__':
    asyncio.run(main())
