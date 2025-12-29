"""Add version and history fields to itinerary

Revision ID: add_replan_version_fields
Revises: add_itinerary_data_field
Create Date: 2025-01-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'add_replan_version_fields'
down_revision: Union[str, None] = 'add_itinerary_data_field'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add version tracking and replan fields to itinerary table."""
    
    # Add version field (default 1 for existing records)
    op.add_column(
        'itinerary',
        sa.Column(
            'version',
            sa.Integer(),
            nullable=False,
            server_default='1',
            comment='Current version number, incremented on each replan'
        )
    )
    
    # Add version_history JSONB field
    op.add_column(
        'itinerary',
        sa.Column(
            'version_history',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment='History of previous versions with their data and changes'
        )
    )
    
    # Add last_replan_at timestamp
    op.add_column(
        'itinerary',
        sa.Column(
            'last_replan_at',
            sa.DateTime(timezone=True),
            nullable=True,
            comment='Timestamp of last replan operation'
        )
    )
    
    # Add replan_task_id for tracking in-progress replans
    op.add_column(
        'itinerary',
        sa.Column(
            'replan_task_id',
            sa.String(255),
            nullable=True,
            comment='Celery task ID for ongoing replan operation'
        )
    )
    
    # Create index on replan_task_id for quick lookups
    op.create_index(
        'ix_itinerary_replan_task_id',
        'itinerary',
        ['replan_task_id'],
        unique=False
    )


def downgrade() -> None:
    """Remove version tracking fields."""
    
    op.drop_index('ix_itinerary_replan_task_id', table_name='itinerary')
    op.drop_column('itinerary', 'replan_task_id')
    op.drop_column('itinerary', 'last_replan_at')
    op.drop_column('itinerary', 'version_history')
    op.drop_column('itinerary', 'version')
