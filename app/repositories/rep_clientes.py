from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models.mdl_clientes import DCliente

def get_by_cod(db: Session, codcliente: str):
    return db.query(DCliente).filter(
        DCliente.codcliente == codcliente
    ).first()

def get_by_dni(db: Session, dni: str):
    return db.query(DCliente).filter(
        DCliente.numerodocumentoidentidad == dni
    ).first()

def get_all(db: Session, skip: int = 0, limit: int = 50):
    return db.query(DCliente).offset(skip).limit(limit).all()

def buscar(db: Session, search: str = "", limit: int = 12):
    term = (search or "").strip()
    query = db.query(DCliente)
    if term:
        like = f"%{term}%"
        query = query.filter(
            or_(
                DCliente.codcliente.ilike(like),
                DCliente.nomcliente.ilike(like),
                DCliente.numerodocumentoidentidad.ilike(like),
            )
        )
    return (
        query
        .order_by(DCliente.codcliente)
        .limit(max(1, min(limit, 25)))
        .all()
    )
