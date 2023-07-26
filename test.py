import asyncio
import datetime
import json
from pathlib import Path
import aiohttp
import xml.etree.ElementTree as ET

from stundenplan24_py import *


async def test_hosting(hosting: Hosting, name: str, session: aiohttp.ClientSession):
    client = IndiwareStundenplanerClient(hosting, session=session)

    path = Path("_schools") / name
    path.mkdir(exist_ok=True)

    try:
        for indiware_mobil_client in client.indiware_mobil_clients:
            available_plans = await indiware_mobil_client.fetch_dates()

            for filename, timestamp in available_plans.items():
                indiware_mobil_plan = await indiware_mobil_client.fetch_plan(filename)

                print(f"> Fetched plan {filename!r}. Timestamp: {indiware_mobil_plan.last_modified!s}")
                with open(path / filename, "w") as f:
                    f.write(indiware_mobil_plan.content)

    except Exception as e:
        raise

    try:
        for substitution_plan_client in client.substitution_plan_clients:
            base_plan = substitution_plan.SubstitutionPlan.from_xml(
                ET.fromstring((await substitution_plan_client.fetch_plan()).content)
            )
            free_days = base_plan.free_days

            current_date = base_plan.date
            while True:
                current_date -= datetime.timedelta(days=1)
                while current_date in free_days or current_date.weekday() in (5, 6):
                    current_date -= datetime.timedelta(days=1)

                # substitution plan of current_date should have been uploaded, may not be available anymore
                try:
                    plan = await substitution_plan_client.fetch_plan(current_date)
                    print(f"> Fetched substitution plan. Date: {current_date!s}. Timestamp: {plan.last_modified}")

                    with open(path / substitution_plan_client.endpoint.plan_file_url2.format(date=current_date.strftime("%Y%m%d")), "w") as f:
                        f.write(plan.content)

                except PlanNotFoundError:
                    break
    except Exception as e:
        raise


async def main():
    with open("my_creds.json") as f:
        hostings = {name: Hosting.deserialize(data["hosting"]) for name, data in json.load(f).items()}

    for name, hosting in hostings.items():
        async with aiohttp.ClientSession() as session:
            await test_hosting(hosting, name, session)

            # substitution_plan_students = await client.fetch_substitution_plan_students(date)
            # substitution_plan_teachers = await client.fetch_substitution_plan_teachers(date)


if __name__ == '__main__':
    asyncio.run(main())
