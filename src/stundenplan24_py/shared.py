from __future__ import annotations

import dataclasses
import datetime
import xml.etree.ElementTree as ET

__all__ = [
    "Value",
    "Exam"
]


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


class Exam:
    year: int
    course: str
    course_teacher: str
    period: int
    begin: datetime.time
    duration: int  # minutes
    info: str | None

    @classmethod
    def from_xml_substitution_plan(cls, xml: ET.Element) -> Exam:
        exam = cls()

        exam.year = int(xml.find("jahrgang").text)
        exam.course = xml.find("kurs").text
        exam.course_teacher = xml.find("kursleiter").text
        exam.period = int(xml.find("stunde").text)
        exam.begin = datetime.datetime.strptime(xml.find("beginn").text, "%H:%M").time()
        exam.duration = int(xml.find("dauer").text)
        exam.info = xml.find("kinfo").text

        return exam

    @classmethod
    def from_xml_indiware_mobile(cls, xml: ET.Element) -> Exam:
        exam = cls()

        exam.year = int(xml.find(f"KlJahrgang").text)
        exam.course = xml.find("KlKurs").text
        exam.course_teacher = xml.find("KlKursleiter").text
        exam.period = int(xml.find("KlStunde").text)
        exam.begin = datetime.datetime.strptime(xml.find("KlBeginn").text, "%H:%M").time()
        exam.duration = int(xml.find("KlDauer").text)
        exam.info = xml.find("KlKinfo").text

        return exam
