from __future__ import annotations

import dataclasses
import datetime
import xml.etree.ElementTree as ET


def parse_free_days(xml: ET.Element) -> list[datetime.date]:
    free_days = []
    for day in xml:
        free_days.append(
            datetime.datetime.strptime(day.text, "%y%m%d").date()
        )

    return free_days


@dataclasses.dataclass
class Value:
    content: str
    was_changed: bool

    def __str__(self):
        return self.content

    def __call__(self):
        return self.content
