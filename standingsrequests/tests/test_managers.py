from datetime import timedelta
from unittest.mock import Mock, patch

from bravado.exception import HTTPError

from django.utils.timezone import now
from eveuniverse.models import EveEntity

from allianceauth.eveonline.models import EveCharacter
from allianceauth.tests.auth_utils import AuthUtils
from app_utils.testing import NoSocketsTestCase, add_character_to_user

from ..core import BaseConfig
from ..models import (
    AbstractStandingsRequest,
    CharacterAffiliation,
    Contact,
    ContactSet,
    CorporationDetails,
    StandingRequest,
    StandingRevocation,
)
from .entity_type_ids import CHARACTER_TYPE_ID, CORPORATION_TYPE_ID
from .my_test_data import (
    TEST_STANDINGS_API_CHARID,
    TEST_STANDINGS_API_CHARNAME,
    create_contacts_set,
    create_entity,
    create_standings_char,
    esi_get_alliances_alliance_id_contacts,
    esi_get_alliances_alliance_id_contacts_labels,
    esi_get_corporations_corporation_id,
    esi_post_characters_affiliation,
    load_eve_entities,
)

CORE_PATH = "standingsrequests.core"
MANAGERS_PATH = "standingsrequests.managers"
MODELS_PATH = "standingsrequests.models"
TEST_USER_NAME = "Peter Parker"


class TestContactSetManager(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = AuthUtils.create_member(TEST_STANDINGS_API_CHARNAME)
        character = create_standings_char()
        add_character_to_user(
            cls.user, character, scopes=["esi-alliances.read_contacts.v1"]
        )
        load_eve_entities()

    @patch(CORE_PATH + ".STANDINGS_API_CHARID", TEST_STANDINGS_API_CHARID)
    @patch(CORE_PATH + ".SR_OPERATION_MODE", "alliance")
    @patch(CORE_PATH + ".SR_OPERATION_MODE", "alliance")
    @patch(MANAGERS_PATH + ".esi")
    def test_can_create_new_from_api(self, mock_esi):
        mock_Contacts = mock_esi.client.Contacts
        mock_Contacts.get_alliances_alliance_id_contacts_labels.side_effect = (
            esi_get_alliances_alliance_id_contacts_labels
        )
        mock_Contacts.get_alliances_alliance_id_contacts.side_effect = (
            esi_get_alliances_alliance_id_contacts
        )

        # labels
        contact_set = ContactSet.objects.create_new_from_api()
        labels = set(contact_set.labels.values_list("label_id", "name"))
        expected = {(1, "blue"), (2, "green"), (3, "yellow"), (4, "red")}
        self.assertSetEqual(labels, expected)

        # all_contacts
        all_contacts = set(
            contact_set.contacts.values_list("eve_entity_id", "standing")
        )
        expected = {
            (1001, 10),
            (1002, 10),
            (1003, 5),
            (1004, 0.01),
            (1005, 0),
            (1006, 0),
            (1008, -5),
            (1009, -10),
            (1010, 5),
            (1110, 5.0),
            (2001, 10.0),
            (2003, 5.0),
            (2102, -10.0),
            (3010, -10.0),
        }
        self.assertSetEqual(all_contacts, expected)

    @patch(CORE_PATH + ".STANDINGS_API_CHARID", TEST_STANDINGS_API_CHARID)
    def test_standings_character_exists(self):
        character = create_standings_char()
        self.assertEqual(BaseConfig.owner_character(), character)

    @patch(CORE_PATH + ".STANDINGS_API_CHARID", TEST_STANDINGS_API_CHARID)
    @patch(MODELS_PATH + ".EveCharacter.objects.create_character")
    def test_standings_character_not_exists(self, mock_create_character):
        character, _ = EveCharacter.objects.get_or_create(
            character_id=TEST_STANDINGS_API_CHARID,
            defaults={
                "character_name": TEST_STANDINGS_API_CHARNAME,
                "corporation_id": 2099,
                "corporation_name": "Dummy Corp",
            },
        )
        mock_create_character.return_value = character
        self.assertEqual(BaseConfig.owner_character(), character)
        self.assertTrue(EveEntity.objects.filter(id=TEST_STANDINGS_API_CHARID).exists())


class TestAbstractStandingsRequestManager(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_contacts_set()
        cls.user_requestor = AuthUtils.create_member("Bruce Wayne")
        cls.user_manager = AuthUtils.create_user("Mike Manager")

    def test_pending_requests_empty(self):
        self.assertEqual(StandingRequest.objects.pending_requests().count(), 0)

    def test_should_count_pending_requests_correctly(self):
        # given
        StandingRequest.objects.create(
            user=self.user_requestor,
            contact_id=1001,
            contact_type_id=CHARACTER_TYPE_ID,
            is_effective=False,
        )
        StandingRequest.objects.create(
            user=self.user_requestor,
            contact_id=1002,
            contact_type_id=CHARACTER_TYPE_ID,
            is_effective=True,
        )
        StandingRequest.objects.create(
            user=self.user_requestor,
            contact_id=1003,
            contact_type_id=CHARACTER_TYPE_ID,
            is_effective=False,
            action_date=now(),
        )
        # when
        result = StandingRequest.objects.pending_requests()
        # then
        self.assertEqual(result.count(), 1)


@patch(MANAGERS_PATH + ".SR_NOTIFICATIONS_ENABLED", True)
@patch(CORE_PATH + ".STANDINGS_API_CHARID", TEST_STANDINGS_API_CHARID)
@patch(MODELS_PATH + ".SR_STANDING_TIMEOUT_HOURS", 24)
@patch(MANAGERS_PATH + ".notify")
class TestAbstractStandingsRequestProcessRequests(NoSocketsTestCase):
    def setUp(self):
        self.user_manager = AuthUtils.create_user("Mike Manager")
        self.user_requestor = AuthUtils.create_user("Roger Requestor")
        ContactSet.objects.all().delete()
        self.contact_set = create_contacts_set()
        create_standings_char()

    def test_when_pilot_standing_satisfied_in_game_mark_effective_and_inform_user(
        self, mock_notify
    ):
        my_request = StandingRequest.objects.create(
            user=self.user_requestor,
            contact_id=1002,
            contact_type_id=CHARACTER_TYPE_ID,
            action_by=self.user_manager,
            action_date=now(),
        )
        StandingRequest.objects.process_requests()
        my_request.refresh_from_db()
        self.assertTrue(my_request.is_effective)
        self.assertIsNotNone(my_request.effective_date)
        self.assertEqual(my_request.action_by, self.user_manager)
        self.assertIsNotNone(my_request.action_date)
        self.assertEqual(mock_notify.call_count, 1)
        args, kwargs = mock_notify.call_args
        self.assertEqual(kwargs["user"], self.user_requestor)

    def test_dont_inform_user_when_sr_was_effective_before(self, mock_notify):
        my_request = StandingRequest.objects.create(
            user=self.user_requestor,
            contact_id=1002,
            contact_type_id=CHARACTER_TYPE_ID,
            action_by=self.user_manager,
            action_date=now(),
            is_effective=True,
            effective_date=now(),
        )
        StandingRequest.objects.process_requests()
        my_request.refresh_from_db()
        self.assertTrue(my_request.is_effective)
        self.assertIsNotNone(my_request.effective_date)
        self.assertEqual(my_request.action_by, self.user_manager)
        self.assertIsNotNone(my_request.action_date)
        self.assertEqual(mock_notify.call_count, 0)

    def test_when_corporation_standing_satisfied_in_game_mark_effective(
        self, mock_notify
    ):
        my_request = StandingRequest.objects.create(
            user=self.user_requestor,
            contact_id=2003,
            contact_type_id=CORPORATION_TYPE_ID,
            action_by=self.user_manager,
            action_date=now(),
        )
        StandingRequest.objects.process_requests()
        my_request.refresh_from_db()
        self.assertTrue(my_request.is_effective)
        self.assertIsNotNone(my_request.effective_date)
        self.assertEqual(my_request.action_by, self.user_manager)
        self.assertIsNotNone(my_request.action_date)
        self.assertTrue(mock_notify.called)

    def test_notify_about_requests_that_are_reset_and_timed_out(self, mock_notify):
        StandingRequest.objects.create(
            user=self.user_requestor,
            contact_id=1008,
            contact_type_id=CHARACTER_TYPE_ID,
            action_by=self.user_manager,
            action_date=now() - timedelta(hours=25),
        )
        StandingRequest.objects.process_requests()
        self.assertEqual(mock_notify.call_count, 2)

    def test_dont_notify_about_requests_that_are_reset_and_not_timed_out(
        self, mock_notify
    ):
        StandingRequest.objects.create(
            user=self.user_requestor,
            contact_id=1008,
            contact_type_id=CHARACTER_TYPE_ID,
            action_by=self.user_manager,
            action_date=now() - timedelta(hours=1),
        )
        StandingRequest.objects.process_requests()
        self.assertEqual(mock_notify.call_count, 0)

    def test_no_action_when_actioned_standing_but_not_in_game_yet(self, mock_notify):
        my_request = StandingRequest.objects.create(
            user=self.user_requestor,
            contact_id=1002,
            contact_type_id=CHARACTER_TYPE_ID,
            action_by=self.user_manager,
            action_date=now(),
        )
        self.contact_set.contacts.get(eve_entity_id=1002).delete()
        StandingRequest.objects.process_requests()
        my_request.refresh_from_db()
        self.assertFalse(my_request.is_effective)
        self.assertIsNone(my_request.effective_date)
        self.assertEqual(mock_notify.call_count, 0)

    def test_raise_exception_when_called_from_abstract_object(self, mock_notify):
        with self.assertRaises(TypeError):
            AbstractStandingsRequest.objects.process_requests()

    def test_pending_request(self, mock_notify):
        StandingRequest.objects.create(
            user=self.user_requestor,
            contact_id=1001,
            contact_type_id=CHARACTER_TYPE_ID,
            is_effective=False,
        )
        self.assertTrue(AbstractStandingsRequest.objects.has_pending_request(1001))

        StandingRequest.objects.create(
            user=self.user_requestor,
            contact_id=1002,
            contact_type_id=CHARACTER_TYPE_ID,
            action_by=self.user_manager,
            action_date=now(),
            is_effective=True,
            effective_date=now(),
        )
        self.assertFalse(AbstractStandingsRequest.objects.has_pending_request(1002))


class TestAbstractStandingsRequestAnnotations(NoSocketsTestCase):
    def setUp(self):
        self.user_manager = AuthUtils.create_user("Mike Manager")
        self.user_requestor = AuthUtils.create_user("Roger Requestor")
        ContactSet.objects.all().delete()
        self.contact_set = create_contacts_set()
        create_standings_char()

    def test_pending_request_annotation(self):
        # given
        r1 = StandingRequest.objects.create(
            user=self.user_requestor,
            contact_id=1001,
            contact_type_id=CHARACTER_TYPE_ID,
            is_effective=False,
        )
        r2 = StandingRequest.objects.create(
            user=self.user_requestor,
            contact_id=1002,
            contact_type_id=CHARACTER_TYPE_ID,
            action_by=self.user_manager,
            action_date=now(),
            is_effective=True,
            effective_date=now(),
        )
        # when
        requests = StandingRequest.objects.all().annotate_is_pending()
        # then
        self.assertTrue(requests.get(pk=r1.pk).is_pending_annotated)
        self.assertFalse(requests.get(pk=r2.pk).is_pending_annotated)


@patch(MODELS_PATH + ".StandingRequest.can_request_corporation_standing")
class TestStandingsRequestValidateRequests(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_contacts_set()
        cls.user = AuthUtils.create_member("Bruce Wayne")

    def setUp(self):
        StandingRequest.objects.all().delete()

    def test_do_nothing_character_request_is_valid(
        self, mock_can_request_corporation_standing
    ):
        AuthUtils.add_permission_to_user_by_name(
            StandingRequest.REQUEST_PERMISSION_NAME, self.user
        )
        request = StandingRequest.objects.get_or_create_2(
            self.user, 1002, StandingRequest.CHARACTER_CONTACT_TYPE
        )

        StandingRequest.objects.validate_requests()
        self.assertTrue(StandingRequest.objects.filter(pk=request.pk).exists())

    def test_create_revocation_if_users_character_has_standing_but_user_no_permission(
        self, mock_can_request_corporation_standing
    ):
        StandingRequest.objects.get_or_create_2(
            self.user, 1002, StandingRequest.CHARACTER_CONTACT_TYPE
        )
        StandingRequest.objects.validate_requests()
        my_revocation = StandingRevocation.objects.get(contact_id=1002)
        self.assertEqual(
            my_revocation.reason, StandingRevocation.Reason.LOST_PERMISSION
        )

    def test_create_revocation_if_users_corporation_is_missing_apis(
        self, mock_can_request_corporation_standing
    ):
        mock_can_request_corporation_standing.return_value = False
        AuthUtils.add_permission_to_user_by_name(
            StandingRequest.REQUEST_PERMISSION_NAME, self.user
        )
        StandingRequest.objects.get_or_create_2(
            self.user, 2001, StandingRequest.CORPORATION_CONTACT_TYPE
        )

        StandingRequest.objects.validate_requests()
        my_revocation = StandingRevocation.objects.get(contact_id=2001)
        self.assertEqual(
            my_revocation.reason, StandingRevocation.Reason.MISSING_CORP_TOKEN
        )

    def test_keep_corp_standing_request_if_all_apis_recorded(
        self, mock_can_request_corporation_standing
    ):
        mock_can_request_corporation_standing.return_value = True
        AuthUtils.add_permission_to_user_by_name(
            StandingRequest.REQUEST_PERMISSION_NAME, self.user
        )
        request = StandingRequest.objects.get_or_create_2(
            self.user, 2001, StandingRequest.CORPORATION_CONTACT_TYPE
        )

        StandingRequest.objects.validate_requests()
        self.assertTrue(StandingRequest.objects.filter(pk=request.pk).exists())


class TestStandingsRequestManager(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_contacts_set()
        cls.user_requestor = AuthUtils.create_member("Bruce Wayne")
        cls.user_manager = AuthUtils.create_user("Mike Manager")

    def test_should_add_new_request(self):
        # when
        my_request = StandingRequest.objects.get_or_create_2(
            self.user_requestor, 1001, StandingRequest.CHARACTER_CONTACT_TYPE
        )
        # then
        self.assertIsInstance(my_request, StandingRequest)

    def test_should_not_create_new_request_that_already_exists(self):
        # given
        my_request_1 = StandingRequest.objects.get_or_create_2(
            self.user_requestor, 1001, StandingRequest.CHARACTER_CONTACT_TYPE
        )
        # when
        my_request_2 = StandingRequest.objects.get_or_create_2(
            self.user_requestor, 1001, StandingRequest.CHARACTER_CONTACT_TYPE
        )
        # then
        self.assertEqual(my_request_1, my_request_2)


class TestStandingsRevocationManager(NoSocketsTestCase):
    def setUp(self):
        ContactSet.objects.all().delete()
        load_eve_entities()
        my_set = ContactSet.objects.create(name="Dummy Set")
        Contact.objects.create(contact_set=my_set, eve_entity_id=1001, standing=10)
        Contact.objects.create(contact_set=my_set, eve_entity_id=1002, standing=5)
        Contact.objects.create(contact_set=my_set, eve_entity_id=1003, standing=0.01)
        Contact.objects.create(contact_set=my_set, eve_entity_id=1005, standing=0)
        Contact.objects.create(contact_set=my_set, eve_entity_id=1008, standing=-5)
        Contact.objects.create(contact_set=my_set, eve_entity_id=1009, standing=-10)
        self.user_manager = AuthUtils.create_user("Mike Manager")
        self.user_requestor = AuthUtils.create_user("Roger Requestor")

    def test_add_revocation_new(self):
        my_revocation = StandingRevocation.objects.add_revocation(
            1001,
            StandingRevocation.CHARACTER_CONTACT_TYPE,
            user=self.user_requestor,
            reason=StandingRevocation.Reason.OWNER_REQUEST,
        )
        self.assertIsInstance(my_revocation, StandingRevocation)

    def test_add_request_already_exists(self):
        StandingRevocation.objects.add_revocation(
            1001, StandingRevocation.CHARACTER_CONTACT_TYPE
        )
        my_revocation_2 = StandingRevocation.objects.add_revocation(
            1001, StandingRevocation.CHARACTER_CONTACT_TYPE
        )
        self.assertIsNone(my_revocation_2)

    def test_check_standing_satisfied_but_deleted_for_neutral_check_only(self):
        my_revocation = StandingRevocation.objects.add_revocation(
            1999, StandingRevocation.CHARACTER_CONTACT_TYPE
        )
        self.assertTrue(my_revocation.evaluate_effective_standing(check_only=True))

    def test_check_standing_satisfied_but_deleted_for_neutral(self):
        my_revocation = StandingRevocation.objects.add_revocation(
            1999, StandingRevocation.CHARACTER_CONTACT_TYPE
        )
        self.assertTrue(my_revocation.evaluate_effective_standing())
        self.assertTrue(my_revocation.is_effective)


@patch(MANAGERS_PATH + ".esi")
class TestCharacterAffiliationsManager(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_manager = AuthUtils.create_user("Mike Manager")
        cls.user_requestor = AuthUtils.create_user("Roger Requestor")

    def test_should_create_new_assocs(self, mock_esi):
        # given
        mock_esi.client.Character.post_characters_affiliation.side_effect = (
            esi_post_characters_affiliation
        )
        create_contacts_set(include_assoc=False)
        StandingRequest.objects.create(
            user=self.user_requestor,
            contact_id=1002,
            contact_type_id=CHARACTER_TYPE_ID,
            action_by=self.user_manager,
            action_date=now(),
        )
        # when
        CharacterAffiliation.objects.update_from_esi()
        # then
        existing_objects = set(
            CharacterAffiliation.objects.values_list("character_id", flat=True)
        )
        self.assertSetEqual(
            existing_objects, {1001, 1002, 1003, 1004, 1005, 1006, 1008, 1009, 1010}
        )

    def test_should_update_existing_assocs(self, mock_esi):
        # given
        mock_esi.client.Character.post_characters_affiliation.side_effect = (
            esi_post_characters_affiliation
        )
        create_contacts_set(include_assoc=True)
        assoc = CharacterAffiliation.objects.get(character_id=1001)
        assoc.corporation = EveEntity.objects.get(id=2003)
        assoc.save()
        # when
        CharacterAffiliation.objects.update_from_esi()
        # then
        existing_objects = set(
            CharacterAffiliation.objects.values_list("character_id", flat=True)
        )
        self.assertSetEqual(
            existing_objects,
            {1001, 1002, 1003, 1004, 1005, 1006, 1008, 1009, 1010},
        )
        assoc.refresh_from_db()
        self.assertEqual(assoc.corporation_id, 2001)

    def test_should_handle_exception_from_api(self, mock_esi):
        # given
        mock_esi.client.Character.post_characters_affiliation.side_effect = HTTPError(
            Mock()
        )
        create_contacts_set(include_assoc=False)
        # when
        CharacterAffiliation.objects.update_from_esi()

    def test_should_add_new_eve_character_relations(self, mock_esi):
        # given
        create_contacts_set(include_assoc=True)
        eve_character_1001 = create_entity(EveCharacter, 1001)
        # when
        CharacterAffiliation.objects.update_evecharacter_relations()
        # then
        assoc = CharacterAffiliation.objects.get(character_id=1001)
        self.assertEqual(assoc.eve_character, eve_character_1001)

    def test_should_update_existing_eve_character_relations(self, mock_esi):
        # given
        create_contacts_set(include_assoc=True)
        eve_character_1001 = create_entity(EveCharacter, 1001)
        eve_character_1002 = create_entity(EveCharacter, 1002)
        assoc = CharacterAffiliation.objects.get(character_id=1001)
        assoc.eve_character = eve_character_1002
        assoc.save()
        # when
        CharacterAffiliation.objects.update_evecharacter_relations()
        # then
        assoc = CharacterAffiliation.objects.get(character_id=1001)
        self.assertEqual(assoc.eve_character, eve_character_1001)


@patch(MANAGERS_PATH + ".esi")
class TestCorporationDetailsManager(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eve_entities()

    def test_should_update_corporations(self, mock_esi):
        # given
        mock_Corporation = mock_esi.client.Corporation
        mock_Corporation.get_corporations_corporation_id.side_effect = (
            esi_get_corporations_corporation_id
        )
        # when
        obj, created = CorporationDetails.objects.update_or_create_from_esi(2001)
        # then
        self.assertTrue(created)
        self.assertEqual(obj.corporation_id, 2001)
        self.assertEqual(obj.alliance_id, 3001)
        self.assertEqual(obj.ceo_id, 2987)
        self.assertEqual(obj.member_count, 3)
        self.assertEqual(obj.ticker, "WYT")
        self.assertIsNone(obj.faction)
