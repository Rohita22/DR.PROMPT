from collections.abc import Mapping
from typing import cast

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
    AllowedLabelGraderConfig,
    ArrayComparisonGraderConfig,
    CaseInsensitiveExactMatchGraderConfig,
    EvaluationConfiguration,
    ExactMatchGraderConfig,
    FieldComparisonGraderConfig,
    GraderConfiguration,
    GraderType,
    JsonSchemaGraderConfig,
    ModelConfiguration,
)
from app.domains.evaluation.test_cases import HiddenTestCase, HiddenTestSuite, VisibleTestCase
from app.domains.scoring.configuration import (
    EfficiencyThresholds,
    EfficiencyTier,
    ScoringConfiguration,
    StarThresholds,
)
from app.infrastructure.database.models import (
    ChallengeRow,
    ChallengeVersionRow,
    HiddenTestCaseRow,
    VisibleExampleRow,
    VisibleTestCaseRow,
)


def grader_config_to_data(config: GraderConfiguration) -> dict[str, object]:
    data: dict[str, object] = {"type": config.grader_type.value}
    if isinstance(config, AllowedLabelGraderConfig):
        data["allowed_labels"] = sorted(config.allowed_labels)
    elif isinstance(config, JsonSchemaGraderConfig):
        data["schema"] = dict(config.schema)
    elif isinstance(config, FieldComparisonGraderConfig):
        data["fields"] = list(config.fields)
    elif isinstance(config, ArrayComparisonGraderConfig):
        data["order_matters"] = config.order_matters
    return data


def grader_config_from_data(data: Mapping[str, object]) -> GraderConfiguration:
    grader_type = GraderType(str(data["type"]))
    if grader_type is GraderType.EXACT_MATCH:
        return ExactMatchGraderConfig()
    if grader_type is GraderType.CASE_INSENSITIVE_EXACT_MATCH:
        return CaseInsensitiveExactMatchGraderConfig()
    if grader_type is GraderType.ALLOWED_LABEL:
        return AllowedLabelGraderConfig(frozenset(cast(list[str], data["allowed_labels"])))
    if grader_type is GraderType.JSON_SCHEMA:
        return JsonSchemaGraderConfig(cast(Mapping[str, object], data["schema"]))
    if grader_type is GraderType.FIELD_COMPARISON:
        return FieldComparisonGraderConfig(tuple(cast(list[str], data["fields"])))
    return ArrayComparisonGraderConfig(bool(data.get("order_matters", True)))


def model_config_to_data(config: ModelConfiguration) -> dict[str, object]:
    return {
        "model_id": config.model_id,
        "temperature": config.temperature,
        "max_output_tokens": config.max_output_tokens,
        "configuration_version": config.configuration_version,
        "system_wrapper": config.system_wrapper,
    }


def model_config_from_data(data: Mapping[str, object]) -> ModelConfiguration:
    return ModelConfiguration(
        model_id=str(data["model_id"]),
        temperature=float(data["temperature"]),
        max_output_tokens=int(data["max_output_tokens"]),
        configuration_version=str(data["configuration_version"]),
        system_wrapper=(str(data["system_wrapper"]) if data.get("system_wrapper") else None),
    )


def scoring_config_to_data(config: ScoringConfiguration) -> dict[str, object]:
    return {
        "accuracy_weight": config.accuracy_weight,
        "efficiency_weight": config.efficiency_weight,
        "efficiency_thresholds": {
            "tiers": [
                {"max_tokens": tier.max_tokens, "score": tier.score}
                for tier in config.efficiency_thresholds.tiers
            ],
            "score_above_max": config.efficiency_thresholds.score_above_max,
        },
        "star_thresholds": {
            "one_star": config.star_thresholds.one_star,
            "two_stars": config.star_thresholds.two_stars,
            "three_stars": config.star_thresholds.three_stars,
            "three_star_max_prompt_tokens": (config.star_thresholds.three_star_max_prompt_tokens),
        },
    }


def scoring_config_from_data(data: Mapping[str, object]) -> ScoringConfiguration:
    efficiency = cast(Mapping[str, object], data["efficiency_thresholds"])
    stars = cast(Mapping[str, object], data["star_thresholds"])
    tiers = cast(list[Mapping[str, object]], efficiency["tiers"])
    max_tokens = stars.get("three_star_max_prompt_tokens")
    return ScoringConfiguration(
        accuracy_weight=float(data["accuracy_weight"]),
        efficiency_weight=float(data["efficiency_weight"]),
        efficiency_thresholds=EfficiencyThresholds(
            tiers=tuple(
                EfficiencyTier(int(tier["max_tokens"]), float(tier["score"])) for tier in tiers
            ),
            score_above_max=float(efficiency["score_above_max"]),
        ),
        star_thresholds=StarThresholds(
            one_star=float(stars["one_star"]),
            two_stars=float(stars["two_stars"]),
            three_stars=float(stars["three_stars"]),
            three_star_max_prompt_tokens=(int(max_tokens) if max_tokens is not None else None),
        ),
    )


def playable_challenge_from_rows(
    challenge: ChallengeRow,
    version: ChallengeVersionRow,
    examples: list[VisibleExampleRow],
    tests: list[VisibleTestCaseRow],
) -> PlayableChallenge:
    default_grader = grader_config_from_data(version.evaluation_config["default_grader"])
    return PlayableChallenge(
        challenge=Challenge(
            id=challenge.id,
            slug=challenge.slug,
            track=ChallengeTrack(challenge.track),
            order=challenge.sort_order,
            current_version_id=challenge.current_version,
        ),
        version=ChallengeVersion(
            version_id=version.version,
            challenge_id=challenge.id,
            title=version.title,
            description=version.description,
            objective=version.objective,
            constraints=tuple(version.constraints),
            difficulty=Difficulty(version.difficulty),
            visible_examples=tuple(
                VisibleExample(row.input, row.expected_output, row.explanation) for row in examples
            ),
            visible_test_cases=tuple(
                VisibleTestCase(
                    id=row.test_id,
                    input=row.input,
                    expected_output=row.expected_output,
                    grader_config=grader_config_from_data(row.evaluation_config),
                )
                for row in tests
            ),
            prompt_token_limit=version.prompt_token_limit,
            evaluation_config=EvaluationConfiguration(default_grader=default_grader),
            scoring_config=scoring_config_from_data(version.scoring_config),
            model_config=model_config_from_data(version.model_config),
            publication_state=PublicationState(version.publication_state),
        ),
    )


def hidden_suite_from_rows(
    challenge_version: str,
    tests: list[HiddenTestCaseRow],
) -> HiddenTestSuite | None:
    if not tests:
        return None
    return HiddenTestSuite(
        challenge_version_id=challenge_version,
        test_cases=tuple(
            HiddenTestCase(
                id=row.test_id,
                input=row.input,
                expected_output=row.expected_output,
                grader_config=grader_config_from_data(row.evaluation_config),
            )
            for row in tests
        ),
    )
