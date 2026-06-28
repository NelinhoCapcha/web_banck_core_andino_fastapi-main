from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.cfg_database import get_db
from app.repositories import rep_clientes
from app.schemas.sch_clientes import ClienteOut

router = APIRouter()

@router.get("", response_model=list[ClienteOut])
def buscar_clientes(
    search: str = Query("", min_length=0),
    limit: int = Query(12, ge=1, le=25),
    db: Session = Depends(get_db),
):
    return rep_clientes.buscar(db, search=search, limit=limit)

@router.get("/{codcliente}", response_model=ClienteOut)
def get_cliente(codcliente: str, db: Session = Depends(get_db)):
    cliente = rep_clientes.get_by_cod(db, codcliente)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return cliente
