"""init chat schema

Revision ID: 20260218_0001
Revises:
Create Date: 2026-02-18 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260218_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    agent_presence = sa.Enum("online", "offline", name="agent_presence")
    conversation_status = sa.Enum("automated", "agent", "closed", name="conversation_status")
    message_sender_type = sa.Enum(
        "customer",
        "bot",
        "agent",
        "system",
        name="message_sender_type",
    )
    message_kind = sa.Enum("text", "quick_reply", "event", name="message_kind")

    bind = op.get_bind()
    agent_presence.create(bind, checkfirst=True)
    conversation_status.create(bind, checkfirst=True)
    message_sender_type.create(bind, checkfirst=True)
    message_kind.create(bind, checkfirst=True)

    op.create_table(
        "agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column(
            "presence",
            sa.Enum("online", "offline", name="agent_presence", create_type=False),
            nullable=False,
            server_default=sa.text("'offline'"),
        ),
        sa.Column("max_active_chats", sa.Integer(), nullable=False, server_default=sa.text("3")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "faq_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("question", sa.String(length=300), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_faq_slug"),
    )

    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_session_id", sa.String(length=120), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "automated",
                "agent",
                "closed",
                name="conversation_status",
                create_type=False,
            ),
            nullable=False,
            server_default=sa.text("'automated'"),
        ),
        sa.Column("assigned_agent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("requested_agent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["assigned_agent_id"], ["agents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_conversations_customer_session_id",
        "conversations",
        ["customer_session_id"],
        unique=False,
    )
    op.create_index(
        "ix_conversations_assigned_agent_id",
        "conversations",
        ["assigned_agent_id"],
        unique=False,
    )

    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "sender_type",
            sa.Enum(
                "customer",
                "bot",
                "agent",
                "system",
                name="message_sender_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("sender_agent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "kind",
            sa.Enum(
                "text",
                "quick_reply",
                "event",
                name="message_kind",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_agent_id"], ["agents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_messages_conversation_id", table_name="messages")
    op.drop_table("messages")

    op.drop_index("ix_conversations_assigned_agent_id", table_name="conversations")
    op.drop_index("ix_conversations_customer_session_id", table_name="conversations")
    op.drop_table("conversations")

    op.drop_table("faq_entries")
    op.drop_table("agents")

    bind = op.get_bind()
    sa.Enum(name="message_kind").drop(bind, checkfirst=True)
    sa.Enum(name="message_sender_type").drop(bind, checkfirst=True)
    sa.Enum(name="conversation_status").drop(bind, checkfirst=True)
    sa.Enum(name="agent_presence").drop(bind, checkfirst=True)
