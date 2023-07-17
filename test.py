import asyncio
import json
from pathlib import Path

from stundenplan24_py import *


async def main():
    with open("creds.json") as f:
        hostings = {name: Hosting.deserialize(data["hosting"]) for name, data in json.load(f).items()}

    for name, hosting in hostings.items():
        client = IndiwareStundenplanerClient(hosting)

        path = Path(name) / "_schools"
        path.mkdir(exist_ok=True)

        try:
            for filename, timestamp in (await client.form_plan_client.fetch_dates()).items():
                form_plan = await client.form_plan_client.fetch_plan(filename)

                with open(path / filename, "w") as f:
                    f.write(form_plan)

            for filename, timestamp in (await client.teacher_plan_client.fetch_dates()).items():
                teacher_plan = await client.teacher_plan_client.fetch_plan(filename)

                with open(path / filename, "w") as f:
                    f.write(teacher_plan)

            for filename, timestamp in (await client.room_plan_client.fetch_dates()).items():
                room_plan = await client.room_plan_client.fetch_plan(filename)

                with open(path / filename, "w") as f:
                    f.write(room_plan)
        except Exception as e:
            print(f"Error while fetching {name}: {e}")
            continue

        # substitution_plan_students = await client.fetch_substitution_plan_students(date)
        # substitution_plan_teachers = await client.fetch_substitution_plan_teachers(date)


if __name__ == '__main__':
    asyncio.run(main())
