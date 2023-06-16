from __future__ import annotations

import dataclasses
import datetime
import xml.etree.ElementTree as ET

from stundenplan24_py.shared import parse_free_days, Value, Exam

__all__ = [
    "FormPlan",
    "Form",
    "Lesson",
    "Class"
]


class FormPlan:
    plan_type: str
    timestamp: datetime.datetime  # time of last update
    plan_date: str
    filename: str
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
        assert day.plan_type == "K", (
            f"Plan type {day.plan_type!r}. A plan type ('Planart') other than 'K' is not supported. "
            "'K' is for 'Klassenplan', 'L' for 'Lehrerplan'."
        )

        day.timestamp = datetime.datetime.strptime(head.find("zeitstempel").text, "%d.%m.%Y, %H:%M")
        day.plan_date = head.find("DatumPlan").text
        day.filename = head.find("datei").text
        day.native = int(head.find("nativ").text)
        day.week = int(head.find("woche").text)
        day.days_per_week = int(head.find("tageprowoche").text)
        try:
            day.school_number = int(head.find("schulnummer").text)
        except (AttributeError, TypeError):
            day.school_number = None

        # parse free days
        day.free_days = parse_free_days(xml.find("FreieTage"))

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
    classes: dict[str, Class]
    lessons: list[Lesson]
    exams: list[Exam]

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
            start, end = period.attrib["ZeitVon"].strip(), period.attrib["ZeitBis"].strip()
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
            form.classes |= {class_.text: class_obj}

        # parse lessons
        form.lessons = []
        for _lesson in xml.find("Pl"):
            form.lessons.append(Lesson.from_xml(_lesson))

        # parse exams
        form.exams = []
        _exams = xml.find("Klausuren")
        if _exams is not None:
            for _exam in _exams:
                form.exams.append(Exam.from_xml_indiware_mobile(_exam))

        return form


@dataclasses.dataclass
class Class:
    teacher: str
    subject: str
    group: str | None


class Lesson:
    period: int
    start: datetime.time
    end: datetime.time

    subject: Value
    teacher: Value
    room: Value

    class_number: str | None
    information: str

    @classmethod
    def from_xml(cls, xml: ET.Element):
        lesson = cls()

        lesson.period = int(xml.find("St").text)
        lesson.start = (datetime.datetime.strptime(xml.find("Beginn").text.strip(), "%H:%M").time()
                        if xml.find("Beginn").text else None)
        lesson.end = (datetime.datetime.strptime(xml.find("Ende").text.strip(), "%H:%M").time()
                      if xml.find("Ende").text else None)

        lesson.subject = Value(xml.find("Fa").text, xml.find("Fa").get("FaAe") == "FaGeaendert")
        lesson.teacher = Value(xml.find("Le").text, xml.find("Le").get("LeAe") == "LeGeaendert")
        lesson.room = Value(xml.find("Ra").text, xml.find("Ra").get("RaAe") == "RaGeaendert")

        try:
            lesson.class_number = xml.find("Nr").text
        except AttributeError:
            lesson.class_number = None
        lesson.information = (xml.find("If").text.strip()
                              if xml.find("If").text is not None else None)

        return lesson
