import json
from pathlib import Path
p=Path('application_challenges/broken_signup_validation/starter/package-lock.json');data=json.loads(p.read_text(encoding='utf-8-sig'));data['name']='product-filter';data['packages']['']['name']='product-filter';Path('application_challenges/product_filter/starter/package-lock.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
p=Path('app/core/config/settings.py');s=p.read_text(encoding='utf-8');s=s.replace('    application_browser_channel:', '    application_sandbox_backend: str = Field(default="disabled", pattern="^(disabled|docker-rootless)$", validation_alias="APPLICATION_SANDBOX_BACKEND")\n    application_sandbox_image: str = Field(default="", validation_alias="APPLICATION_SANDBOX_IMAGE")\n\n    application_browser_channel:');p.write_text(s,encoding='utf-8')
p=Path('app/api/dependencies.py');s=p.read_text(encoding='utf-8');s='from app.infrastructure.application.sandbox import configured_sandbox\n'+s;s=s.replace('PlaywrightApplicationEvaluator(settings.application_browser_channel),\n            StarterProjectRepository(),','PlaywrightApplicationEvaluator(settings.application_browser_channel),\n            StarterProjectRepository(),\n            configured_sandbox(settings),');s=s.replace('PlaywrightApplicationEvaluator(settings.application_browser_channel),\n                StarterProjectRepository(),','PlaywrightApplicationEvaluator(settings.application_browser_channel),\n                StarterProjectRepository(),\n                configured_sandbox(settings),');s+='\n\ndef get_application_sandbox(settings: Annotated[Settings, Depends(get_settings)]):\n    return configured_sandbox(settings)\n';p.write_text(s,encoding='utf-8')
p=Path('app/api/schemas/admin.py');s=p.read_text(encoding='utf-8');s=s.replace('class ApplicationPackageResponse(BaseModel):','class ApplicationPackageResponse(BaseModel):\n    execution_mode: str = "static"\n    runtime_metadata: dict[str, object] | None = None');s=s.replace('id=package.id,','execution_mode=package.defaults.execution_mode.value,\n            runtime_metadata=__import__("dataclasses").asdict(package.sandbox) if package.sandbox else None,\n            id=package.id,');p.write_text(s,encoding='utf-8')
p=Path('app/api/schemas/challenges.py');s=p.read_text(encoding='utf-8');s=s.replace('    starter_preview_viewports: list[str]','    starter_preview_viewports: list[str]\n    execution_mode: str = "static"\n    available: bool = True');s=s.replace('editable_files=list(playable.version.application_config.editable_files),','execution_mode=playable.version.application_config.execution_mode.value,\n                    editable_files=list(playable.version.application_config.editable_files),');p.write_text(s,encoding='utf-8')
p=Path('app/api/routes/challenges.py');s=p.read_text(encoding='utf-8');s=s.replace('    get_challenge_detail_use_case,','    get_challenge_detail_use_case,\n    get_application_sandbox,');s=s.replace('    use_case: Annotated[GetChallengeDetailUseCase, Depends(get_challenge_detail_use_case)],','    use_case: Annotated[GetChallengeDetailUseCase, Depends(get_challenge_detail_use_case)],\n    sandbox=Depends(get_application_sandbox),');s=s.replace('    return ChallengeDetailResponse.from_domain(playable, access)','    response = ChallengeDetailResponse.from_domain(playable, access)\n    if response.application and response.application.execution_mode == "sandboxed_executable":\n        response.application.available = (await sandbox.capability()).available\n    return response');p.write_text(s,encoding='utf-8')
p=Path('app/infrastructure/application/playwright_evaluator.py');s=p.read_text(encoding='utf-8');needle='        package.validate(config)';s=s.replace(needle,needle+'\n        from app.domains.application.sandbox import ExecutionMode, SandboxUnavailableError\n        if config.execution_mode != ExecutionMode.STATIC:\n            raise SandboxUnavailableError()');p.write_text(s,encoding='utf-8')
p=Path('app/infrastructure/challenges/application_fixtures.py');s=p.read_text(encoding='utf-8');s += '''

def _interactive_challenge(slug: str, title: str, order: int, objective: str, constraints: tuple[str, ...]):
    from app.infrastructure.application.starter_projects import StarterProjectRepository
    config = StarterProjectRepository().load(slug).defaults
    return PlayableChallenge(
        challenge=Challenge(id=f"control-{slug}",slug=slug,track=ChallengeTrack.CONTROL,
                            order=order,current_version_id="1"),
        version=replace(RESPONSIVE_HERO_CHALLENGE.version,
                        challenge_id=f"control-{slug}",title=title,
                        description="Instruct a coding agent to repair a small interactive app.",
                        objective=objective,constraints=constraints,application_config=config,
                        model_config=replace(RESPONSIVE_HERO_CHALLENGE.version.model_config,
                            configuration_version=f"{slug}-agent-v1",
                            system_wrapper="You are a careful React/TypeScript coding agent. Follow the player's instructions. Return only structured replacements for the provided editable files.")),
    )


BROKEN_SIGNUP_CHALLENGE = _interactive_challenge(
    "broken-signup-validation", "Broken Signup Validation", 8,
    "Fix signup validation while preserving the design and successful valid submission.",
    ("Trim email whitespace and require a complete email address, including a dotted domain. Plus-addresses are valid.",
     "Require a password of at least 8 characters; do not trim passwords.",
     "Show 'Enter a valid email address.' and 'Use at least 8 characters.' for invalid fields.",
     "Clear each error as the field is corrected. Valid submission shows 'Account created'.",
     "Keep keyboard submission, the layout, header and footer working. Edit only the declared source files."),
)
PRODUCT_FILTER_CHALLENGE = _interactive_challenge(
    "product-filter", "Product Filter", 9,
    "Make category and search filters work together while preserving the design and product data.",
    ("Match product names case-insensitively and trim surrounding search whitespace.",
     "Combine category and search. All products removes only the category restriction.",
     "Clear filters resets both search and category and restores all six products.",
     "Show the existing no-results state when nothing matches. Preserve keyboard operation.",
     "Keep the original product names, prices, ordering, page layout, header and footer."),
)
EXECUTABLE_CHALLENGES = (BROKEN_SIGNUP_CHALLENGE, PRODUCT_FILTER_CHALLENGE)
# Keep the existing static fixture tuple stable for regression clients.
ALL_APPLICATION_CHALLENGES = (*APPLICATION_CHALLENGES, *EXECUTABLE_CHALLENGES)
''';p.write_text(s,encoding='utf-8')
p=Path('app/infrastructure/database/seed.py');s=p.read_text(encoding='utf-8').replace('import APPLICATION_CHALLENGES','import ALL_APPLICATION_CHALLENGES').replace('for playable in APPLICATION_CHALLENGES:','for playable in ALL_APPLICATION_CHALLENGES:');p.write_text(s,encoding='utf-8')
