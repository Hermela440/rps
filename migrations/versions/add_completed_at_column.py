"""Add completed_at column to transactions table

Revision ID: add_completed_at_column
Revises: 
Create Date: 2024-05-30 14:45:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_completed_at_column'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Add completed_at column to transactions table
    op.add_column('transactions', sa.Column('completed_at', sa.DateTime(), nullable=True))

def downgrade():
    # Remove completed_at column from transactions table
    op.drop_column('transactions', 'completed_at') 