"""Add users table with social login support

Revision ID: 002_add_users_table
Revises: 001_initial_schema
Create Date: 2025-01-02

Creates users table with support for:
- Local authentication (email/password)
- Social login (Google, Facebook, Apple)
- Terms acceptance tracking
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "002_add_users_table"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create users table with social login support."""
    
    # Create auth_provider enum type
    auth_provider_enum = postgresql.ENUM(
        "local", "google", "facebook", "apple",
        name="authprovider",
        # Important: disable implicit type creation during create_table.
        # Alembic/SQLAlchemy will otherwise attempt to CREATE TYPE again
        # with checkfirst=False, which breaks idempotency.
        create_type=False,
    )
    auth_provider_enum.create(op.get_bind(), checkfirst=True)
    
    # Create users table
    op.create_table(
        "users",
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
        
        # Authentication fields
        sa.Column(
            "email",
            sa.String(255),
            nullable=False,
            unique=True,
            index=True,
        ),
        sa.Column(
            "hashed_password",
            sa.String(255),
            nullable=True,  # Nullable for social login users
            comment="Bcrypt hashed password, null for social login users",
        ),
        
        # Profile fields
        sa.Column(
            "full_name",
            sa.String(255),
            nullable=False,
        ),
        sa.Column(
            "avatar_url",
            sa.String(500),
            nullable=True,
        ),
        
        # Social login fields
        sa.Column(
            "provider",
            auth_provider_enum,
            nullable=False,
            server_default="local",
        ),
        sa.Column(
            "social_id",
            sa.String(255),
            nullable=True,
            index=True,
            comment="Unique identifier from OAuth provider",
        ),
        
        # Account status fields
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default="true",
        ),
        sa.Column(
            "is_verified",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
        
        # Terms acceptance fields
        sa.Column(
            "has_accepted_terms",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "terms_accepted_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            comment="Timestamp when terms of service were accepted",
        ),
        
        # Login tracking
        sa.Column(
            "last_login_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )
    
    # Create composite index for social login lookups
    op.create_index(
        "ix_users_provider_social_id",
        "users",
        ["provider", "social_id"],
    )
    
    # Add foreign key constraint to itineraries table
    op.create_foreign_key(
        "fk_itineraries_user_id_users",
        "itineraries",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    """Remove users table and related constraints."""
    
    # Remove foreign key from itineraries
    op.drop_constraint(
        "fk_itineraries_user_id_users",
        "itineraries",
        type_="foreignkey",
    )
    
    # Drop indexes
    op.drop_index("ix_users_provider_social_id", table_name="users")
    
    # Drop users table
    op.drop_table("users")
    
    # Drop enum type
    auth_provider_enum = postgresql.ENUM(
        "local", "google", "facebook", "apple",
        name="authprovider",
    )
    auth_provider_enum.drop(op.get_bind(), checkfirst=True)
