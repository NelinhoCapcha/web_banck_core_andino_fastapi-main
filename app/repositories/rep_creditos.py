from sqlalchemy.orm import Session
from sqlalchemy import text

PERIODO_CARTERA = 202512
TOLERANCIA_CANCELACION = 1.00


def get_cartera_asesor(db: Session, pkasesor: int, periodomes: int = 202512):
    """Cartera activa de un asesor desde FAGCUENTACREDITO."""
    sql = text("""
        SELECT
            cc.codcuentacredito,
            cl.nomcliente,
            cl.numerodocumentoidentidad,
            f.montosaldocapital,
            f.montosaldointeres,
            f.montosaldomoratorio,
            f.montosaldogasto,
            (
              COALESCE(f.montosaldocapital, 0)
              + COALESCE(f.montosaldointeres, 0)
              + COALESCE(f.montosaldomoratorio, 0)
              + COALESCE(f.montosaldogasto, 0)
            ) AS pago_pendiente,
            f.tasainterescompensatoria,
            f.tasainteresmoratoria,
            f.diasatrasocredito,
            f.car_vig_capital,
            f.car_ven_capital,
            f.saldoprovisiones,
            p.codtipocredito,
            p.destipocredito,
            p.desproducto,
            cal.codcalificacioncrediticia AS calificacion
        FROM fagcuentacredito f
        JOIN dcuentacredito cc ON cc.pkcuentacredito = f.pkcuentacredito
        JOIN dcliente cl       ON cl.pkcliente = cc.pkcliente
        LEFT JOIN dproducto p  ON p.pkproducto = f.pkproducto
        LEFT JOIN dcalificacioncrediticia cal
            ON cal.pkcalificacioncrediticia = f.pkcalificacioncrediticiainterna
        WHERE f.pkasesor = :pkasesor
          AND f.periodomes = :periodomes
        ORDER BY f.diasatrasocredito DESC
    """)
    return db.execute(sql, {
        "pkasesor": pkasesor,
        "periodomes": periodomes
    }).fetchall()

def get_detalle(db: Session, codcuentacredito: str):
    sql = text("""
        SELECT
            cc.codcuentacredito,
            cl.nomcliente,
            cl.numerodocumentoidentidad,
            s.montoaprobadocredito,
            s.nrocuotaaprobado,
            s.tasainterescompensatoria,
            s.fechaaprobacioncredito,
            f.montosaldocapital,
            f.montosaldointeres,
            f.montosaldomoratorio,
            f.montosaldogasto,
            f.diasatrasocredito,
            f.flagjudicial,
            f.flagcastigado,
            f.pkestadocredito,
            CASE
              WHEN f.flagcastigado = 'S' OR f.pkestadocredito = 7 THEN 'Castigado'
              WHEN f.flagjudicial = 'S' OR f.pkestadocredito = 3 THEN 'Judicial'
              ELSE 'Vigente'
            END AS estado_credito,
            (
              COALESCE(f.montosaldocapital, 0)
              + COALESCE(f.montosaldointeres, 0)
              + COALESCE(f.montosaldomoratorio, 0)
              + COALESCE(f.montosaldogasto, 0)
            ) AS pago_pendiente,
            f.montosaldocliente,
            f.tasainterescompensatoria AS tea_aplicada,
            f.tasainteresmoratoria AS tasa_moratoria,
            p.codtipocredito,
            p.destipocredito,
            p.desproducto
        FROM dcuentacredito cc
        JOIN dcliente cl ON cl.pkcliente = cc.pkcliente
        LEFT JOIN dsolicitud s ON s.pkcliente = cc.pkcliente
        LEFT JOIN fagcuentacredito f ON f.pkcuentacredito = cc.pkcuentacredito
        LEFT JOIN dproducto p ON p.pkproducto = f.pkproducto
        WHERE cc.codcuentacredito = :cod
        LIMIT 1
    """)
    return db.execute(sql, {"cod": codcuentacredito}).fetchone()

def get_cronograma(db: Session, codcuentacredito: str):
    sql = text("""
        SELECT
            p.nrocuota,
            p.fechavencimientopagocuota,
            p.fechapagocuota,
            p.montocuota,
            p.montocapitalprogramado,
            p.montointeresprogramado,
            p.montosaldo,
            p.codestadocuota,
            CASE
              WHEN (
                COALESCE(f.montosaldocapital, 0)
                + COALESCE(f.montosaldointeres, 0)
                + COALESCE(f.montosaldomoratorio, 0)
                + COALESCE(f.montosaldogasto, 0)
              ) <= :tolerancia THEN TRUE
              ELSE (p.fechapagocuota IS NOT NULL)
            END AS pagada
        FROM fplanpagomes p
        JOIN dcuentacredito cc ON cc.pkcuentacredito = p.pkcuentacredito
        LEFT JOIN fagcuentacredito f
          ON f.pkcuentacredito = p.pkcuentacredito
         AND f.periodomes = :periodomes
        WHERE cc.codcuentacredito = :cod
          AND p.periodomes = :periodomes
        ORDER BY p.nrocuota
    """)
    return db.execute(sql, {
        "cod": codcuentacredito,
        "periodomes": PERIODO_CARTERA,
        "tolerancia": TOLERANCIA_CANCELACION,
    }).fetchall()

def tiene_mala_calificacion(db: Session, pkcliente: int) -> bool:
    """
    True si el cliente tiene algún crédito con calificación Deficiente/Dudoso/Pérdida
    (cod 2/3/4). Se usa SOLO para PENALIZAR el pre-scoring; la decisión de elegibilidad
    (gate de sujeto de crédito) la toma svc_elegibilidad, que es la fuente de verdad.
    """
    sql = text("""
        SELECT COUNT(*) FROM fagcuentacredito f
        JOIN dcuentacredito cc ON cc.pkcuentacredito = f.pkcuentacredito
        JOIN dcalificacioncrediticia cal
            ON cal.pkcalificacioncrediticia = f.pkcalificacioncrediticiainterna
        WHERE cc.pkcliente = :pkcliente
          AND cal.codcalificacioncrediticia IN ('2','3','4')
          AND f.periodomes = :periodomes
          AND (
            COALESCE(f.montosaldocapital, 0)
            + COALESCE(f.montosaldointeres, 0)
            + COALESCE(f.montosaldomoratorio, 0)
            + COALESCE(f.montosaldogasto, 0)
          ) > :tolerancia
    """)
    result = db.execute(sql, {
        "pkcliente": pkcliente,
        "periodomes": PERIODO_CARTERA,
        "tolerancia": TOLERANCIA_CANCELACION,
    }).scalar()
    return result > 0


# Mapeo de codtipocredito de dproducto (01/02/03) al código funcional (ME/PE/CO)
# que usa el backend (scoring, ruteo) y que el frontend envía.
_TIPO_PROD_A_FUNC = {"01": "ME", "02": "PE", "03": "CO"}
_SEGMENTO = {"ME": "EMPRESARIAL", "PE": "EMPRESARIAL", "CO": "CONSUMO"}


def get_productos_disponibles(db: Session):
    """
    Tipos de crédito disponibles (distintos) según dproducto, agrupables por segmento.
    Devuelve filas con: codtipocredito(01/02/03), destipocredito.
    """
    return db.execute(text("""
        SELECT DISTINCT codtipocredito, destipocredito
        FROM dproducto
        WHERE flagactivo = '1'
        ORDER BY codtipocredito
    """)).fetchall()


def map_tipo_func(cod_prod: str) -> str:
    """01->ME, 02->PE, 03->CO (código funcional que espera el backend)."""
    return _TIPO_PROD_A_FUNC.get((cod_prod or "").strip(), (cod_prod or "").strip())


def segmento_de(cod_func: str) -> str:
    """ME/PE -> EMPRESARIAL, CO -> CONSUMO."""
    return _SEGMENTO.get(cod_func, "OTRO")
