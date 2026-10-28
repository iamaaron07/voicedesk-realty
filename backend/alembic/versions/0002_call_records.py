"""Persist Bolna call execution summaries."""
from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa

revision = "0002_call_records"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

def upgrade():
    if not inspect(op.get_bind()).has_table("call_records"):
        op.create_table(
        "call_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("execution_id", sa.String(160), nullable=False, unique=True),
        sa.Column("agent_id", sa.String(160), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="session_issued"),
        sa.Column("summary", sa.String(2000)),
        sa.Column("duration_seconds", sa.Integer()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        )
    indexes={i["name"] for i in inspect(op.get_bind()).get_indexes("call_records")}
    if "ix_call_records_user_id" not in indexes: op.create_index("ix_call_records_user_id", "call_records", ["user_id"])
    if "ix_call_records_execution_id" not in indexes: op.create_index("ix_call_records_execution_id", "call_records", ["execution_id"])

def downgrade():
    op.drop_table("call_records")
