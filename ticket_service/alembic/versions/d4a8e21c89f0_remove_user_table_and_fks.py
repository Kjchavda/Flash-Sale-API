"""remove user table and foreign keys to users

Revision ID: d4a8e21c89f0
Revises: 377a1701483c
Create Date: 2026-09-16 15:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4a8e21c89f0'
down_revision: Union[str, Sequence[str], None] = '377a1701483c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: drop FKs to users and drop the users table."""
    # 1. Drop foreign key constraint on tickets.locked_by -> users.user_id
    op.drop_constraint('tickets_locked_by_fkey', 'tickets', type_='foreignkey')

    # 2. Drop foreign key constraint on orders.user_id -> users.user_id
    op.drop_constraint('orders_user_id_fkey', 'orders', type_='foreignkey')

    # 3. Drop the redundant local users table
    op.drop_table('users')


def downgrade() -> None:
    """Downgrade schema: recreate users table and restore FKs."""
    op.create_table(
        'users',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('user_id'),
        sa.UniqueConstraint('email')
    )
    op.create_foreign_key(
        'orders_user_id_fkey',
        'orders',
        'users',
        ['user_id'],
        ['user_id']
    )
    op.create_foreign_key(
        'tickets_locked_by_fkey',
        'tickets',
        'users',
        ['locked_by'],
        ['user_id']
    )
