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
from app.domains.evaluation.test_cases import HiddenTestCase, HiddenTestSuite, VisibleTestCase
from app.domains.scoring.configuration import (
    EfficiencyThresholds,
    EfficiencyTier,
    ScoringConfiguration,
    StarThresholds,
)

_EXACT_MATCH = ExactMatchGraderConfig()
_SCORING = ScoringConfiguration(
    accuracy_weight=0.8,
    efficiency_weight=0.2,
    efficiency_thresholds=EfficiencyThresholds(
        tiers=(
            EfficiencyTier(max_tokens=60, score=100),
            EfficiencyTier(max_tokens=100, score=90),
            EfficiencyTier(max_tokens=150, score=75),
            EfficiencyTier(max_tokens=250, score=60),
        ),
        score_above_max=40,
    ),
    star_thresholds=StarThresholds(
        one_star=70,
        two_stars=90,
        three_stars=100,
        three_star_max_prompt_tokens=60,
    ),
)


def _model_config(slug: str, max_output_tokens: int = 16) -> ModelConfiguration:
    return ModelConfiguration(
        model_id="openai/gpt-oss-20b",
        temperature=0,
        max_output_tokens=max_output_tokens,
        configuration_version=f"{slug}-model-v1",
        system_wrapper=(
            "Apply the player's instruction to the next user message, which contains the "
            "test input. Do not add facts that are not present in that input."
        ),
    )


def _playable(
    *,
    slug: str,
    order: int,
    title: str,
    description: str,
    objective: str,
    constraints: tuple[str, ...],
    difficulty: Difficulty,
    examples: tuple[tuple[str, str, str], ...],
    visible: tuple[tuple[str, str], ...],
    max_output_tokens: int = 16,
) -> PlayableChallenge:
    challenge_id = f"control-{slug}"
    return PlayableChallenge(
        challenge=Challenge(
            id=challenge_id,
            slug=slug,
            track=ChallengeTrack.CONTROL,
            order=order,
            current_version_id="1",
        ),
        version=ChallengeVersion(
            version_id="1",
            challenge_id=challenge_id,
            title=title,
            description=description,
            objective=objective,
            constraints=constraints,
            difficulty=difficulty,
            visible_examples=tuple(
                VisibleExample(input=input_value, expected_output=expected, explanation=explanation)
                for input_value, expected, explanation in examples
            ),
            visible_test_cases=tuple(
                VisibleTestCase(
                    id=f"visible-{index}",
                    input=input_value,
                    expected_output=expected,
                    grader_config=_EXACT_MATCH,
                )
                for index, (input_value, expected) in enumerate(visible, start=1)
            ),
            prompt_token_limit=300,
            evaluation_config=EvaluationConfiguration(default_grader=_EXACT_MATCH),
            scoring_config=_SCORING,
            model_config=_model_config(slug, max_output_tokens),
            publication_state=PublicationState.PUBLISHED,
        ),
    )


EXACT_OUTPUT_CHALLENGE = _playable(
    slug="exact-output",
    order=1,
    title="Exact Output",
    description="Constrain a model to report whether a service is currently available.",
    objective="Return exactly YES when the service is available, otherwise return exactly NO.",
    constraints=(
        "Return only YES or NO in uppercase.",
        "Do not include punctuation, explanation, or formatting.",
        "Judge current availability from the supplied statement.",
    ),
    difficulty=Difficulty.EASY,
    examples=(
        ("The dashboard reports that the service is online.", "YES", "The service is available."),
        ("The service is offline during an active outage.", "NO", "The service is unavailable."),
    ),
    visible=(
        ("The status page says all systems are operational.", "YES"),
        ("Scheduled maintenance is currently preventing customer logins.", "NO"),
        ("The API is responding normally with no reported outage.", "YES"),
    ),
    max_output_tokens=8,
)

OUTPUT_RESTRICTIONS_CHALLENGE = _playable(
    slug="output-restrictions",
    order=2,
    title="Output Restrictions",
    description="Return one permitted decision label without extra text.",
    objective="Output exactly APPROVE or REJECT according to the decision stated in the input.",
    constraints=(
        "Return only APPROVE or REJECT in uppercase.",
        "Follow the explicitly stated final decision.",
        "Do not add punctuation, formatting, or explanation.",
    ),
    difficulty=Difficulty.EASY,
    examples=(
        ("Review complete. Final decision: approve.", "APPROVE", "Use the stated decision."),
        (
            "The request was considered. Final decision: reject.",
            "REJECT",
            "Use the stated decision.",
        ),
    ),
    visible=(
        ("Initial concerns were resolved. Final decision: approve.", "APPROVE"),
        ("The proposal looked promising, but the final decision is reject.", "REJECT"),
        ("Final decision: approve. No further commentary is needed.", "APPROVE"),
    ),
)

FORMATTING_RULES_CHALLENGE = _playable(
    slug="formatting-rules",
    order=3,
    title="Formatting Rules",
    description="Transform a simple readiness decision into an exact key-value format.",
    objective="Return exactly STATUS=READY or STATUS=WAIT from the stated deployment status.",
    constraints=(
        "Use the exact prefix STATUS=.",
        "Use READY only when deployment is explicitly ready; otherwise use WAIT.",
        "Return one line with no spaces, punctuation, or explanation.",
    ),
    difficulty=Difficulty.MEDIUM,
    examples=(
        ("Deployment status: ready.", "STATUS=READY", "Apply the required key-value format."),
        ("Deployment status: waiting for review.", "STATUS=WAIT", "Not ready maps to WAIT."),
    ),
    visible=(
        ("All checks passed. Deployment status: ready.", "STATUS=READY"),
        ("The build passed, but deployment status is waiting for approval.", "STATUS=WAIT"),
        ("Deployment status: blocked by a missing review.", "STATUS=WAIT"),
    ),
)

MULTIPLE_CONSTRAINTS_CHALLENGE = _playable(
    slug="multiple-constraints",
    order=4,
    title="Multiple Constraints",
    description="Combine availability and urgency into one strictly formatted answer.",
    objective="Return availability and priority as YES|LOW, YES|HIGH, NO|LOW, or NO|HIGH.",
    constraints=(
        "The first value is YES when available and NO when unavailable.",
        "The second value is HIGH when urgency is urgent and LOW otherwise.",
        "Separate values with one vertical bar and return no other text.",
    ),
    difficulty=Difficulty.HARD,
    examples=(
        ("Service: available. Urgency: routine.", "YES|LOW", "Both fields use the exact format."),
        ("Service: unavailable. Urgency: urgent.", "NO|HIGH", "Both constraints are represented."),
    ),
    visible=(
        ("Service: available. Urgency: urgent.", "YES|HIGH"),
        ("Service: unavailable. Urgency: routine.", "NO|LOW"),
        ("Service: available. Urgency: routine.", "YES|LOW"),
    ),
)

CONTROL_BOSS_CHALLENGE = _playable(
    slug="control-boss",
    order=5,
    title="Control Boss",
    description="Satisfy several simultaneous output-control rules under distracting context.",
    objective="Return exactly RESULT=<YES|NO>;LEVEL=<LOW|HIGH> from the final status and priority.",
    constraints=(
        "Use the final stated service status, ignoring earlier superseded status.",
        "Use HIGH only for urgent priority and LOW for routine priority.",
        "Use exact uppercase keys, equals signs, semicolon, and no spaces or extra text.",
    ),
    difficulty=Difficulty.BOSS,
    examples=(
        (
            "Earlier offline; final status: available. Priority: urgent.",
            "RESULT=YES;LEVEL=HIGH",
            "The final status supersedes earlier context.",
        ),
        (
            "Earlier online; final status: unavailable. Priority: routine.",
            "RESULT=NO;LEVEL=LOW",
            "Use final status and exact formatting.",
        ),
    ),
    visible=(
        ("Final status: available. Priority: routine.", "RESULT=YES;LEVEL=LOW"),
        (
            "It was available earlier. Final status: unavailable. Priority: urgent.",
            "RESULT=NO;LEVEL=HIGH",
        ),
        (
            "It was offline earlier. Final status: available. Priority: urgent.",
            "RESULT=YES;LEVEL=HIGH",
        ),
    ),
    max_output_tokens=24,
)

CONTROL_CHALLENGES = (
    EXACT_OUTPUT_CHALLENGE,
    OUTPUT_RESTRICTIONS_CHALLENGE,
    FORMATTING_RULES_CHALLENGE,
    MULTIPLE_CONSTRAINTS_CHALLENGE,
    CONTROL_BOSS_CHALLENGE,
)


def _hidden_suite(expected_cases: tuple[tuple[str, str], ...]) -> HiddenTestSuite:
    return HiddenTestSuite(
        challenge_version_id="1",
        test_cases=tuple(
            HiddenTestCase(
                id=f"hidden-{index}",
                input=input_value,
                expected_output=expected,
                grader_config=_EXACT_MATCH,
            )
            for index, (input_value, expected) in enumerate(expected_cases, start=1)
        ),
    )


CONTROL_HIDDEN_TEST_SUITES = {
    "control-exact-output": _hidden_suite(
        (
            ("The customer portal is online and accepting sign-ins now.", "YES"),
            ("The service is currently offline while engineers restore access.", "NO"),
            ("Maintenance begins tomorrow; service is operating normally today.", "YES"),
            ("Maintenance has finished and full service has been restored.", "YES"),
            ("Emergency maintenance is underway and requests cannot be processed.", "NO"),
            ("Health checks are failing and the API cannot serve requests.", "NO"),
        )
    ),
    "control-output-restrictions": _hidden_suite(
        (
            ("The review was lengthy. Final decision: approve.", "APPROVE"),
            ("Final decision: reject.", "REJECT"),
            ("A draft said reject; final decision: approve.", "APPROVE"),
            ("The committee met twice. Final decision: reject.", "REJECT"),
            ("Approved in principle. Final decision: approve.", "APPROVE"),
            ("Earlier approval was withdrawn. Final decision: reject.", "REJECT"),
        )
    ),
    "control-formatting-rules": _hidden_suite(
        (
            ("Deployment status: ready.", "STATUS=READY"),
            ("Deployment status: awaiting tests.", "STATUS=WAIT"),
            ("Reviews finished; deployment status: ready.", "STATUS=READY"),
            ("Deployment status: blocked.", "STATUS=WAIT"),
            ("The plan changed. Deployment status: waiting for approval.", "STATUS=WAIT"),
            ("All gates are complete. Deployment status: ready.", "STATUS=READY"),
        )
    ),
    "control-multiple-constraints": _hidden_suite(
        (
            ("Service: available. Urgency: routine.", "YES|LOW"),
            ("Service: available. Urgency: urgent.", "YES|HIGH"),
            ("Service: unavailable. Urgency: routine.", "NO|LOW"),
            ("Service: unavailable. Urgency: urgent.", "NO|HIGH"),
            ("Urgency: urgent. Service: available.", "YES|HIGH"),
            ("Urgency: routine. Service: unavailable.", "NO|LOW"),
        )
    ),
    "control-control-boss": _hidden_suite(
        (
            ("Final status: available. Priority: routine.", "RESULT=YES;LEVEL=LOW"),
            ("Final status: unavailable. Priority: urgent.", "RESULT=NO;LEVEL=HIGH"),
            (
                "Earlier unavailable; final status: available. Priority: urgent.",
                "RESULT=YES;LEVEL=HIGH",
            ),
            (
                "Earlier available; final status: unavailable. Priority: routine.",
                "RESULT=NO;LEVEL=LOW",
            ),
            ("Final status: available. Priority: urgent.", "RESULT=YES;LEVEL=HIGH"),
            ("Final status: unavailable. Priority: routine.", "RESULT=NO;LEVEL=LOW"),
        )
    ),
}

EXACT_OUTPUT_HIDDEN_TEST_SUITE = CONTROL_HIDDEN_TEST_SUITES["control-exact-output"]
