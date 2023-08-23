from __future__ import annotations

import abc
import dataclasses
import urllib.parse
import typing

__all__ = [
    "Endpoints",
    "IndiwareMobilEndpoint",
    "FormsIndiwareMobilEndpoint",
    "TeachersIndiwareMobilEndpoint",
    "RoomsIndiwareMobilEndpoint",
    "IndiwareMobilEndpoints",
    "SubstitutionPlanEndpoint",
    "StudentsSubstitutionPlanEndpoint",
    "TeachersSubstitutionPlanEndpoint",
    "SubstitutionPlanEndpoints"
]


class Endpoints:
    # indiware mobil
    indiware_mobil_vpdir = "_phpmob/vpdir.php"  # POST with data
    indiware_mobil_file = "mobdaten/{filename}"

    # /mobil/
    indiware_mobil_forms = "mobdaten/PlanKl{date}.xml"  # date must not be "", use below
    indiware_mobil_forms2 = "mobdaten/Klassen.xml"
    indiware_mobil_forms_vpinfo = "mobdaten/vpinfok.txt"

    # /moble/
    indiware_mobil_teachers = "mobdaten/PlanLe{date}.xml"  # date must not be "", use below
    indiware_mobil_teachers2 = "mobdaten/Lehrer.xml"
    indiware_mobil_teachers_vpinfo = "mobdaten/vpinfol.txt"

    # /mobra/
    indiware_mobil_rooms = "mobdaten/PlanRa{date}.xml"  # date must not be "", use below
    indiware_mobil_rooms2 = "mobdaten/Raeume.xml"
    indiware_mobil_rooms_vpinfo = "mobdaten/vpinfor.txt"

    # substitution plan (/vplan/ or /vplanle/)
    substitution_plan = "vdaten/{filename}.xml"
    substitution_plan2_students = "vdaten/VplanKl{date}.xml"  # date can be ""
    substitution_plan2_teachers = "vdaten/VplanLe{date}.xml"  # date can be ""

    # week plan (/wplan/)
    week_plan_forms_timetable = "wdatenk/SPlanKl_Sw{school_week}.xml"
    week_plan_forms_timetable2 = "wdatenk/SPlanKl_Basis.xml"
    week_plan_forms = "wdatenk/WPlanKl_{date}.xml"  # date must not be ""

    week_plan_teachers_timetable = "wdatenr/SPlanLe_Sw{school_week}.xml"
    week_plan_teachers_timetable2 = "wdatenr/SPlanLe_Basis.xml"
    week_plan_teachers = "wdatenr/WPlanLe_{date}.xml"  # date must not be ""

    week_plan_rooms_timetable = "wdatenl/SPlanRa_Sw{school_week}.xml"
    week_plan_rooms_timetable2 = "wdatenl/SPlanRa_Basis.xml"
    week_plan_rooms = "wdatenl/WPlanRa_{date}.xml"  # date must not be ""

    # timetable (/splan/)
    timetable_forms = "sdaten/splank.xml"
    timetable_teachers = "sdaten/splanl.xml"
    timetable_rooms = "sdaten/splanr.xml"


class IndiwareMobilEndpoint(abc.ABC):
    url: str
    vpdir_password: str  # usually mob[k|l|r]

    plan_file_url: str
    plan_file_url2: str
    vpinfo_url: str

    def __init__(self, url: str):
        self.url = url


class FormsIndiwareMobilEndpoint(IndiwareMobilEndpoint):
    vpdir_password = "mobk"
    plan_file_url = Endpoints.indiware_mobil_forms
    plan_file_url2 = Endpoints.indiware_mobil_forms2
    vpinfo_url = Endpoints.indiware_mobil_forms_vpinfo

    @classmethod
    def from_stundenplan24(cls, sp24_url: str) -> FormsIndiwareMobilEndpoint:
        return cls(urllib.parse.urljoin(sp24_url, "mobil/"))


class TeachersIndiwareMobilEndpoint(IndiwareMobilEndpoint):
    vpdir_password = "mobl"
    plan_file_url = Endpoints.indiware_mobil_teachers
    plan_file_url2 = Endpoints.indiware_mobil_teachers2
    vpinfo_url = Endpoints.indiware_mobil_teachers_vpinfo

    @classmethod
    def from_stundenplan24(cls, sp24_url: str) -> TeachersIndiwareMobilEndpoint:
        return cls(urllib.parse.urljoin(sp24_url, "moble/"))


class RoomsIndiwareMobilEndpoint(IndiwareMobilEndpoint):
    vpdir_password = "mobr"
    plan_file_url = Endpoints.indiware_mobil_rooms
    plan_file_url2 = Endpoints.indiware_mobil_rooms2
    vpinfo_url = Endpoints.indiware_mobil_rooms_vpinfo

    @classmethod
    def from_stundenplan24(cls, sp24_url: str) -> RoomsIndiwareMobilEndpoint:
        return cls(urllib.parse.urljoin(sp24_url, "mobra/"))


@dataclasses.dataclass
class IndiwareMobilEndpoints:
    forms: IndiwareMobilEndpoint | None = None
    teachers: IndiwareMobilEndpoint | None = None
    rooms: IndiwareMobilEndpoint | None = None

    @classmethod
    def from_stundenplan24(cls, sp24_url: str) -> IndiwareMobilEndpoints:
        return cls(
            forms=FormsIndiwareMobilEndpoint.from_stundenplan24(sp24_url),
            teachers=TeachersIndiwareMobilEndpoint.from_stundenplan24(sp24_url),
            rooms=RoomsIndiwareMobilEndpoint.from_stundenplan24(sp24_url)
        )

    @classmethod
    def deserialize(cls, data: dict[str, typing.Any]) -> IndiwareMobilEndpoints:
        return cls(
            forms=(
                FormsIndiwareMobilEndpoint(url=data["students"])
                if "students" in data else None
            ),
            teachers=(
                TeachersIndiwareMobilEndpoint(url=data["teachers"])
                if "teachers" in data else None
            ),
            rooms=(
                RoomsIndiwareMobilEndpoint(url=data["rooms"])
                if "rooms" in data else None
            )
        )


class SubstitutionPlanEndpoint:
    url: str
    plan_file_url2: str

    def __init__(self, url: str):
        self.url = url


class StudentsSubstitutionPlanEndpoint(SubstitutionPlanEndpoint):
    plan_file_url2 = Endpoints.substitution_plan2_students

    @classmethod
    def from_stundenplan24(cls, sp24_url: str) -> StudentsSubstitutionPlanEndpoint:
        return cls(urllib.parse.urljoin(sp24_url, "vplan/"))


class TeachersSubstitutionPlanEndpoint(SubstitutionPlanEndpoint):
    plan_file_url2 = Endpoints.substitution_plan2_teachers

    @classmethod
    def from_stundenplan24(cls, sp24_url: str) -> TeachersSubstitutionPlanEndpoint:
        return cls(urllib.parse.urljoin(sp24_url, "vplanle/"))


@dataclasses.dataclass
class SubstitutionPlanEndpoints:
    students: StudentsSubstitutionPlanEndpoint | None = None
    teachers: TeachersSubstitutionPlanEndpoint | None = None

    @classmethod
    def from_stundenplan24(cls, sp24_url: str) -> SubstitutionPlanEndpoints:
        return cls(
            students=StudentsSubstitutionPlanEndpoint.from_stundenplan24(sp24_url),
            teachers=TeachersSubstitutionPlanEndpoint.from_stundenplan24(sp24_url)
        )

    @classmethod
    def deserialize(cls, data: dict[str, typing.Any]):
        return cls(
            students=(
                StudentsSubstitutionPlanEndpoint(url=data["students"])
                if "students" in data else None
            ),
            teachers=(
                TeachersSubstitutionPlanEndpoint(url=data["teachers"])
                if "teachers" in data else None
            )
        )
