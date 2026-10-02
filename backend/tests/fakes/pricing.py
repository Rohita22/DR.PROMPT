"""Pricing Grid deterministic agent fixture; no provider calls."""

from app.infrastructure.application.starter_projects import APPLICATION_CHALLENGES_ROOT
from tests.fakes.application import edit_output

PRICING_STARTER = APPLICATION_CHALLENGES_ROOT / "pricing_grid" / "starter"
SOLUTION = """
.plans { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 20px; }
.plan { width: auto; margin: 0; display: flex; flex-direction: column; }
.plan-action { margin-top: auto; }
.plan ul { margin-bottom: 24px; }
[data-plan="pro"] { background: #d4e7b5; border: 2px solid #3c6535; }
@media (max-width: 760px) {
 .plans { grid-template-columns: minmax(0, 1fr); }
 .pricing { padding: 32px 20px; }
 h1 { font-size: 36px; }
}
"""


def pricing_output(appendix: str = SOLUTION) -> str:
    return edit_output(
        **{
            "src/styles.css": (PRICING_STARTER / "src/styles.css").read_text(encoding="utf-8-sig")
            + appendix
        }
    )
