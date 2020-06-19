from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.utils.timezone import now

from allianceauth.eveonline.models import EveCharacter
from allianceauth.tests.auth_utils import AuthUtils

from . import add_character_to_user
from ..models import StandingsRequest, PilotStanding
from .my_test_data import (
    create_standings_char,
    create_entity,
    create_contacts_set,
    TEST_STANDINGS_ALLIANCE_ID,
)
from ..utils import set_test_logger, NoSocketsTestCase

PACKAGE_PATH = "standingsrequests.management.commands"
logger = set_test_logger(PACKAGE_PATH, __file__)


TEST_USER_NAME = "Peter Parker"
TEST_REQUIRED_SCOPE = "mind_reading.v1"


@patch(
    "standingsrequests.models.STR_ALLIANCE_IDS", [str(TEST_STANDINGS_ALLIANCE_ID)],
)
@patch(
    "standingsrequests.models.SR_REQUIRED_SCOPES",
    {"Member": [TEST_REQUIRED_SCOPE], "Blue": [], "": []},
)
@patch(PACKAGE_PATH + ".standingsrequests_sync_blue_alts.get_input")
class TestSyncRequests(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = AuthUtils.create_member(TEST_USER_NAME)

    def setUp(self):
        create_standings_char()
        self.contacts_set = create_contacts_set()
        StandingsRequest.objects.all().delete()
        self.out = StringIO()

    def test_abort_if_input_is_not_y(self, mock_get_input):
        mock_get_input.return_value = "N"
        alt = create_entity(EveCharacter, 1010)
        add_character_to_user(self.user, alt, scopes=[TEST_REQUIRED_SCOPE])

        call_command("standingsrequests_sync_blue_alts", stdout=self.out)

        self.assertEqual(StandingsRequest.objects.count(), 0)

    def test_creates_new_request_for_blue_alt(self, mock_get_input):
        mock_get_input.return_value = "Y"
        alt = create_entity(EveCharacter, 1010)
        add_character_to_user(self.user, alt, scopes=[TEST_REQUIRED_SCOPE])

        call_command("standingsrequests_sync_blue_alts", stdout=self.out)

        self.assertEqual(StandingsRequest.objects.count(), 1)
        request = StandingsRequest.objects.first()
        self.assertEqual(request.user, self.user)
        self.assertEqual(request.contact_id, 1010)
        self.assertEqual(request.is_effective, True)
        self.assertAlmostEqual((now() - request.request_date).seconds, 0, delta=30)
        self.assertAlmostEqual((now() - request.action_date).seconds, 0, delta=30)
        self.assertAlmostEqual((now() - request.effective_date).seconds, 0, delta=30)

    def test_does_not_create_requests_for_blue_alt_if_request_already_exists(
        self, mock_get_input
    ):
        mock_get_input.return_value = "Y"
        alt = create_entity(EveCharacter, 1010)
        add_character_to_user(self.user, alt, scopes=[TEST_REQUIRED_SCOPE])
        StandingsRequest.add_request(
            self.user,
            alt.character_id,
            PilotStanding.get_contact_type_id(alt.character_id),
        )

        call_command("standingsrequests_sync_blue_alts", stdout=self.out)

        self.assertEqual(StandingsRequest.objects.count(), 1)

    def test_does_not_create_requests_for_non_blue_alts(self, mock_get_input):
        mock_get_input.return_value = "Y"
        alt = create_entity(EveCharacter, 1009)
        add_character_to_user(self.user, alt, scopes=[TEST_REQUIRED_SCOPE])

        call_command("standingsrequests_sync_blue_alts", stdout=self.out)

        self.assertEqual(StandingsRequest.objects.count(), 0)

    def test_does_not_create_requests_for_alts_in_organization(self, mock_get_input):
        mock_get_input.return_value = "Y"
        main = create_entity(EveCharacter, 1002)
        add_character_to_user(
            self.user, main, is_main=True, scopes=[TEST_REQUIRED_SCOPE]
        )

        call_command("standingsrequests_sync_blue_alts", stdout=self.out)

        self.assertEqual(StandingsRequest.objects.count(), 0)

    def test_does_not_create_requests_for_alts_without_matching_scopes(
        self, mock_get_input
    ):
        mock_get_input.return_value = "Y"
        user = AuthUtils.create_member("John Doe")
        alt = create_entity(EveCharacter, 1010)
        add_character_to_user(user, alt)

        call_command("standingsrequests_sync_blue_alts", stdout=self.out)

        self.assertEqual(StandingsRequest.objects.count(), 0)
