from app.domains.challenges.errors import ChallengeDefinitionError
from app.domains.challenges.models import (
    Challenge,
    ChallengeTrack,
    ChallengeVersion,
    Difficulty,
    PlayableChallenge,
    PublicationState,
    VisibleExample,
)
from app.domains.evaluation.configuration import (
    EvaluationConfiguration,
    ExactMatchGraderConfig,
    ModelConfiguration,
)
from app.domains.evaluation.test_cases import VisibleTestCase
from app.domains.scoring.configuration import (
    EfficiencyThresholds,
    ScoringConfiguration,
    StarThresholds,
)

_EXACT_MATCH = ExactMatchGraderConfig()

EXACT_OUTPUT_CHALLENGE = PlayableChallenge(
    challenge=Challenge(
        id="control-exact-output",
        slug="exact-output",
        track=ChallengeTrack.CONTROL,
        order=1,
        current_version_id="1",
    ),
    version=ChallengeVersion(
        version_id="1",
        challenge_id="control-exact-output",
        title="Exact Output",
        description="Constrain a model to report whether a service is currently available.",
        objective="Return exactly YES when the service is available, otherwise return exactly NO.",
        constraints=(
            "Return only YES or NO in uppercase.",
            "Do not include punctuation, explanation, or formatting.",
            "Judge the service's current availability from the supplied statement.",
        ),
        difficulty=Difficulty.EASY,
        visible_examples=(
            VisibleExample(
                input="The dashboard reports that the service is online.",
                expected_output="YES",
                explanation="The service is currently available.",
            ),
            VisibleExample(
                input="The service is offline during an active outage.",
                expected_output="NO",
                explanation="The service is currently unavailable.",
            ),
        ),
        visible_test_cases=(
            VisibleTestCase(
                id="visible-1",
                input="The status page says all systems are operational.",
                expected_output="YES",
                grader_config=_EXACT_MATCH,
            ),
            VisibleTestCase(
                id="visible-2",
                input="Scheduled maintenance is currently preventing customer logins.",
                expected_output="NO",
                grader_config=_EXACT_MATCH,
            ),
            VisibleTestCase(
                id="visible-3",
                input="The API is responding normally with no reported outage.",
                expected_output="YES",
                grader_config=_EXACT_MATCH,
            ),
        ),
        prompt_token_limit=120,
        evaluation_config=EvaluationConfiguration(default_grader=_EXACT_MATCH),
        scoring_config=ScoringConfiguration(
            accuracy_weight=0.8,
            efficiency_weight=0.2,
            efficiency_thresholds=EfficiencyThresholds(
                full_credit_at_or_below=40,
                no_credit_at_or_above=120,
            ),
            star_thresholds=StarThresholds(one_star=50, two_stars=80, three_stars=100),
        ),
        model_config=ModelConfiguration(
            model_id="openai/gpt-oss-20b",
            temperature=0,
            max_output_tokens=8,
            configuration_version="exact-output-model-v1",
            system_wrapper=(
                "Apply the player's instruction to the next user message, which contains the "
                "test input. Do not add facts that are not present in that input."
            ),
        ),
        publication_state=PublicationState.PUBLISHED,
    ),
)


class InMemoryChallengeRepository:
    """Temporary immutable-fixture reader, replaceable through ChallengeReader."""

    def __init__(self, challenges: tuple[PlayableChallenge, ...] | None = None) -> None:
        items = (EXACT_OUTPUT_CHALLENGE,) if challenges is None else tuple(challenges)
        by_slug = {item.challenge.slug: item for item in items}
        if len(by_slug) != len(items):
            raise ChallengeDefinitionError("In-memory challenge slugs must be unique.")
        self._by_slug = by_slug

    def get_by_slug(self, slug: str) -> PlayableChallenge | None:
        return self._by_slug.get(slug)
