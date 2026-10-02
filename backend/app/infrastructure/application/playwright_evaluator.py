import asyncio
import os
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Route, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from app.domains.application.errors import ApplicationEnvironmentError
from app.domains.application.models import (
    ApplicationChallengeConfig,
    Box,
    ElementMetrics,
    LayoutMetrics,
)
from app.domains.application.packages import ApplicationPackage
from app.domains.application.ports import ApplicationInspection, Workspace
from app.domains.execution.models import BuildArtifact, BuildStatus, ScreenshotArtifact
from app.infrastructure.application.process import run_predefined_command, sanitize_log

# Only this trusted measurement code executes. Selectors are arguments, never source strings.
_MEASURE_SCRIPT = """
(selectors) => {
  const elements = {};
  const pendingHits = [];
  window.scrollTo(0, 0);
  for (const selector of selectors) {
    const matches = Array.from(document.querySelectorAll(selector)).slice(0, 21);
    elements[selector] = matches.map(element => {
      const rect = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      let visible = rect.width > 0 && rect.height > 0;
      for (let parent = element; parent; parent = parent.parentElement) {
        const s = getComputedStyle(parent);
        visible = visible && s.visibility !== 'hidden' && s.display !== 'none'
          && Number(s.opacity) > 0;
      }
      const result = {
        box: {x: rect.left, y: rect.top, width: rect.width, height: rect.height, visible},
        tag: element.tagName.toLowerCase(), href: element.getAttribute('href'), hit: false,
        text: element.textContent.replace(/\\s+/g, ' ').trim(),
        background: style.backgroundColor, border_color: style.borderTopColor,
        border_width: parseFloat(style.borderTopWidth) || 0,
        disabled: element.matches(':disabled') || element.getAttribute('aria-disabled') === 'true',
      };
      pendingHits.push([element, result]);
      return result;
    });
  }
  const metrics = {viewport_width: innerWidth, viewport_height: innerHeight,
    scroll_width: document.documentElement.scrollWidth, elements};
  // Snapshot all geometry before scrolling for hit tests.
  for (const [element, result] of pendingHits) {
    if (!['a', 'button'].includes(result.tag)) continue;
    element.scrollIntoView({block: 'center', inline: 'center'});
    const rect = element.getBoundingClientRect();
    const hit = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2);
    result.hit = Boolean(hit && (hit === element || element.contains(hit)));
  }
  window.scrollTo(0, 0);
  return metrics;
}
"""


def _layout(data: dict) -> LayoutMetrics:
    return LayoutMetrics(
        viewport_width=data["viewport_width"],
        viewport_height=data["viewport_height"],
        scroll_width=data["scroll_width"],
        elements={
            selector: tuple(ElementMetrics(**{**e, "box": Box(**e["box"])}) for e in elements)
            for selector, elements in data["elements"].items()
        },
    )


def _url_path(url: str) -> Path | None:
    parsed = urlparse(url)
    if parsed.scheme != "file" or parsed.netloc not in ("", "localhost"):
        return None
    return Path(url2pathname(unquote(parsed.path))).resolve()


class PlaywrightApplicationEvaluator:
    """Fixed build and static browser measurement, confined to local build output."""

    def __init__(self, browser_channel: str | None = None) -> None:
        self._browser_channel = browser_channel

    async def inspect(
        self, workspace: Workspace, config: ApplicationChallengeConfig, package: ApplicationPackage
    ) -> ApplicationInspection:
        package.validate(config)
        from app.domains.application.sandbox import ExecutionMode, SandboxUnavailableError

        if config.execution_mode != ExecutionMode.STATIC:
            raise SandboxUnavailableError()
        return await asyncio.to_thread(self._inspect, workspace.root, config, package)

    def _inspect(
        self, root: Path, config: ApplicationChallengeConfig, package: ApplicationPackage
    ) -> ApplicationInspection:
        limits = config.limits
        process = run_predefined_command(config.build_command, root, limits.build_timeout_seconds)
        if process.timed_out:
            raise ApplicationEnvironmentError("The project build did not finish in time.")
        log = sanitize_log(process.output, root, limits.max_log_chars)
        page = (root / config.build_output).resolve()
        if process.exit_code != 0 or not page.is_relative_to(root) or not page.is_file():
            return ApplicationInspection(BuildArtifact(BuildStatus.FAILED, log), {}, ())
        layouts, screenshots = self._measure(page, config, package)
        return ApplicationInspection(BuildArtifact(BuildStatus.PASSED, log), layouts, screenshots)

    def _measure(
        self, page: Path, config: ApplicationChallengeConfig, package: ApplicationPackage
    ) -> tuple[dict[str, LayoutMetrics], tuple[ScreenshotArtifact, ...]]:
        allowed_root = page.parent
        timeout_ms = config.limits.browser_timeout_seconds * 1000

        def only_build_output(route: Route) -> None:
            path = _url_path(route.request.url)
            if path is not None and path.is_relative_to(allowed_root):
                route.continue_()
            else:
                route.abort()

        layouts = {}
        screenshots = []
        environment = {key: os.environ[key] for key in ("SYSTEMROOT",) if key in os.environ}
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(
                    channel=self._browser_channel, env=environment, timeout=timeout_ms
                )
                try:
                    for view in config.viewports:
                        context = browser.new_context(
                            viewport={"width": view.width, "height": view.height},
                            device_scale_factor=1,
                            java_script_enabled=False,
                            service_workers="block",
                            accept_downloads=False,
                        )
                        try:
                            context.route("**/*", only_build_output)
                            tab = context.new_page()
                            tab.set_default_timeout(timeout_ms)
                            tab.goto(page.as_uri(), wait_until="load")
                            if view.screenshot:
                                screenshots.append(
                                    ScreenshotArtifact(
                                        view.id,
                                        view.width,
                                        view.height,
                                        tab.screenshot(type="png"),
                                        view.label,
                                    )
                                )
                            layouts[view.id] = _layout(
                                tab.evaluate(_MEASURE_SCRIPT, package.selectors)
                            )
                        finally:
                            context.close()
                finally:
                    browser.close()
        except PlaywrightTimeoutError:
            raise ApplicationEnvironmentError(
                "The browser checks did not finish in time."
            ) from None
        except PlaywrightError:
            raise ApplicationEnvironmentError("The browser environment is unavailable.") from None
        return layouts, tuple(screenshots)
