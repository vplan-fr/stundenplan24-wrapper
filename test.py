import asyncio
import xml.etree.ElementTree

import aiohttp

from stundenplan24_py import *


async def main():
    with open("creds.json") as f:
        school_nr, creds = parse_creds_json(f.read())

    client = Stundenplan24Client(school_nr, creds)

    async with aiohttp.ClientSession() as session:
        iw_mobil_xml = await client.fetch_indiware_mobil(session)

    day = vp_mobil.Day.from_xml(xml.etree.ElementTree.fromstring(iw_mobil_xml))

    breakpoint()


if __name__ == '__main__':
    asyncio.run(main())
