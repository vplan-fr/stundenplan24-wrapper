from __future__ import annotations

import datetime
import xml.etree.ElementTree as ET

from stundenplan24_py.shared import Value, parse_free_days


def split_text_if_exists(xml: ET.Element, tag: str) -> list[str]:
    try:
        return xml.find(tag).text.split(", ")
    except AttributeError:
        return []


class SubstitutionPlan:
    file_name: str
    title: str
    school_name: str
    timestamp: datetime.datetime  # time of last update

    absent_teachers: list[str]
    absent_forms: list[str]
    changed_teachers: list[str]
    changed_forms: list[str]

    free_days: list[datetime.date]

    actions: list[Action]

    exams: list[Exam]

    additional_info: list[str]

    @classmethod
    def from_xml(cls, xml: ET.Element) -> SubstitutionPlan:
        plan = cls()

        head = xml.find("kopf")
        plan.file_name = head.find("datei").text
        plan.title = head.find("titel").text
        plan.school_name = head.find("schulname").text
        plan.timestamp = datetime.datetime.strptime(head.find("datum").text, "%d.%m.%Y, %H:%M")

        head_info = head.find("kopfinfo")
        # TODO: absent teachers sometimes have the absent periods in parens like this: Bob (3-7)
        plan.absent_teachers = split_text_if_exists(head_info, "abwesendl")
        plan.absent_forms = split_text_if_exists(head_info, "abwesendk")
        plan.changed_teachers = split_text_if_exists(head_info, "aenderungl")
        plan.changed_forms = split_text_if_exists(head_info, "aenderungk")

        plan.free_days = parse_free_days(xml.find("freietage"))

        plan.actions = []
        for action in xml.find("haupt"):
            plan.actions.append(Action.from_xml(action))

        plan.exams = []
        for exam in xml.find("klausuren"):
            plan.exams.append(Exam.from_xml(exam))

        footer = xml.find("fuss")
        plan.additional_info = []
        for line in footer.find("fusszeile"):
            plan.additional_info.append(line.text)

        return plan


class Action:
    form: str
    period: str
    subject: Value
    teacher: Value
    room: Value
    info: str | None

    @classmethod
    def from_xml(cls, xml: ET.Element) -> Action:
        action = cls()

        action.form = xml.find("klasse").text
        action.period = xml.find("stunde").text
        action.subject = Value(xml.find("fach").text, xml.find("fach").get("fageaendert") == "ae")
        action.teacher = Value(xml.find("lehrer").text, xml.find("lehrer").get("legeaendert") == "ae")
        action.room = Value(xml.find("raum").text, xml.find("raum").get("rageaendert") == "ae")
        action.info = xml.find("info").text

        return action


class Exam:
    year: int
    course: str
    course_teacher: str
    period: int
    begin: datetime.time
    duration: int  # minutes
    info: str | None

    @classmethod
    def from_xml(cls, xml: ET.Element) -> Exam:
        exam = cls()

        exam.year = int(xml.find("jahrgang").text)
        exam.course = xml.find("kurs").text
        exam.course_teacher = xml.find("kursleiter").text
        exam.period = int(xml.find("stunde").text)
        exam.begin = datetime.datetime.strptime(xml.find("beginn").text, "%H:%M").time()
        exam.duration = int(xml.find("dauer").text)
        exam.info = xml.find("kinfo").text

        return exam
