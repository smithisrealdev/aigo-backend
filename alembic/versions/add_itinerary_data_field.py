"""Add JSONB data field and generation tracking to itineraries

Revision ID: add_itinerary_data_field
Revises: [previous_revision]
Create Date: 2025-01-01

This migration adds support for storing complete AI-generated itinerary data.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "add_itinerary_data_field"
down_revision = None  # Update this to your actual previous revision
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add data, generation_error, and completed_at columns to itineraries table."""
    # Add JSONB column for storing complete AI-generated itinerary
    op.add_column(
        "itineraries",
        sa.Column(
            "data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Complete AI-generated itinerary JSON (AIFullItinerary schema)",
        ),
    )

    # Add error tracking column
    op.add_column(
        "itineraries",
        sa.Column(
            "generation_error",
            sa.Text(),
            nullable=True,
            comment="Error message if AI generation failed",
        ),
    )

    # Add completion timestamp
    op.add_column(
        "itineraries",
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When AI generation completed",
        ),
    )

    # Add index on status for faster queries on processing/completed itineraries
    op.create_index(
        "ix_itineraries_status_completed",
        "itineraries",
        ["status", "completed_at"],
        unique=False,
    )


def downgrade() -> None:
    """Remove the added columns."""
    op.drop_index("ix_itineraries_status_completed", table_name="itineraries")
    op.drop_column("itineraries", "completed_at")
    op.drop_column("itineraries", "generation_error")
    op.drop_column("itineraries", "data")
