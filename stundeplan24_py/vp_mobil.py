from __future__ import annotations

import dataclasses
import datetime
from xml.etree import ElementTree as ET


class Day:
    plan_type: str
    timestamp: datetime.datetime
    plan_date: str
    file_name: str
    native: str
    week: int
    days_per_week: int
    school_number: int = None

    free_days: list[datetime.date]
    forms: list[Form]
    additional_info: list[str]

    @classmethod
    def from_xml(cls, xml: ET.Element):
        day = cls()

        # parse head
        head = xml.find("Kopf")
        day.plan_type = head.find("planart").text
        assert day.plan_type == "K", "A plan type ('Planart') other than 'K' is not supported."

        day.timestamp = datetime.datetime.strptime(head.find("zeitstempel").text, "%d.%m.%Y, %H:%M")
        day.plan_date = head.find("DatumPlan").text
        day.file_name = head.find("datei").text
        day.native = int(head.find("nativ").text)
        day.week = int(head.find("woche").text)
        day.days_per_week = int(head.find("tageprowoche").text)
        try:
            day.school_number = int(head.find("schulnummer").text)
        except (AttributeError, TypeError):
            day.school_number = None

        # parse free days
        day.free_days = []
        for free_day in xml.find("FreieTage"):
            day.free_days.append(datetime.datetime.strptime(free_day.text, "%y%m%d").date())

        # parse classes
        day.forms = []
        for class_ in xml.find("Klassen"):
            day.forms.append(Form.from_xml(class_))

        # parse additional info
        day.additional_info = []
        _additional_info = xml.find("ZusatzInfo")
        _additional_info = _additional_info if _additional_info is not None else []
        for line in _additional_info:
            day.additional_info.append(line.text)

        return day


class Form:
    short_name: str
    hash: str | None

    periods: dict[int, tuple[datetime.time, datetime.time]]
    courses: dict[str, str]  # course name: teacher
    classes: dict[int, Class]
    lessons: list[Lesson]

    @classmethod
    def from_xml(cls, xml: ET.Element):
        form = cls()

        form.short_name = xml.find("Kurz").text
        try:
            form.hash = xml.find("Hash").text
        except AttributeError:
            form.hash = None

        # parse periods
        form.periods = {}
        for period in xml.find("KlStunden"):
            start, end = period.attrib["ZeitVon"], period.attrib["ZeitBis"]
            start = datetime.datetime.strptime(start, "%H:%M").time()
            end = datetime.datetime.strptime(end, "%H:%M").time()
            form.periods |= {int(period.text): (start, end)}

        # parse courses
        form.courses = {}
        for _course in xml.find("Kurse"):
            course = _course.find("KKz")
            form.courses |= {course.text: course.attrib["KLe"]}

        # parse classes
        form.classes = {}
        for _class in xml.find("Unterricht"):
            class_ = _class.find("UeNr")
            class_obj = Class(
                teacher=class_.attrib["UeLe"],
                subject=class_.attrib["UeFa"],
                group=class_.attrib["UeGr"] if "UeGr" in class_.attrib else None
            )
            form.classes |= {int(class_.text): class_obj}

        # parse lessons
        form.lessons = []
        for _lesson in xml.find("Pl"):
            form.lessons.append(Lesson.from_xml(_lesson))

        return form


@dataclasses.dataclass
class Class:
    teacher: str
    subject: str
    group: str | None


@dataclasses.dataclass
class Value:
    content: str
    was_changed: bool

    def __str__(self):
        return self.content

    def __call__(self):
        return self.content


class Lesson:
    period: int
    start: datetime.time
    end: datetime.time

    subject: Value
    teacher: Value
    room: Value

    number: int | None
    information: str

    @classmethod
    def from_xml(cls, xml: ET.Element):
        lesson = cls()

        lesson.period = int(xml.find("St").text)
        lesson.start = datetime.datetime.strptime(xml.find("Beginn").text, "%H:%M").time()
        lesson.end = datetime.datetime.strptime(xml.find("Ende").text, "%H:%M").time()

        lesson.subject = Value(xml.find("Fa").text, False)
        lesson.teacher = Value(xml.find("Le").text, False)
        lesson.room = Value(xml.find("Ra").text, False)

        try:
            lesson.number = int(xml.find("Nr").text)
        except AttributeError:
            lesson.number = None
        lesson.information = xml.find("If").text

        return lesson
