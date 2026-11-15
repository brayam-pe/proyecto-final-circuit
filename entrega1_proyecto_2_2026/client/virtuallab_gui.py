"""Gestion grafica de cuentas y laboratorios, simulacion transitoria para estudiantes."""
from __future__ import annotations

import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from html import escape
from pathlib import Path

import requests
from PySpice.Spice.Parser import SpiceParser
from PySpice.Unit import u_ms
from PyQt5.QtCore import QByteArray, Qt, QTimer, QPointF, QRectF, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtWidgets import (
    QApplication, QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFormLayout,
    QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow,
    QMessageBox, QPushButton, QSlider, QTabWidget, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

PROJECT_DIR = Path(__file__).resolve().parents[1]
CLIENT_LABS_DIR = PROJECT_DIR / "client" / "labs"
SERVER_URL = "http://localhost:80"
ET.register_namespace("", "http://www.w3.org/2000/svg")


def generate_schematic_svg(lab_name, netlist):
    """Draw a complete ladder circuit in the teammate's Schemdraw visual style."""
    node_counts = {"R": 2, "C": 2, "L": 2, "V": 2, "I": 2, "D": 2,
                   "Q": 3, "J": 3, "M": 4, "E": 4, "G": 4}
    components = []
    for raw_line in netlist.replace("\r", "\n").split("\n"):
        line = raw_line.strip()
        if not line or line.startswith(("*", ";", ".")):
            continue
        parts = line.split()
        prefix = parts[0][0].upper()
        node_count = node_counts.get(prefix)
        if node_count is None or len(parts) < node_count + 2:
            continue
        components.append((parts[0], prefix, parts[1:1 + node_count], " ".join(parts[1 + node_count:])))

    def is_ground(node):
        return node.casefold() in {"0", "gnd", "ground"}

    source = next((item for item in components
                   if item[1] in ("V", "I") and len(item[2]) == 2
                   and any(is_ground(node) for node in item[2])), None)
    if source:
        input_node = next(node for node in source[2] if not is_ground(node))
    else:
        first_terminal = next((node for item in components for node in item[2] if not is_ground(node)), "input")
        input_node = first_terminal

    # Follow the non-ground passive path from the source. Components connected
    # from a path node to ground become vertical branches, like the colleague's
    # voltage divider and RC schematics.
    passive = [item for item in components if item[1] in ("R", "C", "L", "D") and len(item[2]) == 2]
    chain_nodes = [input_node]
    series_components = []
    used = set()
    current = input_node
    while True:
        candidate = next((item for item in passive
                          if id(item) not in used
                          and all(not is_ground(node) for node in item[2])
                          and any(node.casefold() == current.casefold() for node in item[2])
                          and any(node.casefold() != current.casefold() for node in item[2])), None)
        if candidate is None:
            break
        next_node = next(node for node in candidate[2] if node.casefold() != current.casefold())
        series_components.append(candidate)
        used.add(id(candidate))
        chain_nodes.append(next_node)
        current = next_node

    node_x = {node.casefold(): 280 + index * 270 for index, node in enumerate(chain_nodes)}
    shunts = []
    for item in passive:
        if id(item) in used:
            continue
        grounded = [node for node in item[2] if is_ground(node)]
        signal_nodes = [node for node in item[2] if not is_ground(node)]
        if grounded and signal_nodes and signal_nodes[0].casefold() in node_x:
            shunts.append((item, signal_nodes[0]))
            used.add(id(item))

    extras = [item for item in components
              if item is not source and id(item) not in used
              and len(item[2]) >= 2
              and all(node.casefold() in node_x for node in item[2][:2])
              and not is_ground(item[2][0]) and not is_ground(item[2][1])]

    width = max(700, node_x[chain_nodes[-1].casefold()] + 180)
    top_y, bottom_y, source_x = 135, 390, 140
    shunt_counts = {}
    for _, node in shunts:
        key = node.casefold()
        shunt_counts[key] = shunt_counts.get(key, 0) + 1
    branch_xs, branch_offsets = [], {}
    for _, node in shunts:
        key = node.casefold()
        count = shunt_counts[key]
        index = branch_offsets.get(key, 0)
        branch_offsets[key] = index + 1
        branch_xs.append(node_x[key] + (index - (count - 1) / 2) * 38)
    return_end = max([source_x, *branch_xs])
    height = bottom_y + 90 + max(0, len(extras) - 1) * 65
    ink = "#111111"
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width / 2:.0f}" y="34" text-anchor="middle" font-family="Arial" font-size="22" font-weight="bold" fill="{ink}">{escape(str(lab_name))}</text>',
        f'<g fill="none" stroke="{ink}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round">',
        f'<path d="M {source_x} {top_y} V 215 M {source_x} 305 V {bottom_y} H {return_end}"/>',
        f'<path d="M {source_x} {top_y} H {node_x[chain_nodes[0].casefold()]}"/>',
        f'<circle cx="{source_x}" cy="260" r="45" fill="white"/>',
        f'<path d="M {source_x} 242 V 254 M {source_x - 7} 248 H {source_x + 7} M {source_x - 7} 274 H {source_x + 7}" stroke-width="3"/>',
        '</g>',
    ]

    def add_node(node, x, y):
        label = escape(node, quote=True)
        out.append(f'<circle data-node="{label}" cx="{x}" cy="{y}" r="7" fill="{ink}" stroke="white" stroke-width="1"/>')
        out.append(f'<text x="{x}" y="{y - 18}" text-anchor="middle" font-family="Arial" font-size="14" fill="{ink}">{escape(node)}</text>')

    def add_label(text, x, y, anchor="middle"):
        lines = text.split("\n")
        for line_index, line in enumerate(lines):
            out.append(f'<text x="{x:.1f}" y="{y + line_index * 18:.1f}" text-anchor="{anchor}" font-family="Arial" font-size="15" fill="{ink}">{escape(line)}</text>')

    def symbol_horizontal(prefix, x1, x2, y):
        center = (x1 + x2) / 2
        left, right = center - 48, center + 48
        out.append(f'<path d="M {x1} {y} H {left} M {right} {y} H {x2}" fill="none" stroke="{ink}" stroke-width="4"/>')
        if prefix == "R":
            coords = [f'{left + i * 12} {y + (-10 if i % 2 else 10)}' for i in range(9)]
            out.append(f'<polyline points="{left} {y} {" ".join(coords)} {right} {y}" fill="none" stroke="{ink}" stroke-width="4" stroke-linejoin="round"/>')
        elif prefix == "C":
            out.append(f'<path d="M {left} {y} H {center - 8} M {center - 8} {y - 25} V {y + 25} M {center + 8} {y - 25} V {y + 25} M {center + 8} {y} H {right}" fill="none" stroke="{ink}" stroke-width="4"/>')
        elif prefix == "L":
            out.append(f'<path d="M {left} {y} c 8 -22 16 -22 24 0 c 8 -22 16 -22 24 0 c 8 -22 16 -22 24 0 c 8 -22 16 -22 24 0" fill="none" stroke="{ink}" stroke-width="4"/>')
        elif prefix == "D":
            out.append(f'<path d="M {center - 18} {y - 18} L {center + 12} {y} L {center - 18} {y + 18} Z M {center + 18} {y - 20} V {y + 20}" fill="white" stroke="{ink}" stroke-width="4"/>')
        else:
            out.append(f'<rect x="{center - 24}" y="{y - 20}" width="48" height="40" fill="white" stroke="{ink}" stroke-width="4"/>')
            add_label(prefix, center, y + 5)

    def symbol_vertical(prefix, x, y1, y2):
        center = (y1 + y2) / 2
        top, bottom = center - 48, center + 48
        out.append(f'<path d="M {x} {y1} V {top} M {x} {bottom} V {y2}" fill="none" stroke="{ink}" stroke-width="4"/>')
        if prefix == "R":
            coords = [f'{x + (-10 if i % 2 else 10)} {top + i * 12}' for i in range(9)]
            out.append(f'<polyline points="{x} {top} {" ".join(coords)} {x} {bottom}" fill="none" stroke="{ink}" stroke-width="4" stroke-linejoin="round"/>')
        elif prefix == "C":
            out.append(f'<path d="M {x} {y1} V {center - 8} M {x - 25} {center - 8} H {x + 25} M {x - 25} {center + 8} H {x + 25} M {x} {center + 8} V {y2}" fill="none" stroke="{ink}" stroke-width="4"/>')
        elif prefix == "L":
            out.append(f'<path d="M {x} {top} c 22 8 22 16 0 24 c 22 8 22 16 0 24 c 22 8 22 16 0 24 c 22 8 22 16 0 24" fill="none" stroke="{ink}" stroke-width="4"/>')
        else:
            out.append(f'<rect x="{x - 20}" y="{center - 24}" width="40" height="48" fill="white" stroke="{ink}" stroke-width="4"/>')
            add_label(prefix, x + 32, center + 5, "start")

    add_label(source[0] if source else "Fuente", source_x, 68)
    if source:
        add_label(source[3] or source[1], source_x, 88)
    for index, node in enumerate(chain_nodes):
        add_node(node, node_x[node.casefold()], top_y)
    add_node("0", source_x, bottom_y)
    add_label("GND", source_x, bottom_y + 48)

    for index, item in enumerate(series_components):
        x1 = node_x[chain_nodes[index].casefold()]
        x2 = node_x[chain_nodes[index + 1].casefold()]
        symbol_horizontal(item[1], x1 + 10, x2 - 10, top_y)
        value = item[3] or item[1]
        add_label(f"{item[0]}\n{value}", (x1 + x2) / 2, top_y - 72)

    by_node = {}
    for item, node in shunts:
        by_node.setdefault(node.casefold(), []).append(item)
    for node_key, items in by_node.items():
        x = node_x[node_key]
        count = len(items)
        for index, item in enumerate(items):
            branch_x = x + (index - (count - 1) / 2) * 38
            out.append(f'<path d="M {x} {top_y} H {branch_x} V 195" fill="none" stroke="{ink}" stroke-width="4"/>')
            symbol_vertical(item[1], branch_x, 195, 325)
            out.append(f'<path d="M {branch_x} 325 V {bottom_y}" fill="none" stroke="{ink}" stroke-width="4"/>')
            label_anchor = "end" if index <= (count - 1) / 2 else "start"
            label_x = branch_x - 30 if label_anchor == "end" else branch_x + 30
            add_label(f"{item[0]}\n{item[3] or item[1]}", label_x, 245, label_anchor)

    # Parallel components between visible nodes are drawn as connected lower
    # branches, retaining their terminal node names and the same symbol style.
    for index, item in enumerate(extras):
        x1, x2 = node_x[item[2][0].casefold()], node_x[item[2][1].casefold()]
        lane_y = 210 + index * 65
        left, right = sorted((x1, x2))
        out.append(f'<path d="M {x1} {top_y} V {lane_y} M {x2} {top_y} V {lane_y}" fill="none" stroke="{ink}" stroke-width="3"/>')
        symbol_horizontal(item[1], left, right, lane_y)
        add_label(f"{item[0]} {item[3] or item[1]}", (left + right) / 2, lane_y - 32)

    out.append(f'<path d="M {source_x - 20} {bottom_y + 8} H {source_x + 20} M {source_x - 14} {bottom_y + 17} H {source_x + 14} M {source_x - 7} {bottom_y + 26} H {source_x + 7}" fill="none" stroke="{ink}" stroke-width="3"/>')
    out.append('</svg>')
    return "\n".join(out)


class TransientPlot(QWidget):
    """Small Qt plotter that draws transient node voltages without extra packages."""

    COLORS = [QColor("#2563eb"), QColor("#dc2626"), QColor("#16a34a"),
              QColor("#9333ea"), QColor("#ea580c"), QColor("#0891b2"),
              QColor("#be123c"), QColor("#4d7c0f")]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.times = []
        self.series = {}
        self.current_index = 0
        self.setMinimumHeight(260)

    def set_data(self, times, series):
        self.times = list(times)
        self.series = {name: list(values) for name, values in series.items()}
        self.current_index = 0
        self.update()

    def set_current_index(self, index):
        self.current_index = max(0, index)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("white"))
        if not self.times or not self.series:
            painter.setPen(QColor("#64748b"))
            painter.drawText(self.rect(), Qt.AlignCenter, "Ejecuta una simulacion transitoria para ver los voltajes.")
            return

        plot = QRectF(68, 48, max(100, self.width() - 92), max(100, self.height() - 94))
        all_values = [value for values in self.series.values() for value in values]
        t_min, t_max = min(self.times), max(self.times)
        v_min, v_max = min(all_values), max(all_values)
        if t_max == t_min:
            t_max = t_min + 1e-9
        if v_max == v_min:
            padding = max(abs(v_max) * 0.1, 0.1)
            v_min, v_max = v_min - padding, v_max + padding
        else:
            padding = (v_max - v_min) * 0.08
            v_min, v_max = v_min - padding, v_max + padding

        painter.setFont(painter.font())
        for tick in range(5):
            fraction = tick / 4
            y = plot.bottom() - fraction * plot.height()
            value = v_min + fraction * (v_max - v_min)
            painter.setPen(QPen(QColor("#e2e8f0"), 1))
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            painter.setPen(QColor("#475569"))
            painter.drawText(QRectF(0, y - 9, 61, 18), Qt.AlignRight | Qt.AlignVCenter, f"{value:.3g} V")

        for tick in range(5):
            fraction = tick / 4
            x = plot.left() + fraction * plot.width()
            value_ms = (t_min + fraction * (t_max - t_min)) * 1000
            painter.setPen(QPen(QColor("#e2e8f0"), 1))
            painter.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()))
            painter.setPen(QColor("#475569"))
            painter.drawText(QRectF(x - 34, plot.bottom() + 5, 68, 17), Qt.AlignHCenter, f"{value_ms:.3g}")

        painter.setPen(QColor("#334155"))
        painter.drawText(QRectF(plot.left(), self.height() - 22, plot.width(), 18), Qt.AlignCenter, "Tiempo (ms)")
        painter.save()
        painter.translate(16, plot.center().y())
        painter.rotate(-90)
        painter.drawText(QRectF(-plot.height()/2, -9, plot.height(), 18), Qt.AlignCenter, "Voltaje (V)")
        painter.restore()

        for series_index, (name, values) in enumerate(self.series.items()):
            if len(values) != len(self.times):
                continue
            color = self.COLORS[series_index % len(self.COLORS)]
            painter.setPen(QPen(color, 2))
            path = QPainterPath()
            stride = max(1, len(self.times) // 1800)
            points = list(range(0, len(self.times), stride))
            if points[-1] != len(self.times) - 1:
                points.append(len(self.times) - 1)
            for point_index, sample in enumerate(points):
                x = plot.left() + (self.times[sample] - t_min) / (t_max - t_min) * plot.width()
                y = plot.bottom() - (values[sample] - v_min) / (v_max - v_min) * plot.height()
                if point_index == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
            painter.drawPath(path)
            legend_x = plot.left() + (series_index % 4) * (plot.width() / 4)
            legend_y = 17 + (series_index // 4) * 16
            painter.setPen(QPen(color, 3))
            painter.drawLine(QPointF(legend_x, legend_y), QPointF(legend_x + 16, legend_y))
            painter.setPen(QColor("#334155"))
            painter.drawText(QPointF(legend_x + 21, legend_y + 4), name)

        if len(self.times) > 1:
            index = min(self.current_index, len(self.times) - 1)
            x = plot.left() + (self.times[index] - t_min) / (t_max - t_min) * plot.width()
            painter.setPen(QPen(QColor("#0f172a"), 1, Qt.DashLine))
            painter.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()))
        painter.setPen(QPen(QColor("#64748b"), 1))
        painter.drawRect(plot)


class InteractiveCircuitDiagram(QWidget):
    """Render a schematic once and overlay fast voltage markers and hover labels."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.renderer = QSvgRenderer()
        self.image = QPixmap()
        self.node_positions = {}
        self.node_values = {}
        self.color_function = None
        self.hovered_node = None
        self.setMouseTracking(True)
        self.setMinimumHeight(300)

    def set_svg(self, svg_text):
        self.image = QPixmap()
        self.node_positions.clear()
        self.hovered_node = None
        if not svg_text:
            self.renderer.load(QByteArray())
            self.update()
            return
        try:
            root = ET.fromstring(svg_text)
            parents = {child: parent for parent in root.iter() for child in parent}
            for element in list(root.iter()):
                node_name = element.attrib.get("data-node")
                if node_name and "cx" in element.attrib and "cy" in element.attrib:
                    self.node_positions[node_name.casefold()] = (
                        node_name, QPointF(float(element.attrib["cx"]), float(element.attrib["cy"]))
                    )
                if "data-node-value" in element.attrib:
                    parent = parents.get(element)
                    if parent is not None:
                        parent.remove(element)
            self.renderer.load(QByteArray(ET.tostring(root, encoding="utf-8")))
        except (ET.ParseError, ValueError):
            self.renderer.load(QByteArray(svg_text.encode("utf-8")))
        self.update()

    def set_png(self, png_bytes, lab_name):
        """Use a full-circuit PNG and attach live voltage to its output node."""
        self.renderer.load(QByteArray())
        self.node_positions.clear()
        self.hovered_node = None
        self.image = QPixmap()
        if not self.image.loadFromData(png_bytes, "PNG"):
            raise ValueError("El archivo PNG del circuito no se pudo leer.")

        # Coordinates are the output dots in the teammate's schemdraw diagrams.
        # They are only used for these two known PNG layouts; other diagrams can
        # provide SVG node markers or fall back to the generated schematic.
        key = Path(lab_name).stem.casefold()
        if key == "rc" or key.startswith("rc_"):
            label, point = "output", QPointF(431, 94)
            self.node_positions[label.casefold()] = (label, point)
        elif key == "voltage_divider" or key.startswith("voltage_divider_"):
            label, point = "vout", QPointF(322, 94)
            self.node_positions[label.casefold()] = (label, point)
        self.update()

    def set_node_state(self, values, color_function):
        self.node_values = {name.casefold(): value for name, value in values.items()}
        self.color_function = color_function
        self.update()

    def _drawing_transform(self):
        if not self.image.isNull():
            view = QRectF(0, 0, self.image.width(), self.image.height())
        else:
            view = self.renderer.viewBoxF()
        if ((self.image.isNull() and not self.renderer.isValid()) or
                view.width() <= 0 or view.height() <= 0):
            return QRectF(), 1.0, view
        bounds = self.rect().adjusted(4, 4, -4, -4)
        scale = min(bounds.width() / view.width(), bounds.height() / view.height())
        width, height = view.width() * scale, view.height() * scale
        target = QRectF(bounds.center().x() - width / 2, bounds.center().y() - height / 2, width, height)
        return target, scale, view

    def _screen_point(self, point, target, scale, view):
        return QPointF(target.left() + (point.x() - view.x()) * scale,
                       target.top() + (point.y() - view.y()) * scale)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("white"))
        target, scale, view = self._drawing_transform()
        if not target.isNull():
            if not self.image.isNull():
                painter.drawPixmap(target, self.image, QRectF(self.image.rect()))
            else:
                self.renderer.render(painter, target)
        for key, (label, svg_point) in self.node_positions.items():
            if key not in self.node_values or self.color_function is None or target.isNull():
                continue
            point = self._screen_point(svg_point, target, scale, view)
            color = self.color_function(self.node_values[key])
            radius = max(6.0, 8.0 * scale)
            painter.setPen(QPen(QColor("#0f172a"), 1.5))
            painter.setBrush(color)
            painter.drawEllipse(point, radius, radius)
            if key == self.hovered_node:
                text = f"{label}: {self.node_values[key]:.4f} V"
                metrics = painter.fontMetrics()
                box_width = metrics.horizontalAdvance(text) + 18
                box_height = metrics.height() + 10
                box = QRectF(point.x() - box_width / 2,
                            point.y() - radius - box_height - 7,
                            box_width, box_height)
                if box.top() < 3:
                    box.moveTop(point.y() + radius + 7)
                box.moveLeft(max(3, min(box.left(), self.width() - box_width - 3)))
                painter.setPen(QPen(color.darker(135), 1.5))
                painter.setBrush(QColor("#ffffff"))
                painter.drawRoundedRect(box, 5, 5)
                painter.setPen(QColor("#0f172a"))
                painter.drawText(box, Qt.AlignCenter, text)

    def mouseMoveEvent(self, event):
        target, scale, view = self._drawing_transform()
        hovered = None
        if not target.isNull():
            cursor = QPointF(event.pos())
            for key, (_, svg_point) in self.node_positions.items():
                point = self._screen_point(svg_point, target, scale, view)
                if key in self.node_values and (cursor - point).manhattanLength() <= max(16, 14 * scale):
                    hovered = key
                    break
        if hovered != self.hovered_node:
            self.hovered_node = hovered
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        if self.hovered_node is not None:
            self.hovered_node = None
            self.update()
        super().leaveEvent(event)


class TransientSimulationWorker(QThread):
    completed = pyqtSignal(object, object)
    failed = pyqtSignal(str)

    def __init__(self, netlist, end_ms, parent=None):
        super().__init__(parent)
        self.netlist = netlist
        self.end_ms = end_ms

    def run(self):
        try:
            lines = self.netlist.replace("\r\n", "\n").splitlines()
            netlist = "\r\n".join(
                line for line in lines
                if not re.match(r"^\s*\.(op|tran|ac|dc)(\s|$)", line, re.IGNORECASE)
            )
            circuit = SpiceParser(source=netlist).build_circuit()
            if not list(circuit.element_names):
                raise ValueError("No se reconocieron componentes en el archivo .cir.")
            step_ms = self.end_ms / 1000.0
            simulator = circuit.simulator(temperature=25, nominal_temperature=25)
            analysis = simulator.transient(step_time=u_ms(step_ms), end_time=u_ms(self.end_ms))
            times = [float(value) for value in analysis.time]
            series = {
                str(waveform.name): [float(value) for value in waveform]
                for waveform in analysis.nodes.values()
            }
            if not times or not series:
                raise ValueError("La simulacion no devolvio voltajes de nodos.")
            self.completed.emit(times, series)
        except Exception as exc:
            self.failed.emit(str(exc))


class LoginDialog(QDialog):
    """Compact main screen with sign-in and role-aware registration tabs."""

    authenticated = pyqtSignal(str, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Laboratorio virtual")
        self.setFixedSize(430, 390)
        layout = QVBoxLayout(self)
        title = QLabel("Laboratorio virtual de circuitos")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #17365d;")
        layout.addWidget(title)

        self.pages = QTabWidget()
        login_page = QWidget()
        login_form = QFormLayout(login_page)
        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText("Identificacion")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Contrasena")
        self.login_role = QComboBox()
        self.login_role.addItem("Estudiante", "student")
        self.login_role.addItem("Docente", "professor")
        self.password_input.returnPressed.connect(self.authenticate)
        login_form.addRow("ID:", self.id_input)
        login_form.addRow("Contrasena:", self.password_input)
        login_form.addRow("Ingresar como:", self.login_role)
        self.login_button = QPushButton("Iniciar sesion")
        self.login_button.clicked.connect(self.authenticate)
        login_form.addRow(self.login_button)
        self.pages.addTab(login_page, "Iniciar sesion")

        register_page = QWidget()
        register_form = QFormLayout(register_page)
        self.register_name = QLineEdit()
        self.register_name.setPlaceholderText("Nombre completo")
        self.register_id = QLineEdit()
        self.register_id.setPlaceholderText("Identificacion")
        self.register_password = QLineEdit()
        self.register_password.setEchoMode(QLineEdit.Password)
        self.register_password.setPlaceholderText("Contrasena")
        self.register_role = QComboBox()
        self.register_role.addItem("Estudiante", "student")
        self.register_role.addItem("Docente", "professor")
        register_form.addRow("Nombre:", self.register_name)
        register_form.addRow("ID:", self.register_id)
        register_form.addRow("Contrasena:", self.register_password)
        register_form.addRow("Crear cuenta como:", self.register_role)
        self.register_button = QPushButton("Crear cuenta")
        self.register_button.clicked.connect(self.register_account)
        register_form.addRow(self.register_button)
        self.pages.addTab(register_page, "Registrarse")
        layout.addWidget(self.pages)

        self.status = QLabel("Inicia sesion o crea una cuenta y elige el rol.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

    def register_account(self):
        name = self.register_name.text().strip()
        user_id = self.register_id.text().strip()
        password = self.register_password.text()
        if not name or not user_id or not password:
            self._error("Completa nombre, identificacion y contrasena.")
            return
        self.register_button.setEnabled(False)
        try:
            response = requests.post(f"{SERVER_URL}/register", data={
                "name": name, "id": user_id, "role": self.register_role.currentData(),
                "password": password,
            }, timeout=10)
            response.raise_for_status()
            result = response.text.strip()
            if not result.startswith("User ") or " with role " not in result or not result.endswith(" registered"):
                self._error(result or "El servidor rechazo los datos.")
                return
            self.id_input.setText(user_id)
            self.password_input.setText(password)
            self.login_role.setCurrentIndex(self.login_role.findData(self.register_role.currentData()))
            self.pages.setCurrentIndex(0)
            self.status.setText(f"Cuenta de {self.register_role.currentText().lower()} creada. Inicia sesion.")
            self.register_name.clear()
            self.register_id.clear()
            self.register_password.clear()
        except requests.RequestException as exc:
            self._error(f"No se pudo registrar la cuenta: {exc}")
        finally:
            self.register_button.setEnabled(True)

    def authenticate(self):
        user_id = self.id_input.text().strip()
        password = self.password_input.text()
        if not user_id or not password:
            self._error("Escribe el ID y la contrasena.")
            return
        self.login_button.setEnabled(False)
        self.status.setText("Validando usuario...")
        try:
            response = requests.post(f"{SERVER_URL}/login",
                                     data={"id": user_id, "password": password}, timeout=10)
            if response.status_code != 200 or "succesfully opened" not in response.text:
                self._error(f"No se pudo iniciar sesion: {response.text.strip()}")
                return
            profile = requests.post(f"{SERVER_URL}/user_info", data={"id": user_id}, timeout=10)
            profile.raise_for_status()
            user = profile.json()
            role = user.get("role")
            if role not in ("student", "professor"):
                requests.post(f"{SERVER_URL}/logout", data={"id": user_id}, timeout=10)
                self._error("El servidor devolvio un tipo de usuario desconocido.")
                return
            if role != self.login_role.currentData():
                requests.post(f"{SERVER_URL}/logout", data={"id": user_id}, timeout=10)
                self._error("El rol seleccionado no corresponde a esta cuenta.")
                return
            self.authenticated.emit(user_id, role, user.get("name", ""))
        except (requests.RequestException, ValueError) as exc:
            self._error(f"No se pudo comunicar con el servidor: {exc}")
        finally:
            self.login_button.setEnabled(True)

    def reset(self):
        self.id_input.clear()
        self.password_input.clear()
        self.status.setText("Inicia sesion o crea una cuenta y elige el rol.")
        self.pages.setCurrentIndex(0)

    def _error(self, message):
        self.status.setText(message)
        QMessageBox.warning(self, "Laboratorio virtual", message)


class VirtualLabWindow(QMainWindow):
    session_closed = pyqtSignal()

    def __init__(self, user_id, user_role, user_name=""):
        super().__init__()
        self.setWindowTitle("Laboratorio virtual de circuitos")
        self.resize(1040, 680) if user_role == "professor" else self.resize(1180, 900)
        self.user_id = user_id
        self.user_role = user_role
        self.user_name = user_name
        self.selected_lab = None
        self.netlist = ""
        self.svg_template = ""
        self.transient_times = []
        self.node_series = {}
        self.color_scale = 1.0
        self.simulation_worker = None
        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self._advance_animation)
        self._build_ui()
        if self.user_role == "student":
            self.refresh_student_labs()
        else:
            self.refresh_teacher_data()

    def _build_ui(self):
        root = QWidget()
        layout = QVBoxLayout(root)
        title = QLabel("Laboratorio virtual de circuitos")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #17365d;")
        layout.addWidget(title)

        account = QHBoxLayout()
        display_role = "Estudiante" if self.user_role == "student" else "Docente"
        self.account_label = QLabel(f"Sesion: {self.user_name} - {display_role} ({self.user_id})")
        account.addWidget(self.account_label, 1)
        self.logout_button = QPushButton("Cerrar sesion")
        self.logout_button.clicked.connect(self.close_session)
        account.addWidget(self.logout_button)
        layout.addLayout(account)

        self.status = QLabel("Selecciona una practica para continuar.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.tabs = QTabWidget()
        self.student_tab = self._build_student_tab()
        self.teacher_tab = self._build_teacher_tab()
        if self.user_role == "student":
            self.tabs.addTab(self.student_tab, "Estudiante")
        else:
            self.tabs.addTab(self.teacher_tab, "Docente")
        layout.addWidget(self.tabs, 1)
        self.setCentralWidget(root)

    def _build_student_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        row = QHBoxLayout()
        self.student_labs = QComboBox()
        self.refresh_student_button = QPushButton("Actualizar mis laboratorios")
        self.refresh_student_button.clicked.connect(self.refresh_student_labs)
        self.download_button = QPushButton("Descargar laboratorio")
        self.download_button.setEnabled(False)
        self.download_button.clicked.connect(self.download_lab)
        row.addWidget(self.student_labs, 1)
        row.addWidget(self.refresh_student_button)
        row.addWidget(self.download_button)
        layout.addLayout(row)

        self.diagram = InteractiveCircuitDiagram()
        self.diagram.setStyleSheet("background: white; border: 1px solid #cbd5e1;")
        layout.addWidget(self.diagram, 2)

        simulation = QHBoxLayout()
        self.duration = QDoubleSpinBox()
        self.duration.setRange(0.1, 1000.0)
        self.duration.setDecimals(1)
        self.duration.setSingleStep(1.0)
        self.duration.setValue(10.0)
        self.simulate_button = QPushButton("Simular voltajes en el tiempo")
        self.simulate_button.setEnabled(False)
        self.simulate_button.clicked.connect(self.simulate_transient)
        simulation.addWidget(QLabel("Duracion (ms):"))
        simulation.addWidget(self.duration)
        simulation.addWidget(self.simulate_button)
        layout.addLayout(simulation)

        self.plot = TransientPlot()
        layout.addWidget(self.plot, 2)
        playback = QHBoxLayout()
        self.play_button = QPushButton("Reproducir cambios")
        self.play_button.setEnabled(False)
        self.play_button.clicked.connect(self.toggle_animation)
        self.time_slider = QSlider(Qt.Horizontal)
        self.time_slider.setEnabled(False)
        self.time_slider.valueChanged.connect(self.update_voltage_frame)
        self.time_label = QLabel("t = -- ms")
        playback.addWidget(self.play_button)
        playback.addWidget(self.time_slider, 1)
        playback.addWidget(self.time_label)
        layout.addLayout(playback)

        self.node_table = QTableWidget(0, 2)
        self.node_table.setHorizontalHeaderLabels(["Nodo", "Voltaje instantaneo"])
        self.node_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.node_table.setMaximumHeight(150)
        layout.addWidget(self.node_table)
        return tab

    def _build_teacher_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        upload = QGroupBox("Laboratorios")
        upload_layout = QHBoxLayout(upload)
        self.upload_path_label = QLabel("Ningun archivo seleccionado")
        self.upload_path_label.setWordWrap(True)
        self.upload_button = QPushButton("Elegir ZIP y cargar")
        self.upload_button.clicked.connect(self.upload_lab)
        self.refresh_teacher_button = QPushButton("Actualizar listas")
        self.refresh_teacher_button.clicked.connect(self.refresh_teacher_data)
        upload_layout.addWidget(self.upload_path_label, 1)
        upload_layout.addWidget(self.upload_button)
        upload_layout.addWidget(self.refresh_teacher_button)
        layout.addWidget(upload)

        assignment = QGroupBox("Asignar varios laboratorios a varios estudiantes")
        assign_layout = QVBoxLayout(assignment)
        selections = QHBoxLayout()
        self.teacher_labs = QListWidget()
        self.teacher_labs.setSelectionMode(QListWidget.MultiSelection)
        self.teacher_labs.setMinimumHeight(135)
        self.teacher_labs.setMaximumHeight(210)
        self.students = QListWidget()
        self.students.setSelectionMode(QListWidget.MultiSelection)
        self.students.setMinimumHeight(135)
        self.students.setMaximumHeight(210)
        labs_column = QVBoxLayout()
        labs_column.addWidget(QLabel("Laboratorios · Ctrl/Shift para varios"))
        labs_column.addWidget(self.teacher_labs)
        students_column = QVBoxLayout()
        students_column.addWidget(QLabel("Estudiantes · Ctrl/Shift para varios"))
        students_column.addWidget(self.students)
        selections.addLayout(labs_column, 1)
        selections.addLayout(students_column, 1)
        assign_layout.addLayout(selections)
        self.assign_button = QPushButton("Asignar seleccionados")
        self.assign_button.clicked.connect(self.assign_lab)
        assign_layout.addWidget(self.assign_button)
        layout.addWidget(assignment, 1)
        return tab

    def upload_lab(self):
        if self.user_role != "professor":
            self._error("Inicia sesion como docente para cargar laboratorios.")
            return
        file_path, _ = QFileDialog.getOpenFileName(self, "Seleccionar laboratorio ZIP", "", "Archivos ZIP (*.zip)")
        if not file_path:
            return
        path = Path(file_path)
        try:
            with path.open("rb") as lab_file:
                response = requests.post(
                    f"{SERVER_URL}/upload_lab", data=lab_file.read(),
                    headers={"X-Client-ID": self.user_id, "X-File-Name": path.name}, timeout=60
                )
            response.raise_for_status()
            if "succesfully received" not in response.text:
                self._error(f"No se pudo cargar: {response.text.strip()}")
                return
            self.upload_path_label.setText(path.name)
            self.status.setText(f"Laboratorio cargado: {path.name}. Ahora puedes asignarlo a un estudiante.")
            self.refresh_teacher_data()
        except (OSError, requests.RequestException) as exc:
            self._error(f"No se pudo cargar el ZIP: {exc}")

    def refresh_teacher_data(self):
        if self.user_role != "professor":
            return
        try:
            labs_response = requests.get(f"{SERVER_URL}/list_professors_labs",
                                         data={"id": self.user_id}, timeout=10)
            labs_response.raise_for_status()
            labs = labs_response.json()
            students_response = requests.get(f"{SERVER_URL}/list_students",
                                             data={"id": self.user_id}, timeout=10)
            students_response.raise_for_status()
            students = students_response.json()
            if not isinstance(labs, list) or not isinstance(students, list):
                raise ValueError("El servidor devolvio una lista invalida.")
            self.teacher_labs.clear()
            for lab in labs:
                item = QListWidgetItem(lab.get("lab_name", "Laboratorio"))
                item.setData(Qt.UserRole, lab)
                self.teacher_labs.addItem(item)
            self.students.clear()
            for student in students:
                label = f"{student.get('name', '')} ({student.get('id', '')})"
                item = QListWidgetItem(label)
                item.setData(Qt.UserRole, str(student.get("id", "")))
                self.students.addItem(item)
            self.status.setText(f"Docente: {len(labs)} laboratorios disponibles; {len(students)} estudiantes registrados.")
        except (requests.RequestException, ValueError) as exc:
            self._error(f"No se pudieron actualizar las listas: {exc}")

    def assign_lab(self):
        if self.user_role != "professor":
            self._error("Inicia sesion como docente para asignar laboratorios.")
            return
        labs = [item.data(Qt.UserRole) for item in self.teacher_labs.selectedItems()]
        student_ids = [item.data(Qt.UserRole) for item in self.students.selectedItems()]
        if not labs or not student_ids:
            self._error("Selecciona uno o mas laboratorios y uno o mas estudiantes.")
            return
        successes, failures = [], []
        self.assign_button.setEnabled(False)
        try:
            for student_id in student_ids:
                for lab in labs:
                    lab_name = lab.get("lab_name", "")
                    try:
                        response = requests.post(f"{SERVER_URL}/assign_lab", data={
                            "id": self.user_id, "lab_name": lab_name, "student_id": student_id
                        }, timeout=10)
                        response.raise_for_status()
                        if "succesfully assigned" in response.text.lower():
                            successes.append(f"{lab_name} -> {student_id}")
                        else:
                            failures.append(f"{lab_name} -> {student_id}: {response.text.strip()}")
                    except requests.RequestException as exc:
                        failures.append(f"{lab_name} -> {student_id}: {exc}")
            summary = f"Asignaciones completadas: {len(successes)} de {len(labs) * len(student_ids)}."
            if failures:
                summary += " Fallidas: " + " | ".join(failures)
            self.status.setText(summary)
        finally:
            self.assign_button.setEnabled(True)

    def refresh_student_labs(self):
        if self.user_role != "student":
            return
        try:
            response = requests.get(f"{SERVER_URL}/list_student_labs",
                                    data={"id": self.user_id}, timeout=10)
            response.raise_for_status()
            labs = response.json()
            if not isinstance(labs, list):
                raise ValueError("El servidor devolvio una lista invalida.")
            self.student_labs.clear()
            for lab in labs:
                self.student_labs.addItem(lab.get("lab_name", "Practica"), lab)
            self.download_button.setEnabled(bool(labs))
            self.status.setText(f"Tienes {len(labs)} laboratorios asignados.")
        except (requests.RequestException, ValueError) as exc:
            self._error(f"No se pudieron cargar tus laboratorios: {exc}")

    def download_lab(self):
        lab = self.student_labs.currentData()
        if not lab:
            self._error("No tienes un laboratorio seleccionado.")
            return
        filename = lab.get("file_name", "")
        lab_name = lab.get("lab_name", "")
        try:
            response = requests.get(f"{SERVER_URL}/download_lab", headers={
                "X-Client-ID": self.user_id, "X-File-Name": filename
            }, timeout=60)
            response.raise_for_status()
            CLIENT_LABS_DIR.mkdir(parents=True, exist_ok=True)
            zip_path = CLIENT_LABS_DIR / Path(filename).name
            zip_path.write_bytes(response.content)
            with zipfile.ZipFile(zip_path) as archive:
                cir_name = f"{lab_name}.cir"
                if cir_name not in archive.namelist():
                    raise ValueError(f"El ZIP no contiene {cir_name}.")
                self.netlist = archive.read(cir_name).decode("utf-8")
                png_name = f"{lab_name}.png"
                if png_name in archive.namelist():
                    self.svg_template = ""
                    self.diagram.set_png(archive.read(png_name), lab_name)
                else:
                    # Unify legacy SVG and no-image ZIPs: build them in the
                    # same connected-circuit style as the colleague's model.
                    self.svg_template = generate_schematic_svg(lab_name, self.netlist)
                    self.diagram.set_svg(self.svg_template)
            self.selected_lab = lab
            self.node_series = {}
            self.transient_times = []
            self.plot.set_data([], {})
            self.node_table.setRowCount(0)
            self.simulate_button.setEnabled(True)
            self.play_button.setEnabled(False)
            self.time_slider.setEnabled(False)
            self.status.setText(f"{lab_name} descargado. Puedes iniciar la simulacion transitoria.")
            self._update_schematic({})
        except (requests.RequestException, OSError, zipfile.BadZipFile, KeyError, UnicodeDecodeError, ValueError) as exc:
            self._error(f"No se pudo descargar o abrir el laboratorio: {exc}")

    def simulate_transient(self):
        if not self.netlist or not self.selected_lab:
            self._error("Primero descarga un laboratorio.")
            return
        if self.simulation_worker is not None and self.simulation_worker.isRunning():
            return
        self.timer.stop()
        self.simulate_button.setEnabled(False)
        self.logout_button.setEnabled(False)
        self.status.setText("Simulando en segundo plano; la ventana seguira respondiendo...")
        self.simulation_worker = TransientSimulationWorker(
            self.netlist, self.duration.value(), self
        )
        self.simulation_worker.completed.connect(self._transient_completed)
        self.simulation_worker.failed.connect(self._transient_failed)
        self.simulation_worker.finished.connect(self._simulation_worker_finished)
        self.simulation_worker.start()

    def _transient_completed(self, times, series):
        self.transient_times = times
        self.node_series = series
        self.color_scale = max(1.0, max(abs(value) for values in series.values() for value in values))
        self.plot.set_data(times, series)
        self.time_slider.setRange(0, len(times) - 1)
        self.time_slider.setValue(0)
        self.time_slider.setEnabled(True)
        self.play_button.setEnabled(len(times) > 1)
        self.simulate_button.setEnabled(True)
        self.logout_button.setEnabled(bool(self.user_id))
        self.update_voltage_frame(0)
        varying = any(max(values) - min(values) > 1e-8 for values in series.values())
        if varying:
            self.status.setText("Transitoria lista. Reproduce o mueve el control de tiempo; pasa el cursor por un nodo para ver su voltaje.")
        else:
            self.status.setText("Transitoria lista, pero los voltajes son constantes. Para ver cambios usa una fuente PULSE o SIN en el archivo .cir.")

    def _transient_failed(self, message):
        self.simulate_button.setEnabled(True)
        self.logout_button.setEnabled(bool(self.user_id))
        self._error(f"La simulacion transitoria fallo: {message}")

    def _simulation_worker_finished(self):
        worker = self.sender()
        if self.simulation_worker is worker:
            self.simulation_worker = None
        if worker is not None:
            worker.deleteLater()

    def update_voltage_frame(self, index):
        if not self.transient_times or not self.node_series:
            return
        index = max(0, min(index, len(self.transient_times) - 1))
        time_ms = self.transient_times[index] * 1000.0
        self.time_label.setText(f"t = {time_ms:.4g} ms")
        self.plot.set_current_index(index)
        names = list(self.node_series)
        if self.node_table.rowCount() != len(names):
            self.node_table.setRowCount(len(names))
            for row, name in enumerate(names):
                self.node_table.setItem(row, 0, QTableWidgetItem(name))
                self.node_table.setItem(row, 1, QTableWidgetItem())
        current = {}
        for row, (name, values) in enumerate(self.node_series.items()):
            value = values[min(index, len(values) - 1)]
            color = self._voltage_color(value)
            current[name.casefold()] = value
            node_item = self.node_table.item(row, 0)
            value_item = self.node_table.item(row, 1)
            value_item.setText(f"{value:.6g} V")
            node_item.setBackground(color)
            value_item.setBackground(color)
            text_color = QColor("#111827") if color.lightness() > 145 else QColor("white")
            node_item.setForeground(text_color)
            value_item.setForeground(text_color)
            self.node_table.setItem(row, 0, node_item)
            self.node_table.setItem(row, 1, value_item)
        self._update_schematic(current)

    def _voltage_color(self, voltage):
        normalized = max(-1.0, min(1.0, voltage / self.color_scale))
        hue = int(round(120 - normalized * 120))
        return QColor.fromHsv(hue, 210, 245)

    def _update_schematic(self, current):
        self.diagram.set_node_state(current, self._voltage_color)

    def toggle_animation(self):
        if self.timer.isActive():
            self.timer.stop()
            self.play_button.setText("Reproducir cambios")
        else:
            if self.time_slider.value() >= self.time_slider.maximum():
                self.time_slider.setValue(0)
            self.play_button.setText("Pausar")
            self.timer.start()

    def _advance_animation(self):
        current = self.time_slider.value()
        if current >= self.time_slider.maximum():
            self.timer.stop()
            self.play_button.setText("Reproducir cambios")
            return
        increment = max(1, self.time_slider.maximum() // 150)
        self.time_slider.setValue(min(self.time_slider.maximum(), current + increment))

    def close_session(self):
        if not self.user_id:
            return
        if self.simulation_worker is not None and self.simulation_worker.isRunning():
            self._error("Espera a que termine la simulacion antes de cerrar la sesion.")
            return
        self.timer.stop()
        try:
            response = requests.post(f"{SERVER_URL}/logout", data={"id": self.user_id}, timeout=10)
            response.raise_for_status()
            if "succesfully closed" not in response.text:
                self._error(f"No se pudo cerrar sesion: {response.text.strip()}")
                return
            self.user_id = ""
            self.user_role = ""
            self.selected_lab = None
            self.netlist = ""
            self.svg_template = ""
            self.diagram.set_svg("")
            self.node_series = {}
            self.transient_times = []
            self.logout_button.setEnabled(False)
            self.simulate_button.setEnabled(False)
            self.download_button.setEnabled(False)
            self.play_button.setEnabled(False)
            self.time_slider.setEnabled(False)
            self.student_labs.clear()
            self.teacher_labs.clear()
            self.students.clear()
            self.node_table.setRowCount(0)
            self.plot.set_data([], {})
            self._update_schematic({})
            self.hide()
            self.session_closed.emit()
        except requests.RequestException as exc:
            self._error(f"No se pudo comunicar con el servidor: {exc}")

    def closeEvent(self, event):
        if self.simulation_worker is not None and self.simulation_worker.isRunning():
            self._error("Espera a que termine la simulacion antes de cerrar la ventana.")
            event.ignore()
            return
        if self.user_id:
            try:
                requests.post(f"{SERVER_URL}/logout", data={"id": self.user_id}, timeout=5)
            except requests.RequestException:
                pass
            self.user_id = ""
        event.accept()

    def _error(self, message):
        self.status.setText(message)
        QMessageBox.warning(self, "Laboratorio virtual", message)


class ApplicationController:
    def __init__(self):
        self.login_dialog = LoginDialog()
        self.window = None
        self.login_dialog.authenticated.connect(self.open_workspace)
        self.login_dialog.show()

    def open_workspace(self, user_id, role, name):
        self.login_dialog.hide()
        self.window = VirtualLabWindow(user_id, role, name)
        self.window.session_closed.connect(self.return_to_login)
        self.window.setAttribute(Qt.WA_DeleteOnClose, True)
        self.window.show()

    def return_to_login(self):
        if self.window is not None:
            self.window.deleteLater()
            self.window = None
        self.login_dialog.reset()
        self.login_dialog.show()
        self.login_dialog.activateWindow()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Laboratorio virtual de circuitos")
    controller = ApplicationController()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
