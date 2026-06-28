"""
FASE 1 â€” Generador de datos de Homebanking.

Crea:
  1. usuarios_homebanking: un usuario de portal por cada cliente con crÃ©dito.
     username = codcliente en minÃºscula, password_hash = bcrypt(DNI). (demo)
  2. foperaciones: movimientos histÃ³ricos 2025 por canal Homebanking (WEB/APP):
     - Desembolso de capital (DCAP) al inicio del crÃ©dito.
     - Pagos de cuota (PCAP/PINT) segÃºn fplanpagomes (cuotas con montocapitalpagado>0).

Idempotente: si ya existen usuarios/operaciones, no duplica.

Ejecutar: venv/Scripts/python.exe scripts/seed_homebanking.py
"""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bcrypt                                  # noqa: E402
from sqlalchemy import create_engine, text   # noqa: E402
from app.core.cfg_config import settings     # noqa: E402


def hash_password(p: str) -> str:
    """Hash bcrypt directo (evita el bug passlib<->bcrypt). Demo."""
    return bcrypt.hashpw(p.encode()[:72], bcrypt.gensalt()).decode()


def _catalogos(c):
    """Resuelve PKs de catÃ¡logos por cÃ³digo (no hardcodear)."""
    def pk(tabla, col, val):
        return c.execute(text(f"SELECT pk{tabla[1:]} FROM {tabla} WHERE {col}=:v LIMIT 1"),
                         {"v": val}).scalar()
    return {
        "tipo_cre": pk("dtipooperacion", "codtipooperacion", "CRE"),
        "tipo_deb": pk("dtipooperacion", "codtipooperacion", "DEB"),
        "con_dcap": pk("dconceptooperacion", "codconceptooperacion", "DCAP"),
        "con_pcap": pk("dconceptooperacion", "codconceptooperacion", "PCAP"),
        "con_pint": pk("dconceptooperacion", "codconceptooperacion", "PINT"),
        "medio_web": pk("dmediopago", "codmediopago", "WEB"),
        "medio_app": pk("dmediopago", "codmediopago", "APP"),
        "canal_web": pk("dcanaltransaccional", "codcanaltransaccional", "WEB"),
        "canal_app": pk("dcanaltransaccional", "codcanaltransaccional", "APP"),
        "cond_norm": pk("dcondicioncontable", "codcondicioncontable", "01"),
    }


def crear_usuarios(c):
    """Un usuario de homebanking por cada cliente con credito (idempotente)."""
    rows = c.execute(text("""
        SELECT DISTINCT cc.pkcliente,
               LOWER(TRIM(cl.codcliente)) AS username,
               TRIM(cl.numerodocumentoidentidad) || '@' || cl.pkcliente::text AS password
        FROM dcuentacredito cc
        JOIN dcliente cl ON cl.pkcliente = cc.pkcliente
        WHERE NOT EXISTS (SELECT 1 FROM usuarios_homebanking u WHERE u.pkcliente = cc.pkcliente)
    """)).mappings().all()
    for row in rows:
        c.execute(text("""
            INSERT INTO usuarios_homebanking
                (pkcliente, username, password_hash, intentos_fallidos, bloqueado, activo, fecultactualizacion)
            VALUES (:pkcliente, :username, :hash, 0, 'N', 'S', NOW())
        """), {
            "pkcliente": row["pkcliente"],
            "username": row["username"],
            "hash": hash_password(row["password"]),
        })
    return len(rows)

def generar_operaciones(c, cat):
    """
    Genera movimientos en foperaciones a partir de fplanpagomes:
    - 1 DESEMBOLSO (DCAP) por crÃ©dito (canal WEB).
    - 1 PAGO por cada cuota con montocapitalpagado>0 (canal APP), con su interÃ©s si aplica.
    Solo para clientes que tienen usuario de homebanking.
    """
    # Desembolsos: uno por cuenta de crÃ©dito (usa fecha de desembolso real).
    # codtipkar 'CR' (abono al cliente), codkardex correlativo Ãºnico 'DES-<pkcuenta>'.
    desem = c.execute(text("""
        INSERT INTO foperaciones
            (codtipkar, codkardex, pkcuentacredito, pkconceptooperacion, pktipooperacion, pkmediopago,
             pkcanaltransaccional, pkmoneda, pkcondicioncontable, pkproducto,
             pkagenciaorigen, montooperacion, montopagoconcepto,
             codtipoegresoingreso, fechahoraoperacion, periododia, codusuope, fecultactualizacion)
        SELECT 'CR', 'DES-' || f.pkcuentacredito,
               f.pkcuentacredito, :con_dcap, :tipo_cre, :medio_web,
               :canal_web, f.pkmoneda, :cond_norm, f.pkproducto,
               f.pkagencia, f.montocapitaldesembolsado, f.montocapitaldesembolsado,
               'I', f.fechadesembolsocredito,
               CAST(TO_CHAR(f.fechadesembolsocredito,'YYYYMMDD') AS INTEGER), 'HB', NOW()
        FROM fagcuentacredito f
        WHERE f.montocapitaldesembolsado > 0
          AND EXISTS (SELECT 1 FROM dcuentacredito cc JOIN usuarios_homebanking u ON u.pkcliente=cc.pkcliente
                      WHERE cc.pkcuentacredito = f.pkcuentacredito)
          AND NOT EXISTS (SELECT 1 FROM foperaciones o
                          WHERE o.pkcuentacredito=f.pkcuentacredito AND o.pkconceptooperacion=:con_dcap)
    """), cat)

    # Pagos de cuota: uno por cuota pagada (capital). codtipkar 'DB' (cargo).
    # codkardex Ãºnico 'PAG-<pkcuenta>-<nrocuota>'.
    pagos_cap = c.execute(text("""
        INSERT INTO foperaciones
            (codtipkar, codkardex, pkcuentacredito, nrocuotaplazo, pkconceptooperacion, pktipooperacion, pkmediopago,
             pkcanaltransaccional, pkmoneda, pkcondicioncontable, pkproducto,
             pkagenciaorigen, montooperacion, montopagoconcepto,
             codtipoegresoingreso, fechahoraoperacion, periododia, codusuope, fecultactualizacion)
        SELECT 'DB', 'PAG-' || p.pkcuentacredito || '-' || p.nrocuota,
               p.pkcuentacredito, p.nrocuota, :con_pcap, :tipo_deb, :medio_app,
               :canal_app, p.pkmoneda, :cond_norm, p.pkproducto,
               p.pkagencia, p.montocapitalpagado, p.montocapitalpagado,
               'E', COALESCE(p.fechapagocuota, p.fechavencimientopagocuota),
               CAST(TO_CHAR(COALESCE(p.fechapagocuota,p.fechavencimientopagocuota),'YYYYMMDD') AS INTEGER),
               'HB', NOW()
        FROM fplanpagomes p
        WHERE p.montocapitalpagado > 0
          AND EXISTS (SELECT 1 FROM usuarios_homebanking u WHERE u.pkcliente=p.pkcliente)
          AND NOT EXISTS (SELECT 1 FROM foperaciones o
                          WHERE o.pkcuentacredito=p.pkcuentacredito AND o.nrocuotaplazo=p.nrocuota
                            AND o.pkconceptooperacion=:con_pcap)
    """), cat)

    return desem.rowcount, pagos_cap.rowcount


def main():
    e = create_engine(settings.DATABASE_URL)
    with e.begin() as c:
        cat = _catalogos(c)
        faltan = [k for k, v in cat.items() if v is None]
        if faltan:
            print("[ERROR] catÃ¡logos no encontrados:", faltan)
            return
        nu = crear_usuarios(c)
        print(f"[OK] usuarios_homebanking nuevos: {nu}")
        nd, npg = generar_operaciones(c, cat)
        print(f"[OK] foperaciones desembolsos: {nd} | pagos de cuota: {npg}")
        tot = c.execute(text("SELECT COUNT(*) FROM foperaciones")).scalar()
        tu = c.execute(text("SELECT COUNT(*) FROM usuarios_homebanking")).scalar()
        print(f"[TOTAL] usuarios={tu} | operaciones={tot}")
    print("Fase 1 completada.")


if __name__ == "__main__":
    main()

