"""
Utilidades para el manejo de información de proyectos.
Incluye funciones para parsear y formatear proyectos con su jerarquía completa.
"""


def parsear_path_proyecto(path_completo: str) -> dict:
    """
    Parsea el path completo de un proyecto y extrae sus componentes.
    
    El formato típico es: "Cliente - Departamento - Proyecto"
    También puede ser: "Cliente - Proyecto" o simplemente "Proyecto"
    
    Args:
        path_completo: String con el path completo del proyecto
                       Ej: "Arelance - Departamento Desarrollo - Estudio"
    
    Returns:
        dict con:
            - nombre: Nombre del proyecto (última parte)
            - departamento: Departamento/área (penúltima parte) o None
            - cliente: Cliente/empresa (primera parte) o None
            - path_completo: El path original completo
    """
    if not path_completo:
        return {
            "nombre": "",
            "departamento": None,
            "cliente": None,
            "path_completo": ""
        }
    
    partes = [p.strip() for p in path_completo.split(' - ')]
    
    resultado = {
        "nombre": partes[-1] if partes else "",
        "departamento": None,
        "cliente": None,
        "path_completo": path_completo
    }
    
    if len(partes) >= 2:
        resultado["departamento"] = partes[-2]
    
    if len(partes) >= 3:
        resultado["cliente"] = partes[0]
    
    return resultado


def formatear_proyecto_con_jerarquia(path_completo: str, formato: str = "completo") -> str:
    """
    Formatea el nombre del proyecto incluyendo su jerarquía.
    
    Args:
        path_completo: Path completo del proyecto
        formato: 
            - "completo": "Proyecto (Departamento - Cliente)"
            - "corto": "Proyecto (Departamento)"
            - "nombre": Solo el nombre del proyecto
    
    Returns:
        String formateado
    
    Ejemplos:
        >>> formatear_proyecto_con_jerarquia("Arelance - Dpto Desarrollo - Estudio", "completo")
        "Estudio (Dpto Desarrollo - Arelance)"
        
        >>> formatear_proyecto_con_jerarquia("Arelance - Dpto Desarrollo - Estudio", "corto")
        "Estudio (Dpto Desarrollo)"
        
        >>> formatear_proyecto_con_jerarquia("Arelance - Dpto Desarrollo - Estudio", "nombre")
        "Estudio"
    """
    info = parsear_path_proyecto(path_completo)
    
    if formato == "nombre":
        return info["nombre"]
    
    if formato == "corto":
        if info["departamento"]:
            return f"{info['nombre']} ({info['departamento']})"
        return info["nombre"]
    
    # formato == "completo"
    if info["cliente"] and info["departamento"]:
        return f"{info['nombre']} ({info['departamento']} - {info['cliente']})"
    elif info["departamento"]:
        return f"{info['nombre']} ({info['departamento']})"
    
    return info["nombre"]


def formatear_proyecto_para_respuesta(path_completo: str, incluir_cliente: bool = True) -> str:
    """
    Formatea el proyecto de forma natural para incluir en respuestas del bot.
    
    Args:
        path_completo: Path completo del proyecto
        incluir_cliente: Si True, incluye el cliente. Si False, solo departamento.
    
    Returns:
        String formateado de forma natural
    
    Ejemplos:
        >>> formatear_proyecto_para_respuesta("Arelance - Dpto Desarrollo - Estudio")
        "Estudio del Dpto Desarrollo (Arelance)"
        
        >>> formatear_proyecto_para_respuesta("Arelance - Dpto Desarrollo - Estudio", incluir_cliente=False)
        "Estudio del Dpto Desarrollo"
    """
    info = parsear_path_proyecto(path_completo)
    
    if not info["departamento"]:
        return info["nombre"]
    
    # Formato natural: "Proyecto del Departamento"
    resultado = f"{info['nombre']} del {info['departamento']}"
    
    if incluir_cliente and info["cliente"]:
        resultado += f" ({info['cliente']})"
    
    return resultado


def extraer_info_proyectos_tabla(proyectos_tabla: list) -> list:
    """
    Procesa una lista de proyectos de la tabla y añade información parseada.
    
    Args:
        proyectos_tabla: Lista de dicts con key 'proyecto' conteniendo el path completo
    
    Returns:
        La misma lista con campos adicionales:
            - nombre_corto: Solo el nombre del proyecto
            - departamento: El departamento
            - cliente: El cliente
            - nombre_formateado: Nombre con jerarquía
    """
    for proyecto in proyectos_tabla:
        path = proyecto.get('proyecto', '')
        info = parsear_path_proyecto(path)
        
        proyecto['nombre_corto'] = info['nombre']
        proyecto['departamento'] = info['departamento']
        proyecto['cliente'] = info['cliente']
        proyecto['nombre_formateado'] = formatear_proyecto_con_jerarquia(path, "corto")
    
    return proyectos_tabla
