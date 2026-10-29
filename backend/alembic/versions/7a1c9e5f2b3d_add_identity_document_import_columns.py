"""add identity document import columns to documents

Revision ID: 7a1c9e5f2b3d
Revises: 0eb88898ddd4
Create Date: 2026-10-27

Adds the columns needed to attach an RC / Driving Licence / Insurance
Policy identity document directly to an existing customer (and, where
applicable, their vehicle or policy) ahead of any claim - see
services/document_import.py. Every column added here is nullable, so
every existing documents row (all of which are claim-scoped) is
unaffected; Claim_ID itself becomes nullable so a claim-independent
identity document can have no claim at all.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "7a1c9e5f2b3d"
down_revision: Union[str, None] = "0eb88898ddd4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("documents", "Claim_ID", existing_type=sa.String(30), nullable=True)

    op.add_column("documents", sa.Column("Customer_ID", sa.String(30), nullable=True))
    op.add_column("documents", sa.Column("Vehicle_ID", sa.String(30), nullable=True))
    op.add_column("documents", sa.Column("Policy_ID", sa.String(30), nullable=True))
    op.add_column("documents", sa.Column("Document_Expiry_Date", sa.Date(), nullable=True))
    op.add_column("documents", sa.Column("Issuer_Reference", sa.String(255), nullable=True))
    op.add_column("documents", sa.Column("Uploaded_By", sa.String(30), nullable=True))

    op.create_foreign_key(
        "fk_documents_customer_id", "documents", "customers", ["Customer_ID"], ["Customer_ID"]
    )
    op.create_foreign_key(
        "fk_documents_vehicle_id", "documents", "vehicles", ["Vehicle_ID"], ["Vehicle_ID"]
    )
    op.create_foreign_key(
        "fk_documents_policy_id", "documents", "policies", ["Policy_ID"], ["Policy_ID"]
    )
    op.create_foreign_key(
        "fk_documents_uploaded_by", "documents", "authentication_users", ["Uploaded_By"], ["User_ID"]
    )
    op.create_index("ix_documents_Customer_ID", "documents", ["Customer_ID"])


def downgrade() -> None:
    op.drop_index("ix_documents_Customer_ID", table_name="documents")
    op.drop_constraint("fk_documents_uploaded_by", "documents", type_="foreignkey")
    op.drop_constraint("fk_documents_policy_id", "documents", type_="foreignkey")
    op.drop_constraint("fk_documents_vehicle_id", "documents", type_="foreignkey")
    op.drop_constraint("fk_documents_customer_id", "documents", type_="foreignkey")

    op.drop_column("documents", "Uploaded_By")
    op.drop_column("documents", "Issuer_Reference")
    op.drop_column("documents", "Document_Expiry_Date")
    op.drop_column("documents", "Policy_ID")
    op.drop_column("documents", "Vehicle_ID")
    op.drop_column("documents", "Customer_ID")

    op.alter_column("documents", "Claim_ID", existing_type=sa.String(30), nullable=False)
