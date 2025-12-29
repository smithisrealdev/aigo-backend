"""Add user preferences table for onboarding

Revision ID: 003_add_user_preferences
Revises: 002_add_users_table
Create Date: 2025-12-29

Creates user_preferences table with support for:
- Travel style preferences
- Food and dietary preferences
- Mobility preferences
- Budget preferences
- Onboarding tracking
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "003_add_user_preferences"
down_revision = "002_add_users_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create user_preferences table and enum types."""
    
    # Create enum types
    food_preference_enum = postgresql.ENUM(
        "local", "international", "vegetarian", "halal", "any",
        name="foodpreference",
        # Disable implicit type creation during create_table (see 002 migration).
        create_type=False,
    )
    food_preference_enum.create(op.get_bind(), checkfirst=True)
    
    mobility_preference_enum = postgresql.ENUM(
        "walking", "public_transit", "driving", "mixed",
        name="mobilitypreference",
        create_type=False,
    )
    mobility_preference_enum.create(op.get_bind(), checkfirst=True)
    
    budget_level_enum = postgresql.ENUM(
        "budget", "moderate", "premium", "luxury",
        name="budgetlevel",
        create_type=False,
    )
    budget_level_enum.create(op.get_bind(), checkfirst=True)
    
    # Create user_preferences table
    op.create_table(
        "user_preferences",
        # Primary key and timestamps (from Base)
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        
        # Foreign key to users
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
            index=True,
        ),
        
        # Travel styles (array of strings)
        sa.Column(
            "travel_styles",
            postgresql.ARRAY(sa.String(50)),
            nullable=True,
            comment="List of preferred travel styles",
        ),
        
        # Food preference
        sa.Column(
            "food_preference",
            food_preference_enum,
            nullable=True,
        ),
        
        # Mobility preference
        sa.Column(
            "mobility_preference",
            mobility_preference_enum,
            nullable=True,
        ),
        
        # Budget level
        sa.Column(
            "budget_level",
            budget_level_enum,
            nullable=True,
        ),
        
        # Interests array
        sa.Column(
            "interests",
            postgresql.ARRAY(sa.String(100)),
            nullable=True,
            comment="Specific interests like temples, beaches, nightlife",
        ),
        
        # Dietary restrictions
        sa.Column(
            "dietary_restrictions",
            postgresql.ARRAY(sa.String(100)),
            nullable=True,
        ),
        
        # Accessibility needs
        sa.Column(
            "accessibility_needs",
            sa.String(500),
            nullable=True,
        ),
        
        # Preferred languages
        sa.Column(
            "preferred_languages",
            postgresql.ARRAY(sa.String(10)),
            nullable=True,
            comment="ISO language codes",
        ),
        
        # Onboarding tracking
        sa.Column(
            "has_completed_onboarding",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "onboarding_completed_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "onboarding_step",
            sa.Integer,
            nullable=False,
            server_default="0",
            comment="Current step in onboarding flow",
        ),
        
        # Custom preferences as JSON
        sa.Column(
            "custom_preferences",
            postgresql.JSON,
            nullable=True,
            comment="Additional custom preferences",
        ),
    )


def downgrade() -> None:
    """Remove user_preferences table and enum types."""
    
    # Drop table
    op.drop_table("user_preferences")
    
    # Drop enum types
    budget_level_enum = postgresql.ENUM(
        "budget", "moderate", "premium", "luxury",
        name="budgetlevel",
    )
    budget_level_enum.drop(op.get_bind(), checkfirst=True)
    
    mobility_preference_enum = postgresql.ENUM(
        "walking", "public_transit", "driving", "mixed",
        name="mobilitypreference",
    )
    mobility_preference_enum.drop(op.get_bind(), checkfirst=True)
    
    food_preference_enum = postgresql.ENUM(
        "local", "international", "vegetarian", "halal", "any",
        name="foodpreference",
    )
    food_preference_enum.drop(op.get_bind(), checkfirst=True)
