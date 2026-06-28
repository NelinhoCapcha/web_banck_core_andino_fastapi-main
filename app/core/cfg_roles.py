"""
Mapeo de cargos (dcargopersonal) a roles funcionales del flujo MPR-003-CRE
y helpers de autorización por rol (decisión §7.2 / §7.3 del PLAN).
"""

# codcargopersonal -> rol funcional usado en el token y en los permisos
CARGO_A_ROL = {
    "G01": "gerencia",        # Gerente Central
    "G02": "gerencia",        # Gerente de Área
    "F01": "jefe_regional",   # Jefe de Negocios Regional
    "F02": "administrador",   # Administrador de Agencia
    "F03": "operaciones",     # Jefe de Operaciones
    "F04": "riesgos",         # Jefe de Riesgos
    "F05": "comite",          # Funcionario de Créditos
    "E01": "asesor",          # Asesor de Negocios
    "E02": "operaciones",     # Asistente de Operaciones
    "E03": "analista",        # Analista de Créditos
    "E04": "operaciones",     # Auxiliar de Operaciones
}

ROL_POR_DEFECTO = "asesor"
ROLES_CORE = set(CARGO_A_ROL.values())
ROLES_RECUPERACIONES_OPERATIVO = ROLES_CORE - {"asesor"}


def rol_desde_cargo(codcargopersonal: str | None) -> str:
    if not codcargopersonal:
        return ROL_POR_DEFECTO
    return CARGO_A_ROL.get(codcargopersonal.strip(), ROL_POR_DEFECTO)


# Matriz de permisos por acción del flujo de otorgamiento (§7) + recuperaciones
PERMISOS = {
    "crear_solicitud":   {"asesor", "administrador"},
    "registrar_propuesta": {"asesor", "administrador"},
    "opinion_admin":     {"administrador"},
    "opinion_jefe_reg":  {"jefe_regional"},
    "opinion_riesgos":   {"riesgos", "analista"},
    "enviar_comite":     {"asesor", "administrador"},
    "resolver_comite":   {"comite", "administrador", "gerencia"},
    # Recuperaciones / Mora
    "consultar_mora":    ROLES_CORE,
    "gestionar_cobranza": ROLES_RECUPERACIONES_OPERATIVO,  # R2: todos excepto asesor
    "derivar_judicial":  ROLES_RECUPERACIONES_OPERATIVO,  # R3: todos excepto asesor
    "castigar_credito":  ROLES_RECUPERACIONES_OPERATIVO,  # R3: todos excepto asesor
}


def puede(rol: str, accion: str) -> bool:
    """True si el rol tiene permiso para la acción dada."""
    return rol in PERMISOS.get(accion, set())
