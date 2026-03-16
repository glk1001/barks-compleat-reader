from enum import StrEnum


class EntityType(StrEnum):
    PERSON = "person"
    LOCATION = "location"
    ORG = "org"
    WORK = "work"
    MISC = "misc"
