"""
Core de negocio.
Lógica principal de imputación, consultas y ejecución de acciones.
"""

from .imputacion import (
    procesar_mensaje,
    iniciar_sesion_automatica,
    mostrar_mensaje_bienvenida,
    loop_interactivo
)

from .ejecutor import (
    ejecutar_accion,
    ejecutar_lista_acciones
)

from .consultas import (
    consultar_dia,
    consultar_semana,
    mostrar_comandos
)

__all__ = [
    # Imputación
    'procesar_mensaje',
    'iniciar_sesion_automatica',
    'mostrar_mensaje_bienvenida',
    'loop_interactivo',
    
    # Ejecutor
    'ejecutar_accion',
    'ejecutar_lista_acciones',
    
    # Consultas
    'consultar_dia',
    'consultar_semana',
    'mostrar_comandos'
]
