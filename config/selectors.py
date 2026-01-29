"""
Selectores CSS y XPATH para la aplicación web de GestiónITT
"""


class Selectors:
    """Todos los selectores de la interfaz web de GestiónITT"""
    
    # ========================================
    # 🔐 LOGIN
    # ========================================
    USERNAME = '#usuario'
    PASSWORD = '#password'
    SUBMIT = '#btAceptar'
    ERROR_LOGIN = '.errorLogin'
    BOTON_SALIR = '.botonSalirHtml'
    
    # ========================================
    #  NAVEGACIÓN Y CALENDARIO
    # ========================================
    CALENDAR_BUTTON = '.ui-datepicker-trigger'
    DATEPICKER_CALENDAR = '.ui-datepicker-calendar'
    DATEPICKER_TITLE = '.ui-datepicker-title'
    DATEPICKER_NEXT = '.ui-datepicker-next'
    DATEPICKER_PREV = '.ui-datepicker-prev'
    VOLVER = '#btVolver'
    
    # ========================================
    #  IMPUTACIÓN DE HORAS
    # ========================================
    # Proyectos
    SELECT_SUBPROYECTO_NAME = "select[name*='subproyecto']"
    SELECT_SUBPROYECTO_ID = "select[id*='subproyecto']"
    SELECT_SUBPROYECTO_LISTA = "select[id^='listaEmpleadoHoras'][id$='.subproyecto']"
    
    # Botones de acción
    BTN_NUEVA_LINEA = '#btNuevaLinea'
    BTN_CAMBIAR_SUBPROYECTO = "input[id^='btCambiarSubproyecto']"
    BTN_GUARDAR_LINEA = '#btGuardarLinea'
    BTN_EMITIR = '#btEmitir'
    BTN_ELIMINAR = "button.botonEliminar, button#botonEliminar, input[id*='btEliminar']"
    
    # Campos de horas por día
    CAMPO_HORAS_DIA_TEMPLATE = "input[id$='.{dia_key}']"  # Usar .format(dia_key='h1')
    
    # ========================================
    #  BUSCADOR DE PROYECTOS
    # ========================================
    BUSCADOR_INPUT = '#textoBusqueda'
    BUSCADOR_BOTON = '#buscar'
    TREE_TIPOLOGIA = '#treeTipologia'
    
    # ========================================
    # ⏰ JORNADA LABORAL
    # ========================================
    BTN_INICIO_JORNADA = '#botonInicioJornada'
    BTN_FIN_JORNADA = '#botonFinJornada'
    
    # ========================================
    # 💬 DIÁLOGOS Y ERRORES
    # ========================================
    UI_DIALOG = '.ui-dialog, .modal, [role="dialog"]'
    DIALOG_CONTENT = '.ui-dialog-content, .modal-body, p'
    
    # ========================================
    #  XPATH ESPECÍFICOS
    # ========================================
    @staticmethod
    def xpath_dia_calendario(dia: int) -> str:
        """XPath para seleccionar un día específico en el calendario"""
        return f"//a[text()='{dia}']"
    
    @staticmethod
    def xpath_proyecto_tree(nombre_proyecto: str) -> str:
        """XPath para buscar un proyecto en el árbol de proyectos"""
        return (
            f"//li[@rel='subproyectos']//a[contains(translate(normalize-space(.), "
            f"'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), "
            f"'{nombre_proyecto.lower()}')]"
        )
    
    @staticmethod
    def campo_horas_dia(dia_key: str) -> str:
        """Selector para campo de horas de un día específico"""
        return f"input[id$='.{dia_key}']"
