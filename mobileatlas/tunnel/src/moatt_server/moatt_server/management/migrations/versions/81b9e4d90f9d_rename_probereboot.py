"""Rename ProbeRebootLog to ProbeServiceStartupLog

Revision ID: 81b9e4d90f9d
Revises: 8a77c2747150
Create Date: 2021-04-29 14:48:58.392716

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '81b9e4d90f9d'
down_revision = '8a77c2747150'
branch_labels = None
depends_on = None


def upgrade():
    op.rename_table('probe_reboot_log', 'probe_service_startup_log')


def downgrade():
    op.rename_table('probe_service_startup_log', 'probe_reboot_log')
