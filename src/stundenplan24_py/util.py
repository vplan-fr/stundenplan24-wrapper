from pathlib import Path
import xml.etree.ElementTree as ET

from . import *


def create_indiware_mobil_crawler(client: Stundenplan24Client,
                                  cache_dir: Path,
                                  **kwargs
                                  ) -> Crawler[indiware_mobil.FormPlan]:
    async def get(date):
        data = await client.fetch_indiware_mobil(date)

        return Result(
            data=data,
            timestamp=indiware_mobil.FormPlan.from_xml(ET.fromstring(data)).timestamp
        )

    return Crawler[indiware_mobil.FormPlan](
        cache_dir, get,
        interpreter=lambda data: indiware_mobil.FormPlan.from_xml(ET.fromstring(data)),
        **kwargs
    )
