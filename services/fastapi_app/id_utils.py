"""Utility to handle supplier ID resolution across SQLite (string) and PostgreSQL (UUID)."""
import uuid
from database import IS_SQLITE

def resolve_id(id_str: str):
    """Convert a string ID to the correct type for the current database backend."""
    if not id_str:
        return id_str

    if isinstance(id_str, str) and id_str.startswith("SUPPLIER_"):
        try:
            from database import SessionLocal
            from models import SupplierNode
            num_part = id_str.split("_")[1]
            supp_name = f"Supplier {int(num_part):03d}"
            db = SessionLocal()
            try:
                supp = db.query(SupplierNode).filter(SupplierNode.name == supp_name).first()
                if supp:
                    return supp.id
            except Exception:
                pass
            finally:
                db.close()
        except Exception:
            pass

    if IS_SQLITE:
        return id_str
    if isinstance(id_str, uuid.UUID):
        return id_str
    try:
        return uuid.UUID(id_str)
    except ValueError:
        return id_str
