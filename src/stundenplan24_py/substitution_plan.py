from __future__ import annotations

import datetime
import xml.etree.ElementTree as ET

from .shared import parse_free_days, parse_plan_date, Value, Exam

import pytz

__all__ = ["SubstitutionPlan", "Action"]


def split_text_if_exists(xml: ET.Element, tag: str) -> list[str]:
    try:
        return xml.find(tag).text.split(", ")
    except AttributeError:
        return []


class SubstitutionPlan:
    filename: str
    date: datetime.date
    school_name: str
    timestamp: datetime.datetime  # time of last update

    absent_teachers: list[str]
    absent_forms: list[str]
    absent_rooms: list[str]
    changed_teachers: list[str]
    changed_forms: list[str]

    free_days: list[datetime.date]

    actions: list[Action]

    exams: list[Exam]

    break_supervisions: list[str]

    additional_info: list[str]

    @classmethod
    def from_xml(cls, xml: ET.Element) -> SubstitutionPlan:
        plan = cls()

        head = xml.find("kopf")
        plan.filename = head.find("datei").text
        plan.date = parse_plan_date(head.find("titel").text)
        plan.school_name = head.find("schulname").text
        plan.timestamp = (
            pytz.timezone("Europe/Berlin")
            .localize(datetime.datetime.strptime(head.find("datum").text, "%d.%m.%Y, %H:%M"))
        )

        head_info = head.find("kopfinfo")

        plan.absent_teachers = split_text_if_exists(head_info, "abwesendl")
        plan.absent_forms = split_text_if_exists(head_info, "abwesendk")
        plan.absent_rooms = split_text_if_exists(head_info, "abwesendr")
        plan.changed_teachers = split_text_if_exists(head_info, "aenderungl")
        plan.changed_forms = split_text_if_exists(head_info, "aenderungk")

        plan.free_days = parse_free_days(xml.find("freietage"))

        plan.actions = []
        for action in xml.find("haupt") or []:
            plan.actions.append(Action.from_xml(action))

        plan.exams = []
        for exam in xml.find("klausuren") or []:
            plan.exams.append(Exam.from_xml_substitution_plan(exam))

        plan.break_supervisions = []
        for supervision_row in xml.find("aufsichten") or []:
            plan.break_supervisions.append(supervision_row.find("aufsichtinfo").text)

        footer = xml.find("fuss")
        plan.additional_info = []

        if footer is not None:
            for line in footer.find("fusszeile") or []:
                plan.additional_info.append(line.text)

        return plan


class Action:
    form: str | None
    period: str

    subject: Value
    teacher: Value
    room: Value

    original_subject: str | None
    original_teacher: str | None
    original_room: str | None

    info: str | None

    @classmethod
    def from_xml(cls, xml: ET.Element) -> Action:
        action = cls()

        action.form = form.text if (form := xml.find("klasse")) is not None else None
        action.period = xml.find("stunde").text

        fach = xml.find("fach")
        lehrer = xml.find("lehrer")
        raum = xml.find("raum")

        vfach = xml.find("vfach")
        vlehrer = xml.find("vlehrer")
        vraum = xml.find("vraum")

        if (vfach is not None) or (vlehrer is not None) or (vraum is not None):
            # this is a teachers' substitution plan
            action.original_subject = fach.text
            action.original_teacher = lehrer.text
            action.original_room = raum.text if raum is not None else None

            action.subject = Value(vfach.text, vfach.get("legeaendert") == "ae")
            action.teacher = Value(vlehrer.text, vlehrer.get("legeaendert") == "ae")
            action.room = Value(vraum.text, vraum.get("rageaendert") == "ae")
        else:
            # in students' substitution plans, the original values are included in the info
            action.original_subject = None
            action.original_teacher = None
            action.original_room = None

            action.subject = Value(fach.text, xml.find("lehrer").get("legeaendert") == "ae")
            action.teacher = Value(lehrer, lehrer.get("legeaendert") == "ae")
            action.room = Value(raum.text, raum.get("rageaendert") == "ae")

        action.info = xml.find("info").text

        return action
