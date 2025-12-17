"""
Capa de automatización web con Selenium.
Gestiona toda la interacción con la intranet de imputación de horas.
"""

from .interactions import (
    hacer_login,
    volver_inicio,
    guardar_linea,
    emitir_linea,
    save_cookies
)

from .navigation import (
    seleccionar_fecha,
    lunes_de_semana
)

from .proyecto_handler import (
    seleccionar_proyecto,
    eliminar_linea_proyecto,
    imputar_horas_dia,
    imputar_horas_semana,
    borrar_todas_horas_dia,
    leer_tabla_imputacion,
    copiar_semana_anterior
)

from .jornada import (
    iniciar_jornada,
    finalizar_jornada
)

from .listado_proyectos_backup import (
    listar_todos_proyectos,
    formatear_lista_proyectos
)

__all__ = [
    # Interactions
    'hacer_login',
    'volver_inicio',
    'guardar_linea',
    'emitir_linea',
    'save_cookies',
    
    # Navigation
    'seleccionar_fecha',
    'lunes_de_semana',
    
    # Proyecto Handler
    'seleccionar_proyecto',
    'eliminar_linea_proyecto',
    'imputar_horas_dia',
    'imputar_horas_semana',
    'borrar_todas_horas_dia',
    'leer_tabla_imputacion',
    'copiar_semana_anterior',
    
    # Jornada
    'iniciar_jornada',
    'finalizar_jornada',
    
    # Listado Proyectos
    'listar_todos_proyectos',
    'formatear_lista_proyectos'
]
