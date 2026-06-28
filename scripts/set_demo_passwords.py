"""
Inicializa o rota las claves demo de Banco Andino.

Patron usado:
  - Clientes Homebanking: DNI@PKCLIENTE
  - Personal Core: DNI@PKPERSONAL

Uso:
  venv/Scripts/python.exe scripts/set_demo_passwords.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text  # noqa: E402

from app.core.cfg_config import settings  # noqa: E402
from app.core.cfg_security import hash_password  # noqa: E402


def main() -> None:
    engine = create_engine(settings.DATABASE_URL)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE dpersonal ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255)"))

        clientes = conn.execute(text("""
            SELECT u.pkusuario,
                   TRIM(c.numerodocumentoidentidad) || '@' || c.pkcliente::text AS password
            FROM usuarios_homebanking u
            JOIN dcliente c ON c.pkcliente = u.pkcliente
        """)).mappings().all()
        for row in clientes:
            conn.execute(text("""
                UPDATE usuarios_homebanking
                SET password_hash = :hash,
                    intentos_fallidos = 0,
                    bloqueado = 'N',
                    activo = 'S',
                    fecultactualizacion = NOW()
                WHERE pkusuario = :pkusuario
            """), {"hash": hash_password(row["password"]), "pkusuario": row["pkusuario"]})

        empleados = conn.execute(text("""
            SELECT pkpersonal,
                   TRIM(numerodni) || '@' || pkpersonal::text AS password
            FROM dpersonal
            WHERE COALESCE(estadopersonal, '1') = '1'
        """)).mappings().all()
        for row in empleados:
            conn.execute(text("""
                UPDATE dpersonal
                SET password_hash = :hash,
                    fecultactualizacion = NOW()
                WHERE pkpersonal = :pkpersonal
            """), {"hash": hash_password(row["password"]), "pkpersonal": row["pkpersonal"]})

    print(f"[OK] clientes actualizados: {len(clientes)} | patron=DNI@PKCLIENTE")
    print(f"[OK] personal actualizado: {len(empleados)} | patron=DNI@PKPERSONAL")


if __name__ == "__main__":
    main()
