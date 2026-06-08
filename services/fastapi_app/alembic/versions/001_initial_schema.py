"""initial schema

Revision ID: 001
Revises: 
Create Date: 2026-06-06 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import geoalchemy2

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")

    op.create_table('supplier_nodes',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('country', sa.String(), nullable=False),
        sa.Column('tier', sa.Integer(), nullable=False),
        sa.Column('reliability_score', sa.Float(), nullable=True),
        sa.Column('geom', geoalchemy2.types.Geometry(geometry_type='POINT', srid=4326, from_text='ST_GeomFromEWKT', name='geometry'), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('sku_catalog',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('criticality_score', sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('supplier_sku_links',
        sa.Column('supplier_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('sku_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('lead_time_days', sa.Integer(), nullable=False),
        sa.Column('capacity_units', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['sku_id'], ['sku_catalog.id'], ),
        sa.ForeignKeyConstraint(['supplier_id'], ['supplier_nodes.id'], ),
        sa.PrimaryKeyConstraint('supplier_id', 'sku_id')
    )
    
    op.create_table('disruption_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('occurred_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('severity', sa.Float(), nullable=False),
        sa.Column('affected_supplier_ids', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False),
        sa.Column('predicted', sa.Boolean(), nullable=False),
        sa.Column('agent_action', sa.String(), nullable=True),
        sa.Column('resolved_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('risk_signals',
        sa.Column('supplier_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('timestamp', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('signal_type', sa.String(), nullable=False),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('source', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('supplier_id', 'timestamp', 'signal_type')
    )
    
    # TimescaleDB hypertable
    op.execute("SELECT create_hypertable('risk_signals', 'timestamp', chunk_time_interval => interval '1 week');")
    
    # Create indexes
    op.create_index('ix_risk_signals_supplier_id_timestamp', 'risk_signals', ['supplier_id', 'timestamp'])

def downgrade() -> None:
    op.drop_table('risk_signals')
    op.drop_table('disruption_events')
    op.drop_table('supplier_sku_links')
    op.drop_table('sku_catalog')
    op.drop_table('supplier_nodes')
    op.execute("DROP EXTENSION IF EXISTS timescaledb;")
    op.execute("DROP EXTENSION IF EXISTS postgis;")
