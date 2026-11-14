"""Drop redundant indexes and add cascade deletes.

Revision ID: 0068351dff69
Revises: 94c168d7c633
Create Date: 2026-11-14 08:25:11.931221
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0068351dff69"
down_revision: str | Sequence[str] | None = "94c168d7c633"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_NAMING_CONVENTION = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"
}


def upgrade() -> None:
    """Drop redundant primary/unused indexes and add ON DELETE CASCADE FKs."""
    op.drop_index(op.f("ix_feed_caches_feed_id"), table_name="feed_caches")
    op.drop_index(op.f("ix_newsletters_id"), table_name="newsletters")
    op.drop_index(op.f("ix_settings_id"), table_name="settings")
    op.drop_index(op.f("ix_settings_imap_server"), table_name="settings")

    with op.batch_alter_table(
        "entries", schema=None, naming_convention=_NAMING_CONVENTION
    ) as batch_op:
        batch_op.drop_index(batch_op.f("ix_entries_id"))
        batch_op.drop_constraint(
            "fk_entries_newsletter_id_newsletters", type_="foreignkey"
        )
        batch_op.create_foreign_key(
            "fk_entries_newsletter_id_newsletters",
            "newsletters",
            ["newsletter_id"],
            ["id"],
            ondelete="CASCADE",
        )

    with op.batch_alter_table(
        "senders", schema=None, naming_convention=_NAMING_CONVENTION
    ) as batch_op:
        batch_op.drop_index(batch_op.f("ix_senders_id"))
        batch_op.drop_constraint(
            "fk_senders_newsletter_id_newsletters", type_="foreignkey"
        )
        batch_op.create_foreign_key(
            "fk_senders_newsletter_id_newsletters",
            "newsletters",
            ["newsletter_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    """Restore indexes and non-cascading foreign keys."""
    with op.batch_alter_table(
        "senders", schema=None, naming_convention=_NAMING_CONVENTION
    ) as batch_op:
        batch_op.drop_constraint(
            "fk_senders_newsletter_id_newsletters", type_="foreignkey"
        )
        batch_op.create_foreign_key(
            "fk_senders_newsletter_id_newsletters",
            "newsletters",
            ["newsletter_id"],
            ["id"],
        )
        batch_op.create_index(batch_op.f("ix_senders_id"), ["id"], unique=False)

    with op.batch_alter_table(
        "entries", schema=None, naming_convention=_NAMING_CONVENTION
    ) as batch_op:
        batch_op.drop_constraint(
            "fk_entries_newsletter_id_newsletters", type_="foreignkey"
        )
        batch_op.create_foreign_key(
            "fk_entries_newsletter_id_newsletters",
            "newsletters",
            ["newsletter_id"],
            ["id"],
        )
        batch_op.create_index(batch_op.f("ix_entries_id"), ["id"], unique=False)

    op.create_index(
        op.f("ix_settings_imap_server"), "settings", ["imap_server"], unique=False
    )
    op.create_index(op.f("ix_settings_id"), "settings", ["id"], unique=False)
    op.create_index(op.f("ix_newsletters_id"), "newsletters", ["id"], unique=False)
    op.create_index(
        op.f("ix_feed_caches_feed_id"), "feed_caches", ["feed_id"], unique=False
    )
