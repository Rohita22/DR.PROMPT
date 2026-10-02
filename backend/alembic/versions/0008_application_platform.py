"""Version the application configuration and preserve Hero's existing measurement policy.

Revision ID: 0008_application_platform
Revises: 0007_add_application_execution_guard
"""

from alembic import op

revision = "0008_application_platform"
down_revision = "0007_add_application_execution_guard"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        UPDATE challenge_versions
        SET application_config = application_config || '
{"schema_version": 1, "viewports": [
{"id": "desktop", "width": 1280, "height": 800, "label": "Desktop", "screenshot": true},
{"id": "wide", "width": 1440, "height": 900, "label": "Wide desktop", "screenshot": false},
{"id": "mobile", "width": 390, "height": 844, "label": "Phone", "screenshot": true},
{"id": "small", "width": 320, "height": 640, "label": "Narrow phone", "screenshot": false}]}'::jsonb
        WHERE challenge_type = 'application'
          AND application_config->>'starter_project' = 'responsive-hero'
          AND NOT (application_config ? 'schema_version')
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE challenge_versions
        SET application_config = application_config - 'schema_version' - 'viewports'
        WHERE challenge_type = 'application'
          AND application_config->>'starter_project' = 'responsive-hero'
          AND application_config->>'schema_version' = '1'
    """)
