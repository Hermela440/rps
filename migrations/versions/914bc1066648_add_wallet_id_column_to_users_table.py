"""Add wallet_id column to users table

Revision ID: 914bc1066648
Revises: 
Create Date: 2025-05-30 14:12:36.359482

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '914bc1066648'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('wallet_id', sa.String(length=255), nullable=True))
        batch_op.create_unique_constraint('uq_users_wallet_id', ['wallet_id'])


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_constraint('uq_users_wallet_id', type_='unique')
        batch_op.drop_column('wallet_id')