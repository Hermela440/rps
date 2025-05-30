"""Merge multiple heads

Revision ID: merge_heads
Revises: 45d8aff96cfe, add_completed_at_column
Create Date: 2024-05-30 14:50:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'merge_heads'
down_revision = ('45d8aff96cfe', 'add_completed_at_column')
branch_labels = None
depends_on = None

def upgrade():
    pass

def downgrade():
    pass 