"""Initial database schema

Revision ID: 001_initial_schema
Revises: None
Create Date: 2025-01-01

Creates all initial tables for AiGo Backend.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create initial database schema."""
    
    # Create itineraries table
    op.create_table(
        "itineraries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("destination", sa.String(255), nullable=False),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("total_budget", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="THB"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("cover_image_url", sa.String(500), nullable=True),
        sa.Column("is_public", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("notes", sa.Text, nullable=True),
        # AI Generation fields
        sa.Column("original_prompt", sa.Text, nullable=True,
                  comment="Original user prompt for AI generation"),
        sa.Column("generation_task_id", sa.String(255), nullable=True,
                  comment="Celery task ID for async generation"),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=True, 
                  comment="Complete AI-generated itinerary JSON"),
        sa.Column("generation_error", sa.Text, nullable=True,
                  comment="Error message if AI generation failed"),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True,
                  comment="When AI generation completed"),
        # Re-plan versioning fields
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("version_history", postgresql.JSONB, nullable=True, server_default="[]",
                  comment="History of all versions"),
        sa.Column("last_replan_at", sa.TIMESTAMP(timezone=True), nullable=True,
                  comment="When the itinerary was last replanned"),
        sa.Column("replan_task_id", sa.String(255), nullable=True,
                  comment="Celery task ID for ongoing replan"),
        sa.Column("previous_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("replan_reason", sa.String(50), nullable=True),
        sa.Column("replan_trigger_type", sa.String(50), nullable=True),
        sa.Column("replan_trigger_details", postgresql.JSONB, nullable=True),
        # Timestamps
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    
    # Add foreign key for version chain
    op.create_foreign_key(
        "fk_itineraries_previous_version",
        "itineraries",
        "itineraries",
        ["previous_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    
    # Create indexes for itineraries
    op.create_index("ix_itineraries_user_id_status", "itineraries", ["user_id", "status"])
    op.create_index("ix_itineraries_destination", "itineraries", ["destination"])
    op.create_index("ix_itineraries_start_date", "itineraries", ["start_date"])
    op.create_index("ix_itineraries_generation_task_id", "itineraries", ["generation_task_id"])
    op.create_index("ix_itineraries_replan_task_id", "itineraries", ["replan_task_id"])
    
    # Create daily_plans table
    op.create_table(
        "daily_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("itinerary_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("day_number", sa.Integer, nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("daily_budget", sa.Numeric(12, 2), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["itinerary_id"], ["itineraries.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_daily_plans_itinerary_id", "daily_plans", ["itinerary_id"])
    
    # Create activities table
    op.create_table(
        "activities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("itinerary_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("daily_plan_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("category", sa.String(50), nullable=False, server_default="sightseeing"),
        sa.Column("day_number", sa.Integer, nullable=False, server_default="1"),
        sa.Column("order", sa.Integer, nullable=False, server_default="0"),
        # Location
        sa.Column("location_name", sa.String(500), nullable=True),
        sa.Column("location_address", sa.String(500), nullable=True),
        sa.Column("latitude", sa.Float, nullable=True),
        sa.Column("longitude", sa.Float, nullable=True),
        sa.Column("google_place_id", sa.String(255), nullable=True),
        # Time
        sa.Column("start_time", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("end_time", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("duration_minutes", sa.Integer, nullable=True),
        # Cost
        sa.Column("estimated_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("actual_cost", sa.Numeric(12, 2), nullable=True),
        # Booking
        sa.Column("booking_reference", sa.String(255), nullable=True),
        sa.Column("booking_url", sa.String(500), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        # Timestamps
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["itinerary_id"], ["itineraries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["daily_plan_id"], ["daily_plans.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_activities_itinerary_id", "activities", ["itinerary_id"])
    op.create_index("ix_activities_daily_plan_id", "activities", ["daily_plan_id"])


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table("activities")
    op.drop_table("daily_plans")
    op.drop_table("itineraries")
