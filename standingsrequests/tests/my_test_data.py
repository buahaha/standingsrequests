from copy import deepcopy
import inspect
import json
import os
from unittest.mock import Mock

from bravado.exception import HTTPNotFound

from allianceauth.eveonline.models import (
    EveCharacter,
    EveCorporationInfo,
    EveAllianceInfo,
)

from ..managers import _ContactsWrapper

from ..models import (
    AllianceStanding,
    CharacterAssociation,
    ContactSet,
    CorpStanding,
    EveNameCache,
    PilotStanding,
)


TEST_STANDINGS_API_CHARID = 1001
TEST_STANDINGS_API_CHARNAME = "Bruce Wayne"
TEST_STANDINGS_CORPORATION_ID = 2001
TEST_STANDINGS_CORPORATION_NAME = "Wayne Technologies"
TEST_STANDINGS_ALLIANCE_ID = 3001
TEST_STANDINGS_ALLIANCE_NAME = "Wayne Enterprises"


##########################
# internal functions


def _load_test_data():
    currentdir = os.path.dirname(
        os.path.abspath(inspect.getfile(inspect.currentframe()))
    )

    with open(currentdir + "/my_test_data.json", "r", encoding="utf-8") as f:
        my_test_data = json.load(f)

    return my_test_data


def _load_entities():
    entities = dict()
    for character_id, character in _my_test_data["EveCharacter"].items():
        entities[int(character_id)] = character["character_name"]

    for corporation_id, corporation in _my_test_data["EveCorporationInfo"].items():
        entities[int(corporation_id)] = corporation["corporation_name"]

    for alliance_id, alliance in _my_test_data["EveAllianceInfo"].items():
        entities[int(alliance_id)] = alliance["alliance_name"]

    return entities


_my_test_data = _load_test_data()
_entities = _load_entities()


##########################
# common functions


def get_my_test_data() -> dict:
    """returns the raw test data dict"""
    return _my_test_data


def get_entity_name(entity_id: int):
    """returns name if entity is found, else None"""

    if int(entity_id) in _entities:
        return _entities[int(entity_id)]
    else:
        return None


def get_entity_names(eve_entity_ids: list) -> dict:
    """returns dict with {id: name} for found entities, else empty dict"""
    names_info = dict()
    for id in eve_entity_ids:
        name = get_entity_name(id)
        if name:
            names_info[id] = name

    return names_info


def get_entity_data(EntityClass: type, entity_id: int) -> object:
    if EntityClass not in [EveCharacter, EveCorporationInfo, EveAllianceInfo]:
        raise TypeError("Invalid entity_class: {}".format(EntityClass.__name__))
    if str(entity_id) not in _my_test_data[EntityClass.__name__]:
        raise ValueError(
            "not entity found in test data for that entity_id = {}".format(entity_id)
        )
    return _my_test_data[EntityClass.__name__][str(entity_id)]


def create_entity(EntityClass: type, entity_id: int) -> object:
    """creates an Eve entity from test data"""
    data = get_entity_data(EntityClass, entity_id)
    return EntityClass.objects.create(**data)


##########################
# esi emulation


class BravadoOperationStub:
    """Stub to simulate the operation object return from bravado via django-esi"""

    class RequestConfig:
        def __init__(self, also_return_response):
            self.also_return_response = also_return_response

    def __init__(self, data, headers: dict = None, also_return_response: bool = False):
        self._data = data
        self._headers = headers if headers else {"x-pages": 1}
        self.request_config = BravadoOperationStub.RequestConfig(also_return_response)

    def result(self, **kwargs):
        if self.request_config.also_return_response:
            mock_response = Mock(**{"headers": self._headers})
            return [self._data, mock_response]
        else:
            return self._data


def esi_post_universe_names(ids, *args, **kwargs) -> object:
    entities = list()
    for entity in _my_test_data["esi_post_universe_names"]:
        if entity["id"] in ids:
            entities.append(entity)

    return BravadoOperationStub(entities)


def esi_post_characters_affiliation(characters, *args, **kwargs) -> object:
    result = []
    for assoc in _my_test_data["CharacterAssociation"]:
        if assoc["character_id"] in characters:
            row = assoc.copy()
            del row["main_character_id"]
            result.append(row)

    return BravadoOperationStub(result)


def esi_get_corporations_corporation_id(corporation_id, *args, **kwargs) -> object:
    result = []
    corporation_id = str(corporation_id)
    if corporation_id not in _my_test_data["EveCorporationInfo"]:
        raise HTTPNotFound(Mock(), message="Test Exception")

    row = _my_test_data["EveCorporationInfo"][corporation_id]
    result = {
        "name": row["corporation_name"],
        "ticker": row["corporation_ticker"],
        "member_count": row["member_count"],
        "ceo_id": 2987,
    }
    if row["alliance_id"]:
        result["alliance_id"] = row["alliance_id"]

    return BravadoOperationStub(result)


def esi_get_alliances_alliance_id_contacts_labels(*args, **kwargs) -> object:
    return BravadoOperationStub(deepcopy(_my_test_data["alliance_labels"]))


def esi_get_alliances_alliance_id_contacts(*args, **kwargs) -> object:
    return BravadoOperationStub(deepcopy(_my_test_data["alliance_contacts"]))


##########################
# app specific functions


def create_standings_char():
    character, _ = EveCharacter.objects.get_or_create(
        character_id=TEST_STANDINGS_API_CHARID,
        defaults={
            "character_name": TEST_STANDINGS_API_CHARNAME,
            "corporation_id": TEST_STANDINGS_CORPORATION_ID,
            "corporation_name": TEST_STANDINGS_CORPORATION_ID,
            "alliance_id": TEST_STANDINGS_ALLIANCE_ID,
            "alliance_name": TEST_STANDINGS_ALLIANCE_NAME,
        },
    )
    EveNameCache.objects.update_or_create(
        entity_id=character.character_id, defaults={"name": character.character_name},
    )
    EveNameCache.objects.update_or_create(
        entity_id=character.corporation_id,
        defaults={"name": character.corporation_name},
    )
    EveNameCache.objects.update_or_create(
        entity_id=character.alliance_id, defaults={"name": character.alliance_name},
    )
    return character


def get_test_labels() -> list:
    """returns labels from test data as list of _ContactsWrapper.Label"""
    labels = list()
    for label_data in get_my_test_data()["alliance_labels"]:
        labels.append(_ContactsWrapper.Label(label_data))

    return labels


def get_test_contacts():
    """returns contacts from test data as list of _ContactsWrapper.Contact"""
    labels = get_test_labels()

    contact_ids = [x["contact_id"] for x in get_my_test_data()["alliance_contacts"]]
    names_info = get_entity_names(contact_ids)
    contacts = list()
    for contact_data in get_my_test_data()["alliance_contacts"]:
        contacts.append(_ContactsWrapper.Contact(contact_data, labels, names_info))

    return contacts


def create_contacts_set(my_set: object = None) -> object:

    if not my_set:
        my_set = ContactSet.objects.create(name="Dummy Set")

    # add labels
    ContactSet.objects._add_labels_from_api(my_set, get_test_labels())

    # create contacts for ContactSet
    for contact in _my_test_data["alliance_contacts"]:
        if contact["contact_type"] == "character":
            MyStandingClass = PilotStanding

        elif contact["contact_type"] == "corporation":
            MyStandingClass = CorpStanding

        elif contact["contact_type"] == "alliance":
            MyStandingClass = AllianceStanding

        else:
            raise ValueError("Invalid contact type")

        my_standing = MyStandingClass.objects.create(
            contact_set=my_set,
            contact_id=contact["contact_id"],
            name=get_entity_name(contact["contact_id"]),
            standing=contact["standing"],
        )
        for label_id in contact["label_ids"]:
            my_standing.labels.add(my_set.contactlabel_set.get(label_id=label_id))

    # update EveNameCache based on characters
    for character_id, character_data in _my_test_data["EveCharacter"].items():
        EveNameCache.objects.get_or_create(
            entity_id=character_id, defaults={"name": character_data["character_name"]}
        )
        EveNameCache.objects.get_or_create(
            entity_id=character_data["corporation_id"],
            defaults={"name": character_data["corporation_name"]},
        )
        if character_data["alliance_id"]:
            EveNameCache.objects.get_or_create(
                entity_id=character_data["alliance_id"],
                defaults={"name": character_data["alliance_name"]},
            )

    # create CharacterAssociation
    CharacterAssociation.objects.all().delete()
    for assoc in _my_test_data["CharacterAssociation"]:
        CharacterAssociation.objects.create(**assoc)

    return my_set


def create_eve_objects():
    """creates all Eve objects from test data"""
    EveCharacter.objects.all().delete()
    EveCorporationInfo.objects.all().delete()
    EveAllianceInfo.objects.all().delete()
    for character_data in _my_test_data[EveCharacter.__name__].values():
        character = EveCharacter.objects.create(**character_data)
        if character.alliance_id:
            defaults = {
                "alliance_name": character.alliance_name,
                "alliance_ticker": character.alliance_ticker,
                "executor_corp_id": 2001,
            }
            alliance, _ = EveAllianceInfo.objects.get_or_create(
                alliance_id=character.alliance_id, defaults=defaults
            )
        else:
            alliance = None

        defaults = {
            "corporation_name": character.corporation_name,
            "corporation_ticker": character.corporation_ticker,
            "member_count": 99,
            "alliance": alliance,
        }
        EveCorporationInfo.objects.get_or_create(
            corporation_id=character.corporation_id, defaults=defaults
        )
