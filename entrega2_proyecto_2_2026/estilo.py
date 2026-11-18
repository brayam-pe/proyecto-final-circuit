# Hoja de estilo (QSS) del Virtual Lab: tema oscuro con acentos turquesa.
# QSS funciona igual que el CSS de las páginas web: "selector { propiedad: valor; }".
# Se aplica a toda la aplicación con una sola línea en ventana_login.py: app.setStyleSheet(ESTILO)
# Dentro del texto los comentarios se escriben entre /* y */ (así se comenta en QSS).

ESTILO = """
/* Todas las ventanas: fondo oscuro, letra clara y fuente Segoe UI de 11 puntos */
QMainWindow, QWidget { background: #1b1f27; color: #e3e7ee; font-family: 'Segoe UI'; font-size: 11pt; }

/* Las etiquetas no llevan fondo propio (toman el de la ventana) */
QLabel { background: transparent; }

/* Etiqueta con nombre "titulo": letra grande, en negrilla y turquesa */
QLabel#titulo { font-size: 18pt; font-weight: 600; color: #4fd1c5; }

/* Etiqueta con nombre "subtitulo": letra pequeña y gris */
QLabel#subtitulo { color: #8b95a7; font-size: 10pt; }

/* Campos de texto y listas desplegables: fondo un poco más claro, borde gris y esquinas redondeadas */
QLineEdit, QComboBox { background: #252b36; border: 1px solid #3a4352; border-radius: 6px; padding: 6px 8px; color: #e3e7ee; }

/* Cuando el usuario está escribiendo en el campo, el borde se pone turquesa */
QLineEdit:focus, QComboBox:focus { border: 2px solid #4fd1c5; }

/* Las opciones que aparecen al abrir el combo también van oscuras */
QComboBox QAbstractItemView { background: #252b36; color: #e3e7ee; selection-background-color: #2f5f5b; }

/* Listas y cajas de texto: fondo oscuro, borde gris y esquinas redondeadas */
QListWidget, QTextEdit { background: #232833; border: 1px solid #3a4352; border-radius: 6px; padding: 4px; color: #e3e7ee; }

/* Cada renglón de las listas tiene un poco de espacio interno */
QListWidget::item { padding: 5px; border-radius: 4px; }

/* Renglón seleccionado: fondo turquesa oscuro y letra blanca */
QListWidget::item:selected { background: #2f5f5b; color: #ffffff; }

/* Botones normales: gris oscuro con esquinas redondeadas */
QPushButton { background: #2a313d; border: 1px solid #3f4858; border-radius: 6px; padding: 7px 14px; color: #e3e7ee; }

/* Cuando el mouse pasa por encima de un botón, se aclara un poco */
QPushButton:hover { background: #333b49; }

/* Botón con nombre "primario" (la acción principal): turquesa con letra oscura en negrilla */
QPushButton#primario { background: #2bb3a6; color: #0f1a1a; border: none; font-weight: 600; }

/* Botón primario con el mouse encima: un turquesa un poco más claro */
QPushButton#primario:hover { background: #3cc7ba; }

/* Botones apagados (setEnabled(False)): se ven grises para que se note que no funcionan */
QPushButton:disabled, QPushButton#primario:disabled { background: #262c36; color: #5d6676; border: 1px solid #2f3643; }

/* Botón con nombre "salir": sin relleno, con letra y borde rojizos */
QPushButton#salir { background: transparent; color: #ff8a80; border: 1px solid #5a3b3b; }

/* Etiqueta con nombre "imagen" (donde va el circuito): fondo blanco para que el dibujo se vea bien */
QLabel#imagen { background: #ffffff; color: #1b1f27; border: 1px solid #3a4352; border-radius: 6px; }
"""
