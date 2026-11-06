"""add sender id to messages

Revision ID: b3ba216c1b4b
Revises: 109c69a4d164
Create Date: 2026-10-14 10:50:12.999983

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b3ba216c1b4b"
down_revision: Union[str, Sequence[str], None] = "109c69a4d164"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("sender_id", sa.String(length=36), nullable=True),
    )

    op.create_index(
        "ix_messages_sender_id",
        "messages",
        ["sender_id"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_messages_sender_id_users",
        "messages",
        "users",
        ["sender_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_messages_sender_id_users",
        "messages",
        type_="foreignkey",
    )

    op.drop_index(
        "ix_messages_sender_id",
        table_name="messages",
    )

    op.drop_column("messages", "sender_id")
