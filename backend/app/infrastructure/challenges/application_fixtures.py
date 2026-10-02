"""The repository-controlled APPLICATION challenges, defined in repository-controlled code.

Hero and Pricing occupy orders 6 and 7 in CONTROL, reusing the existing linear
unlocking rules unchanged: Hero follows the boss, and Pricing follows Hero.
"""

from dataclasses import replace

from app.domains.challenges.models import (
    Challenge,
    ChallengeTrack,
    ChallengeType,
    ChallengeVersion,
    Difficulty,
    PlayableChallenge,
    PublicationState,
)
from app.domains.evaluation.configuration import (
    EvaluationConfiguration,
    ExactMatchGraderConfig,
    ModelConfiguration,
    ReasoningEffort,
)
from app.domains.scoring.configuration import (
    EfficiencyThresholds,
    EfficiencyTier,
    ScoringConfiguration,
    StarThresholds,
)
from app.infrastructure.application.starter_projects import StarterProjectRepository

_AGENT_SYSTEM_WRAPPER = (
    "You are a careful front-end coding agent working on a small static website. "
    "The user message describes what to change. Edit only the supplied editable files, "
    "preserve unrelated behavior, and do not invent additional files. Return only the "
    "requested structured edit data, with complete replacement contents for every changed file."
)

RESPONSIVE_HERO_CONFIG = StarterProjectRepository().load("responsive-hero").defaults
PRICING_GRID_CONFIG = StarterProjectRepository().load("pricing-grid").defaults

RESPONSIVE_HERO_CHALLENGE = PlayableChallenge(
    challenge=Challenge(
        id="control-responsive-hero",
        slug="responsive-hero",
        track=ChallengeTrack.CONTROL,
        order=6,
        current_version_id="1",
    ),
    version=ChallengeVersion(
        version_id="1",
        challenge_id="control-responsive-hero",
        title="Responsive Hero",
        description=(
            "An AI coding agent will edit a small landing page for you. You never touch "
            "the code: your prompt is the agent's only instruction."
        ),
        objective=(
            "Instruct the coding agent to turn the stacked hero section into a responsive "
            "two-column layout: content on the left and the illustration on the right on "
            "desktop, collapsing into a clean single column on phones."
        ),
        constraints=(
            "Desktop (1280px): heading, copy, and CTA on the left; illustration on the right.",
            "The call-to-action stays visible without scrolling on desktop.",
            "Phones (390px): a single readable column with no horizontal scrolling.",
            "The header, navigation, features, and footer must stay exactly as they are.",
            "Keep the existing data-role attributes on the hero elements.",
            "The agent can edit only src/index.html and src/styles.css; no scripts.",
        ),
        difficulty=Difficulty.HARD,
        visible_examples=(),
        visible_test_cases=(),
        prompt_token_limit=400,
        # Unused by APPLICATION execution; ChallengeVersion requires a default grader.
        evaluation_config=EvaluationConfiguration(default_grader=ExactMatchGraderConfig()),
        scoring_config=ScoringConfiguration(
            accuracy_weight=0.8,
            efficiency_weight=0.2,
            efficiency_thresholds=EfficiencyThresholds(
                tiers=(
                    EfficiencyTier(max_tokens=80, score=100),
                    EfficiencyTier(max_tokens=150, score=90),
                    EfficiencyTier(max_tokens=250, score=75),
                    EfficiencyTier(max_tokens=400, score=60),
                ),
                score_above_max=40,
            ),
            star_thresholds=StarThresholds(
                one_star=70,
                two_stars=85,
                three_stars=100,
                three_star_max_prompt_tokens=150,
            ),
        ),
        model_config=ModelConfiguration(
            model_id="openai/gpt-oss-20b",
            temperature=0,
            max_output_tokens=8192,
            configuration_version="responsive-hero-agent-v2",
            system_wrapper=_AGENT_SYSTEM_WRAPPER,
            reasoning_effort=ReasoningEffort.LOW,
        ),
        publication_state=PublicationState.PUBLISHED,
        challenge_type=ChallengeType.APPLICATION,
        application_config=RESPONSIVE_HERO_CONFIG,
    ),
)


PRICING_GRID_CHALLENGE = PlayableChallenge(
    challenge=Challenge(
        id="control-pricing-grid",
        slug="pricing-grid",
        track=ChallengeTrack.CONTROL,
        order=7,
        current_version_id="1",
    ),
    version=replace(
        RESPONSIVE_HERO_CHALLENGE.version,
        challenge_id="control-pricing-grid",
        title="Pricing Grid",
        description="Give an AI coding agent clear instructions to redesign a pricing section. "
        "Your prompt is its only brief.",
        objective="Turn the pricing section into a responsive three-card layout. "
        "Make Pro visually prominent, preserve all pricing text and actions, "
        "and stack the cards cleanly on phones without changing the header or footer.",
        constraints=(
            "Desktop (1280px): three readable pricing cards in one row, "
            "each at least 20% of the viewport width.",
            "Make Pro distinct with a different background or a contrasting border "
            "at least 2px wide.",
            "Phones (390px and narrower): stack the cards with no horizontal scrolling.",
            "Keep Starter, Pro, Business, all prices, feature text, "
            "and call-to-action links visible and usable.",
            "Keep the header, footer, and existing data attributes unchanged.",
            "The agent can edit only src/index.html and src/styles.css; no scripts.",
        ),
        model_config=replace(
            RESPONSIVE_HERO_CHALLENGE.version.model_config,
            configuration_version="pricing-grid-agent-v1",
        ),
        application_config=PRICING_GRID_CONFIG,
    ),
)

APPLICATION_CHALLENGES = (RESPONSIVE_HERO_CHALLENGE, PRICING_GRID_CHALLENGE)


def _interactive_challenge(
    slug: str, title: str, order: int, objective: str, constraints: tuple[str, ...]
):
    from app.infrastructure.application.starter_projects import StarterProjectRepository

    config = StarterProjectRepository().load(slug).defaults
    return PlayableChallenge(
        challenge=Challenge(
            id=f"control-{slug}",
            slug=slug,
            track=ChallengeTrack.CONTROL,
            order=order,
            current_version_id="1",
        ),
        version=replace(
            RESPONSIVE_HERO_CHALLENGE.version,
            challenge_id=f"control-{slug}",
            title=title,
            description="Instruct a coding agent to repair a small interactive app.",
            objective=objective,
            constraints=constraints,
            application_config=config,
            model_config=replace(
                RESPONSIVE_HERO_CHALLENGE.version.model_config,
                configuration_version=f"{slug}-agent-v1",
                system_wrapper=(
                    "You are a careful React/TypeScript coding agent. "
                    "Follow the player's instructions. Return only structured replacements "
                    "for the provided editable files."
                ),
            ),
        ),
    )


BROKEN_SIGNUP_CHALLENGE = _interactive_challenge(
    "broken-signup-validation",
    "Broken Signup Validation",
    8,
    "Fix signup validation while preserving the design and successful valid submission.",
    (
        "Trim email whitespace and require a complete email address, including "
        "a dotted domain. Plus-addresses are valid.",
        "Require a password of at least 8 characters; do not trim passwords.",
        "Show 'Enter a valid email address.' and 'Use at least 8 characters.' for invalid fields.",
        "Clear each error as the field is corrected. Valid submission shows 'Account created'.",
        "Keep keyboard submission, the layout, header and footer working. "
        "Edit only the declared source files.",
    ),
)
PRODUCT_FILTER_CHALLENGE = _interactive_challenge(
    "product-filter",
    "Product Filter",
    9,
    "Make category and search filters work together while preserving the design and product data.",
    (
        "Match product names case-insensitively and trim surrounding search whitespace.",
        "Combine category and search. All products removes only the category restriction.",
        "Clear filters resets both search and category and restores all six products.",
        "Show the existing no-results state when nothing matches. Preserve keyboard operation.",
        "Keep the original product names, prices, ordering, page layout, header and footer.",
    ),
)
EXECUTABLE_CHALLENGES = (BROKEN_SIGNUP_CHALLENGE, PRODUCT_FILTER_CHALLENGE)
# Keep the existing static fixture tuple stable for regression clients.
ALL_APPLICATION_CHALLENGES = (*APPLICATION_CHALLENGES, *EXECUTABLE_CHALLENGES)
