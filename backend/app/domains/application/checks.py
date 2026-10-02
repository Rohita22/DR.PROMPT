"""Trusted, deterministic checks over explicit browser measurements; no browser code here."""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from types import MappingProxyType

from app.domains.application.errors import ApplicationConfigurationError
from app.domains.application.models import ElementMetrics, LayoutMetrics


@dataclass(frozen=True, slots=True)
class CheckParameters:
    viewports: tuple[str, ...] = ()
    selectors: tuple[str, ...] = ()
    count: int = 1
    min_width_ratio: float = 0
    max_width_ratio: float = 0
    tolerance: float = 2
    above_fold: bool = False
    texts: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    steps: tuple[dict, ...] = ()

    def __post_init__(self) -> None:
        if not 1 <= self.count <= 20 or not 0 <= self.min_width_ratio <= 1:
            raise ApplicationConfigurationError("Invalid check count or width ratio.")
        if not 0 <= self.max_width_ratio <= 1:
            raise ApplicationConfigurationError("Invalid maximum width ratio.")
        if not 0 <= self.tolerance <= 10:
            raise ApplicationConfigurationError("Invalid check tolerance.")
        if len(self.selectors) > 10 or any(not s or len(s) > 160 for s in self.selectors):
            raise ApplicationConfigurationError("Invalid measurement selector.")
        if any(tag not in {"header", "footer", "nav", "section"} for tag in self.tags):
            raise ApplicationConfigurationError("Invalid protected landmark.")
        for step in self.steps:
            if set(step) - {"action", "selector", "value", "count"} or step.get("action") not in {
                "fill",
                "select",
                "click",
                "press",
                "text",
                "count",
                "visible",
                "hidden",
                "attribute",
            }:
                raise ApplicationConfigurationError("Invalid interaction step.")
            if not isinstance(step.get("selector"), str) or len(step["selector"]) > 160:
                raise ApplicationConfigurationError("Invalid interaction selector.")
            if len(str(step.get("value", ""))) > 300:
                raise ApplicationConfigurationError("Interaction value exceeds bounds.")
        if len(self.steps) > 20:
            raise ApplicationConfigurationError("Too many interaction steps.")
        for name in ("viewports", "selectors", "texts", "tags", "steps"):
            object.__setattr__(self, name, tuple(getattr(self, name)))


@dataclass(frozen=True, slots=True)
class CheckDefinition:
    id: str
    implementation: str
    label: str
    parameters: CheckParameters = CheckParameters()


@dataclass(frozen=True, slots=True)
class ApplicationFacts:
    build_succeeded: bool
    protected_files_unchanged: bool
    starter_html: str
    result_html: str
    layouts: Mapping[str, LayoutMetrics]
    behavior_results: Mapping[str, bool] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ApplicationCheckResult:
    check_id: str
    passed: bool
    label: str
    message: str | None = None


def _elements(layout: LayoutMetrics, params: CheckParameters) -> tuple[ElementMetrics, ...]:
    return tuple(e for selector in params.selectors for e in layout.elements.get(selector, ()))


def _row(layout: LayoutMetrics, p: CheckParameters) -> bool:
    elements = _elements(layout, p)
    if len(elements) != p.count or not all(e.box.visible for e in elements):
        return False
    boxes = [e.box for e in elements]
    return (
        all(a.right <= b.x + p.tolerance for a, b in zip(boxes, boxes[1:], strict=False))
        and min(b.bottom for b in boxes) > max(b.y for b in boxes)
        and all(b.width >= layout.viewport_width * p.min_width_ratio for b in boxes)
    )


def _stack(layout: LayoutMetrics, p: CheckParameters) -> bool:
    elements = _elements(layout, p)
    if len(elements) != p.count or not all(e.box.visible for e in elements):
        return False
    boxes = sorted((e.box for e in elements), key=lambda b: b.y)
    # Hero's original readability rule applies to the first selected content element.
    return (
        all(a.bottom <= b.y + p.tolerance for a, b in zip(boxes, boxes[1:], strict=False))
        and (elements[0].box.width >= layout.viewport_width * p.min_width_ratio)
        and (
            not p.max_width_ratio
            or all(
                b.width <= layout.viewport_width * p.max_width_ratio + p.tolerance for b in boxes
            )
        )
    )


def _visible(layout: LayoutMetrics, p: CheckParameters) -> bool:
    elements = _elements(layout, p)
    return len(elements) == p.count and all(
        e.box.visible
        and (not p.above_fold or 0 <= e.box.y < e.box.bottom <= layout.viewport_height)
        for e in elements
    )


def _clickable(layout: LayoutMetrics, p: CheckParameters) -> bool:
    elements = _elements(layout, p)
    return len(elements) == p.count and all(
        e.box.visible
        and e.hit
        and not e.disabled
        and (e.tag == "button" or (e.tag == "a" and bool((e.href or "").strip())))
        for e in elements
    )


def _structure(layout: LayoutMetrics, p: CheckParameters) -> bool:
    # Selectors express required semantic relationships, never executable expressions.
    return all(len(layout.elements.get(selector, ())) == 1 for selector in p.selectors)


def _texts(layout: LayoutMetrics, p: CheckParameters) -> bool:
    elements = _elements(layout, p)
    return tuple(e.text for e in elements) == p.texts and all(e.box.visible for e in elements)


def _prominent(layout: LayoutMetrics, p: CheckParameters) -> bool:
    featured = layout.elements.get(p.selectors[0], ())
    peers = layout.elements.get(p.selectors[1], ())
    if len(featured) != 1 or len(peers) != p.count - 1:
        return False
    pro = featured[0]
    return pro.box.visible and all(
        peer.box.visible
        and (
            pro.background != peer.background
            or (pro.border_width >= 2 and pro.border_color != peer.border_color)
        )
        for peer in peers
    )


def _landmark_blocks(html: str, tags: tuple[str, ...]) -> list[str] | None:
    blocks = []
    for tag in tags:
        matches = re.findall(rf"<{tag}\b.*?</{tag}>", html, re.DOTALL | re.IGNORECASE)
        if len(matches) != 1:
            return None
        blocks.append(" ".join(matches[0].split()))
    return blocks


def landmarks_unchanged(starter_html: str, result_html: str, tags=("header", "footer")) -> bool:
    starter = _landmark_blocks(starter_html, tags)
    return starter is not None and starter == _landmark_blocks(result_html, tags)


def _layout_check(
    predicate: Callable[[LayoutMetrics, CheckParameters], bool],
) -> Callable[[ApplicationFacts, CheckParameters], bool]:
    def check(facts: ApplicationFacts, params: CheckParameters) -> bool:
        return all(
            viewport in facts.layouts
            and predicate(
                facts.layouts[viewport],
                params if viewport == params.viewports[0] else replace(params, above_fold=False),
            )
            for viewport in params.viewports
        )

    return check


class ApplicationCheckRegistry:
    """Per-instance immutable registry of trusted implementations and parameter contracts."""

    def __init__(self) -> None:
        self._checks = MappingProxyType(
            {
                "build_succeeds": lambda f, p: f.build_succeeded,
                "interaction": lambda f, p: False,
                "protected_files_unchanged": lambda f, p: f.protected_files_unchanged,
                "protected_markup_unchanged": lambda f, p: landmarks_unchanged(
                    f.starter_html, f.result_html, p.tags
                ),
                "horizontal_row": _layout_check(_row),
                "vertical_stack": _layout_check(_stack),
                "element_visible": _layout_check(_visible),
                "element_clickable": _layout_check(_clickable),
                "required_structure": _layout_check(_structure),
                "text_preserved": _layout_check(_texts),
                "link_destinations": _layout_check(
                    lambda layout, p: tuple(e.href for e in _elements(layout, p)) == p.texts
                ),
                "element_prominent": _layout_check(_prominent),
                "no_horizontal_overflow": _layout_check(
                    lambda layout, p: layout.scroll_width <= layout.viewport_width + 1
                ),
            }
        )

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(self._checks)

    def validate(self, check: CheckDefinition) -> None:
        kind, p = check.implementation, check.parameters
        if kind not in self._checks:
            raise ApplicationConfigurationError("Unknown trusted check implementation.")
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", check.id):
            raise ApplicationConfigurationError("Invalid check ID.")
        if not check.label.strip() or len(check.label) > 120:
            raise ApplicationConfigurationError("Invalid check label.")
        non_browser = {"build_succeeds", "protected_files_unchanged", "protected_markup_unchanged"}
        if kind not in non_browser and not p.viewports:
            raise ApplicationConfigurationError("Browser checks require viewports.")
        if kind not in non_browser | {"no_horizontal_overflow", "interaction"} and not p.selectors:
            raise ApplicationConfigurationError("Element checks require selectors.")
        if kind == "interaction" and not p.steps:
            raise ApplicationConfigurationError("Interactive checks require trusted steps.")
        if kind == "protected_markup_unchanged" and not p.tags:
            raise ApplicationConfigurationError("Protected markup requires landmark tags.")
        if kind in {"horizontal_row", "vertical_stack", "element_prominent"} and p.count < 2:
            raise ApplicationConfigurationError("Layout checks require multiple elements.")
        if kind == "element_prominent" and len(p.selectors) != 2:
            raise ApplicationConfigurationError("Prominence requires featured and peer selectors.")
        if kind in {"text_preserved", "link_destinations"} and len(p.texts) != p.count:
            raise ApplicationConfigurationError("Text check count must match expected content.")

    def evaluate(
        self,
        checks: tuple[CheckDefinition, ...],
        facts: ApplicationFacts,
    ) -> tuple[ApplicationCheckResult, ...]:
        results = []
        for check in checks:
            self.validate(check)
            passed = (
                facts.behavior_results.get(check.id, False)
                if check.implementation == "interaction"
                else self._checks[check.implementation](facts, check.parameters)
            )
            message = (
                None
                if passed
                else (
                    "Not measured because the page did not build."
                    if not facts.build_succeeded and check.parameters.viewports
                    else f"Requirement not met: {check.label}."
                )
            )
            results.append(ApplicationCheckResult(check.id, passed, check.label, message))
        return tuple(results)
