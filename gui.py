import csv
import os
import sys
from collections import deque
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from matplotlib import rcParams
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from data_source import (
    DEFAULT_BAUDRATE,
    SERIAL_MODE,
    SIMULATOR_MODE,
    DataSourceError,
    create_source,
    is_pyserial_available,
    list_serial_devices,
)
from parse import parse_data
from recorder import CSV_FILE, save_data


BASE_DIR = Path(__file__).resolve().parent
ASSET_DIR = BASE_DIR / "assets"
FONT_FILE = ASSET_DIR / "fonts" / "NotoSansSC-VariableFont_wght.ttf"
VOLTAGE_ICON_FILE = ASSET_DIR / "voltage-wave.svg"
STATUS_DOT_FILE = ASSET_DIR / "status-dot.svg"

MAX_POINTS = 50
WARNING_THRESHOLD = 2.5
SAMPLE_INTERVAL = 500

COLORS = {
    "canvas": "#F5F5F5",
    "surface": "#FFFFFF",
    "surface_muted": "#D9D9D9",
    "text": "#1E1E1E",
    "text_secondary": "#757575",
    "brand": "#2C2C2C",
    "border": "#D9D9D9",
    "positive": "#02542D",
    "danger": "#900B09",
    "danger_dot": "#EC221F",
    "danger_bg": "#FEE9E7",
}


def set_layout_margins(layout, left, top, right, bottom):
    layout.setContentsMargins(left, top, right, bottom)


def repolish(widget):
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def add_shadow(widget, blur=14, y_offset=2, alpha=18):
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur)
    shadow.setOffset(0, y_offset)
    shadow.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(shadow)


def make_label(text, role=None, tone=None):
    label = QLabel(text)
    if role:
        label.setProperty("role", role)
    if tone:
        label.setProperty("tone", tone)
    return label


def make_svg(path, size):
    icon = QSvgWidget(str(path))
    icon.setFixedSize(size, size)
    return icon


class StatusPill(QFrame):
    def __init__(self, text, tone="positive", parent=None):
        super().__init__(parent)
        self.setObjectName("statusPill")
        self.setProperty("tone", tone)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        set_layout_margins(layout, 10, 5, 10, 5)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.dot = make_svg(STATUS_DOT_FILE, 8)
        layout.addWidget(self.dot)

        self.label = make_label(text, role="pillText", tone=tone)
        layout.addWidget(self.label)
        self.set_status(text, tone)

    def set_status(self, text, tone="positive"):
        self.setProperty("tone", tone)
        self.label.setText(text)
        self.label.setProperty("tone", tone)
        self.dot.setVisible(tone == "positive")
        repolish(self)
        repolish(self.label)


class MetricCard(QFrame):
    def __init__(self, title, value="--", tone="default", parent=None):
        super().__init__(parent)
        self.setObjectName("metricCard")
        self.setFixedHeight(128)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        set_layout_margins(layout, 24, 20, 24, 20)
        layout.setSpacing(8)
        layout.addStretch(1)
        self.title_label = make_label(title, role="metricTitle")
        self.value_label = make_label(value, role="metricValue", tone=tone)
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addStretch(1)

    def set_value(self, value, tone="default"):
        self.value_label.setText(value)
        self.value_label.setProperty("tone", tone)
        repolish(self.value_label)


class DetailRow(QWidget):
    def __init__(self, label, value, tone="default", parent=None):
        super().__init__(parent)
        self.setFixedHeight(26)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addWidget(make_label(label, role="detailLabel"))
        layout.addStretch(1)
        self.value_widget = make_label(value, role="detailValue", tone=tone)
        layout.addWidget(self.value_widget)

    def set_value(self, value, tone="default"):
        self.value_widget.setText(value)
        self.value_widget.setProperty("tone", tone)
        repolish(self.value_widget)


class PortDetailRow(QWidget):
    """Compact serial-port picker used inside the fixed-height control card."""

    def __init__(self, refresh_callback, changed_callback, parent=None):
        super().__init__(parent)
        self.setFixedHeight(26)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(make_label("串口端口", role="detailLabel"))
        layout.addStretch(1)

        self.combo = QComboBox()
        self.combo.setObjectName("portCombo")
        self.combo.setFixedSize(142, 26)
        self.combo.currentIndexChanged.connect(changed_callback)
        layout.addWidget(self.combo)

        self.refresh_button = QPushButton("刷新")
        self.refresh_button.setObjectName("refreshButton")
        self.refresh_button.setFixedSize(48, 26)
        self.refresh_button.clicked.connect(refresh_callback)
        layout.addWidget(self.refresh_button)

    def set_serial_enabled(self, enabled):
        self.combo.setEnabled(enabled)
        self.refresh_button.setEnabled(enabled)


class LegendItem(QWidget):
    def __init__(self, text, tone="default", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)
        dot = QFrame()
        dot.setObjectName("legendDot")
        dot.setProperty("tone", tone)
        dot.setFixedSize(8, 8)
        layout.addWidget(dot)
        layout.addWidget(make_label(text, role="legendText", tone=tone))


class VoltageChartPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self.setFixedHeight(416)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        add_shadow(self)

        layout = QVBoxLayout(self)
        set_layout_margins(layout, 24, 20, 24, 20)
        layout.setSpacing(16)

        header = QWidget()
        header.setFixedHeight(48)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(16)

        titles = QWidget()
        title_layout = QVBoxLayout(titles)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(1)
        title_layout.addWidget(make_label("电压实时变化曲线", role="sectionTitle"))
        title_layout.addWidget(make_label("最近 50 个采样点 · 范围 0–3.3 V", role="caption"))

        legend = QWidget()
        legend_layout = QHBoxLayout(legend)
        legend_layout.setContentsMargins(0, 0, 0, 0)
        legend_layout.setSpacing(16)
        legend_layout.addWidget(LegendItem("实时电压"))
        legend_layout.addWidget(LegendItem("2.5 V 警戒线", tone="danger"))

        header_layout.addWidget(titles)
        header_layout.addStretch(1)
        header_layout.addWidget(legend)
        layout.addWidget(header)

        self.figure = Figure(figsize=(8.68, 3.04), dpi=100)
        self.figure.patch.set_facecolor(COLORS["canvas"])
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setObjectName("chartCanvas")
        self.canvas.setFixedHeight(304)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.canvas)

        self.axis = self.figure.add_subplot(111)
        self.figure.subplots_adjust(left=0.066, right=0.977, top=0.91, bottom=0.21)
        self.axis.set_facecolor(COLORS["canvas"])
        self.axis.set_ylim(0, 3.3)
        self.axis.set_xlim(1, MAX_POINTS)
        self.axis.set_yticks([0.0, 0.8, 1.6, 2.5, 3.3])
        self.axis.set_xticks([1, 10, 20, 30, 40, 50])
        self.axis.tick_params(axis="both", colors=COLORS["text_secondary"], labelsize=8, length=0, pad=9)
        self.axis.grid(axis="y", color=COLORS["border"], linewidth=0.9)
        self.axis.grid(axis="x", visible=False)
        for side in ("top", "right", "left"):
            self.axis.spines[side].set_visible(False)
        self.axis.spines["bottom"].set_color(COLORS["text_secondary"])
        self.axis.spines["bottom"].set_linewidth(0.8)
        self.axis.set_xlabel("采样次数", color=COLORS["text_secondary"], fontsize=8, loc="right", labelpad=-1)
        self.axis.text(-0.047, 1.03, "V", transform=self.axis.transAxes, color=COLORS["text_secondary"], fontsize=8, ha="left", va="bottom")

        self.axis.axhline(WARNING_THRESHOLD, color=COLORS["danger_dot"], linestyle=(0, (4, 3)), linewidth=1.2, zorder=3)
        self.axis.text(
            0.97,
            WARNING_THRESHOLD + 0.13,
            "警戒 2.5 V",
            transform=self.axis.get_yaxis_transform(),
            color=COLORS["danger"],
            fontsize=8,
            ha="right",
            va="center",
            bbox={"boxstyle": "round,pad=0.55,rounding_size=1.2", "facecolor": COLORS["danger_bg"], "edgecolor": "none"},
            zorder=6,
        )
        self.line, = self.axis.plot(
            [], [], color=COLORS["brand"], linewidth=2.1, marker="o", markersize=4.2,
            markerfacecolor=COLORS["brand"], markeredgewidth=0, zorder=4,
        )
        self.area = None
        self.warning_points = None
        self.current_point = None
        self.current_annotation = None

    def update_series(self, sample_numbers, voltages):
        numbers = list(sample_numbers)
        values = list(voltages)
        self.line.set_data(numbers, values)
        for artist_name in ("area", "warning_points", "current_point", "current_annotation"):
            artist = getattr(self, artist_name)
            if artist is not None:
                artist.remove()
                setattr(self, artist_name, None)

        if numbers and values:
            self.area = self.axis.fill_between(numbers, values, 0, color=COLORS["surface_muted"], alpha=0.58, zorder=2)
            warning_pairs = [(x, value) for x, value in zip(numbers, values) if value >= WARNING_THRESHOLD]
            if warning_pairs:
                self.warning_points = self.axis.scatter(
                    [pair[0] for pair in warning_pairs], [pair[1] for pair in warning_pairs],
                    s=18, color=COLORS["danger_dot"], zorder=5,
                )
            last_x, last_value = numbers[-1], values[-1]
            self.current_point = self.axis.scatter(
                [last_x], [last_value], s=32, facecolor=COLORS["surface"],
                edgecolor=COLORS["brand"], linewidth=2, zorder=7,
            )
            self.current_annotation = self.axis.annotate(
                f"{last_value:.2f} V", xy=(last_x, last_value), xytext=(-18, -20),
                textcoords="offset points", ha="right", va="center", fontsize=8,
                color=COLORS["brand"],
                bbox={"boxstyle": "round,pad=0.65,rounding_size=1.3", "facecolor": COLORS["surface"], "edgecolor": COLORS["brand"], "linewidth": 0.8},
                zorder=8,
            )
            if max(numbers) <= MAX_POINTS:
                self.axis.set_xlim(1, MAX_POINTS)
                self.axis.set_xticks([1, 10, 20, 30, 40, 50])
            else:
                left, right = max(1, numbers[-1] - MAX_POINTS + 1), numbers[-1]
                self.axis.set_xlim(left, right)
                step = max(1, (right - left) // 5)
                self.axis.set_xticks(sorted(set(list(range(left, right + 1, step))[:5] + [right])))
        self.canvas.draw_idle()


class CollectionControlPanel(QFrame):
    def __init__(
        self,
        start_callback,
        stop_callback,
        refresh_ports_callback,
        port_changed_callback,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("panel")
        self.setFixedSize(408, 416)
        add_shadow(self)
        layout = QVBoxLayout(self)
        set_layout_margins(layout, 24, 20, 24, 20)
        layout.setSpacing(16)

        header = QWidget()
        header.setFixedHeight(28)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.addWidget(make_label("采集控制", role="sectionTitle"))
        header_layout.addStretch(1)
        self.status_pill = StatusPill("采集中")
        header_layout.addWidget(self.status_pill)
        layout.addWidget(header)

        divider = QFrame()
        divider.setObjectName("divider")
        divider.setFixedHeight(1)
        layout.addWidget(divider)

        details = QWidget()
        details.setFixedHeight(128)
        detail_layout = QVBoxLayout(details)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(8)
        self.source_row = DetailRow("数据模式", "模拟数据")
        self.port_row = PortDetailRow(
            refresh_ports_callback,
            port_changed_callback,
        )
        self.baudrate_row = DetailRow("波特率", f"{DEFAULT_BAUDRATE}")
        self.threshold_row = DetailRow(
            "报警阈值",
            f"≥ {WARNING_THRESHOLD:.2f} V",
            tone="danger",
        )
        for row in (
            self.source_row,
            self.port_row,
            self.baudrate_row,
            self.threshold_row,
        ):
            detail_layout.addWidget(row)
        layout.addWidget(details)

        notice = QFrame()
        notice.setObjectName("hardwareNotice")
        notice.setFixedHeight(80)
        notice_layout = QVBoxLayout(notice)
        set_layout_margins(notice_layout, 12, 10, 12, 10)
        notice_layout.setSpacing(4)
        self.notice_title = make_label("当前使用模拟数据", role="noticeTitle")
        notice_layout.addWidget(self.notice_title)
        self.notice_body = make_label(
            "无需硬件即可验证解析、曲线和 CSV 流程。",
            role="caption",
        )
        self.notice_body.setWordWrap(True)
        notice_layout.addWidget(self.notice_body)
        layout.addWidget(notice)

        actions = QWidget()
        actions.setFixedHeight(40)
        action_layout = QHBoxLayout(actions)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(12)
        self.start_button = QPushButton("开始采集")
        self.start_button.setObjectName("primaryButton")
        self.stop_button = QPushButton("停止采集")
        self.stop_button.setObjectName("neutralButton")
        for button in (self.start_button, self.stop_button):
            button.setFixedHeight(40)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.start_button.clicked.connect(start_callback)
        self.stop_button.clicked.connect(stop_callback)
        action_layout.addWidget(self.start_button)
        action_layout.addWidget(self.stop_button)
        layout.addWidget(actions)

    def set_running(self, running):
        self.start_button.setEnabled(not running)
        self.stop_button.setEnabled(running)
        self.status_pill.set_status("采集中" if running else "已停止", "positive" if running else "neutral")

    def set_mode(self, mode):
        is_serial = mode == SERIAL_MODE
        self.source_row.set_value("真实串口" if is_serial else "模拟数据")
        self.port_row.set_serial_enabled(is_serial)

    def set_notice(self, title, body, tone="default"):
        self.notice_title.setText(title)
        self.notice_title.setProperty("tone", tone)
        self.notice_body.setText(body)
        self.notice_body.setProperty("tone", tone)
        repolish(self.notice_title)
        repolish(self.notice_body)


class SampleTable(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(0, 3, parent)
        self.setObjectName("sampleTable")
        self.setHorizontalHeaderLabels(["时间", "电压", "状态"])
        for column in range(self.columnCount()):
            self.horizontalHeaderItem(column).setTextAlignment(
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            )
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setFixedHeight(28)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.horizontalHeader().setSectionsClickable(False)
        self.setShowGrid(True)
        self.setGridStyle(Qt.PenStyle.SolidLine)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFixedHeight(156)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        available = self.viewport().width()
        first = int(available * 0.278)
        second = int(available * 0.278)
        self.setColumnWidth(0, first)
        self.setColumnWidth(1, second)
        self.setColumnWidth(2, max(80, available - first - second))

    def set_records(self, records):
        self.setRowCount(len(records))
        for row_index, record in enumerate(records):
            time_text, voltage, is_warning = record
            values = [time_text, f"{voltage:.2f} V", "超过阈值" if is_warning else "正常"]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter))
                color = COLORS["text"]
                if is_warning and column > 0:
                    color = COLORS["danger"]
                elif column == 2:
                    color = COLORS["positive"]
                item.setForeground(QColor(color))
                font = item.font()
                font.setPointSize(9)
                if column == 2:
                    font.setWeight(QFont.Weight.DemiBold)
                item.setFont(font)
                self.setItem(row_index, column, item)
            self.setRowHeight(row_index, 32)


class SamplesPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self.setFixedHeight(232)
        add_shadow(self, blur=12, y_offset=2, alpha=14)
        layout = QVBoxLayout(self)
        set_layout_margins(layout, 24, 16, 24, 16)
        layout.setSpacing(12)

        header = QWidget()
        header.setFixedHeight(32)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.addWidget(make_label("最新采样记录", role="sectionTitle"))
        header_layout.addStretch(1)
        self.csv_pill = StatusPill("CSV 自动记录中")
        header_layout.addWidget(self.csv_pill)
        layout.addWidget(header)
        self.table = SampleTable()
        layout.addWidget(self.table)

    def set_running(self, running):
        self.csv_pill.set_status("CSV 自动记录中" if running else "CSV 记录已暂停", "positive" if running else "neutral")

    def set_records(self, records):
        self.table.set_records(records)


class VoltageMonitor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("STM32 电压采集与监控系统")
        self.setWindowIcon(QIcon(str(VOLTAGE_ICON_FILE)))
        self.resize(1440, 1024)
        self.setMinimumSize(1120, 760)
        self.sample_count = 0
        self.sample_numbers = deque(maxlen=MAX_POINTS)
        self.voltages = deque(maxlen=MAX_POINTS)
        self.recent_records = deque(maxlen=4)
        self.source_mode = SIMULATOR_MODE
        self.data_source = create_source(SIMULATOR_MODE)
        self.serial_ports = []
        self.create_interface()
        self.create_timer()
        self.refresh_serial_ports()
        self.apply_source_mode_ui()
        if os.environ.get("VOLTAGE_MONITOR_SNAPSHOT") == "1":
            self.load_snapshot_state()
        else:
            self.load_history()
            QTimer.singleShot(0, self.start_collection)

    def create_interface(self):
        root = QWidget()
        root.setObjectName("root")
        root.setMinimumSize(1120, 760)
        self.dashboard_root = root
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        header = QFrame()
        header.setObjectName("appHeader")
        header.setFixedHeight(96)
        header_layout = QHBoxLayout(header)
        set_layout_margins(header_layout, 48, 20, 48, 20)
        header_layout.setSpacing(24)

        brand = QWidget()
        brand_layout = QHBoxLayout(brand)
        brand_layout.setContentsMargins(0, 0, 0, 0)
        brand_layout.setSpacing(14)
        brand_mark = QFrame()
        brand_mark.setObjectName("brandMark")
        brand_mark.setFixedSize(48, 48)
        brand_mark_layout = QHBoxLayout(brand_mark)
        brand_mark_layout.setContentsMargins(10, 10, 10, 10)
        brand_mark_layout.addWidget(make_svg(VOLTAGE_ICON_FILE, 28))
        brand_layout.addWidget(brand_mark)
        title_group = QWidget()
        title_layout = QVBoxLayout(title_group)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(2)
        title_layout.addWidget(make_label("STM32 电压采集与监控系统", role="productTitle"))
        title_layout.addWidget(make_label("Python 数据采集 · 实时可视化 · CSV 记录", role="subtitle"))
        brand_layout.addWidget(title_group)
        header_layout.addWidget(brand)
        header_layout.addStretch(1)

        device_context = QWidget()
        device_layout = QHBoxLayout(device_context)
        device_layout.setContentsMargins(0, 0, 0, 0)
        device_layout.setSpacing(12)

        self.mode_combo = QComboBox()
        self.mode_combo.setObjectName("modeCombo")
        self.mode_combo.setFixedSize(112, 38)
        self.mode_combo.addItem("模拟模式", SIMULATOR_MODE)
        self.mode_combo.addItem("串口模式", SERIAL_MODE)
        device_layout.addWidget(self.mode_combo)
        device_layout.addWidget(self.make_chip("STM32F103 · USART1", "muted"))
        self.connection_chip = QFrame()
        self.connection_chip.setObjectName("connectionChip")
        self.connection_chip.setProperty("tone", "positive")
        connection_layout = QHBoxLayout(self.connection_chip)
        set_layout_margins(connection_layout, 14, 0, 14, 0)
        connection_layout.setSpacing(8)
        self.connection_dot = make_svg(STATUS_DOT_FILE, 8)
        connection_layout.addWidget(self.connection_dot)
        self.connection_label = make_label(
            "模拟通道正常",
            role="chipText",
            tone="positive",
        )
        connection_layout.addWidget(self.connection_label)
        self.connection_chip.setFixedHeight(38)
        device_layout.addWidget(self.connection_chip)
        header_layout.addWidget(device_context)
        root_layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setObjectName("contentScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        page = QWidget()
        page.setObjectName("contentPage")
        page.setMinimumWidth(1100)
        page_layout = QVBoxLayout(page)
        set_layout_margins(page_layout, 48, 32, 48, 32)
        page_layout.setSpacing(24)

        overview = QWidget()
        overview.setFixedHeight(168)
        overview_layout = QVBoxLayout(overview)
        overview_layout.setContentsMargins(0, 0, 0, 0)
        overview_layout.setSpacing(12)
        overview_header = QWidget()
        overview_header.setFixedHeight(28)
        overview_header_layout = QHBoxLayout(overview_header)
        overview_header_layout.setContentsMargins(0, 0, 0, 0)
        overview_header_layout.addWidget(make_label("实时概览", role="sectionTitle"))
        overview_header_layout.addStretch(1)
        self.last_updated_label = make_label(f"最近更新 --:--:-- · {SAMPLE_INTERVAL} ms / 次", role="caption")
        overview_header_layout.addWidget(self.last_updated_label)
        overview_layout.addWidget(overview_header)

        cards = QWidget()
        cards.setFixedHeight(128)
        cards_layout = QHBoxLayout(cards)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(16)
        self.current_card = MetricCard("当前电压", "-- V")
        self.average_card = MetricCard("平均电压", "-- V")
        self.maximum_card = MetricCard("最大电压", "-- V")
        self.status_card = MetricCard("采集状态", "未开始")
        for card in (self.current_card, self.average_card, self.maximum_card, self.status_card):
            cards_layout.addWidget(card, 1)
        overview_layout.addWidget(cards)
        page_layout.addWidget(overview)

        monitoring = QWidget()
        monitoring.setFixedHeight(416)
        monitoring_layout = QHBoxLayout(monitoring)
        monitoring_layout.setContentsMargins(0, 0, 0, 0)
        monitoring_layout.setSpacing(20)
        self.chart_panel = VoltageChartPanel()
        self.control_panel = CollectionControlPanel(
            self.start_collection,
            self.stop_collection,
            self.refresh_serial_ports,
            self.on_serial_port_changed,
        )
        monitoring_layout.addWidget(self.chart_panel, 1)
        monitoring_layout.addWidget(self.control_panel)
        page_layout.addWidget(monitoring)

        self.samples_panel = SamplesPanel()
        page_layout.addWidget(self.samples_panel)
        page_layout.addStretch(1)
        scroll.setWidget(page)
        root_layout.addWidget(scroll, 1)
        self.mode_combo.currentIndexChanged.connect(self.on_source_mode_changed)

    def make_chip(self, text, tone):
        chip = QFrame()
        chip.setObjectName("headerChip")
        chip.setProperty("tone", tone)
        chip.setFixedHeight(38)
        layout = QHBoxLayout(chip)
        set_layout_margins(layout, 14, 0, 14, 0)
        layout.addWidget(make_label(text, role="chipText", tone=tone))
        return chip

    def create_timer(self):
        self.timer = QTimer(self)
        self.timer.setInterval(SAMPLE_INTERVAL)
        self.timer.timeout.connect(self.update_data)

    def selected_serial_port(self):
        return self.control_panel.port_row.combo.currentData()

    def set_connection_status(self, text, tone="positive"):
        self.connection_chip.setProperty("tone", tone)
        self.connection_label.setText(text)
        self.connection_label.setProperty("tone", tone)
        self.connection_dot.setVisible(tone == "positive")
        repolish(self.connection_chip)
        repolish(self.connection_label)

    def refresh_serial_ports(self, _checked=False):
        """Scan COM ports and update the picker without restarting the app."""

        combo = self.control_panel.port_row.combo
        previous_port = combo.currentData()
        combo.blockSignals(True)
        combo.clear()

        try:
            self.serial_ports = list_serial_devices()
        except DataSourceError as error:
            self.serial_ports = []
            combo.addItem("读取失败", None)
            combo.blockSignals(False)
            self.show_source_error(str(error))
            return []

        if not is_pyserial_available():
            combo.addItem("未安装 pyserial", None)
        elif not self.serial_ports:
            combo.addItem("未发现串口", None)
        else:
            for port in self.serial_ports:
                combo.addItem(port.display_name, port.device)

            if previous_port:
                matching_index = combo.findData(previous_port)
                if matching_index >= 0:
                    combo.setCurrentIndex(matching_index)

        combo.blockSignals(False)
        if self.source_mode == SERIAL_MODE:
            self.configure_data_source()
            self.apply_source_mode_ui()
        return self.serial_ports

    def configure_data_source(self):
        self.data_source.close()
        self.data_source = create_source(
            self.source_mode,
            port=self.selected_serial_port(),
            baudrate=DEFAULT_BAUDRATE,
        )

    def apply_source_mode_ui(self):
        self.control_panel.set_mode(self.source_mode)
        if self.source_mode == SIMULATOR_MODE:
            combo = self.control_panel.port_row.combo
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("无需串口", None)
            combo.blockSignals(False)
            self.set_connection_status("模拟通道正常", "positive")
            self.control_panel.set_notice(
                "当前使用模拟数据",
                "无需硬件即可验证解析、曲线和 CSV 流程。",
            )
            return

        if not is_pyserial_available():
            self.set_connection_status("缺少串口库", "danger")
            self.control_panel.set_notice(
                "缺少 pyserial",
                "请运行：python -m pip install pyserial",
                "danger",
            )
        elif not self.serial_ports:
            self.set_connection_status("未发现串口", "danger")
            self.control_panel.set_notice(
                "未发现可用串口",
                "连接 USB 转 TTL 后点击“刷新”，程序不会退出。",
                "danger",
            )
        else:
            port = self.selected_serial_port()
            self.set_connection_status("等待连接", "neutral")
            self.control_panel.set_notice(
                "串口准备就绪",
                f"{port} · {DEFAULT_BAUDRATE} baud，点击开始采集。",
            )

    def on_source_mode_changed(self, _index):
        new_mode = self.mode_combo.currentData()
        if new_mode == self.source_mode:
            return

        was_running = self.timer.isActive()
        self.timer.stop()
        self.data_source.close()
        self.source_mode = new_mode
        if self.source_mode == SERIAL_MODE:
            self.refresh_serial_ports()
        else:
            self.configure_data_source()
            self.apply_source_mode_ui()
        self.set_running_visuals(False, warning=False)

        if was_running:
            self.start_collection()

    def on_serial_port_changed(self, _index):
        if self.source_mode != SERIAL_MODE:
            return
        was_running = self.timer.isActive()
        self.timer.stop()
        self.configure_data_source()
        self.apply_source_mode_ui()
        self.set_running_visuals(False, warning=False)
        if was_running and self.selected_serial_port():
            self.start_collection()

    def show_source_error(self, message):
        self.timer.stop()
        self.data_source.close()
        self.set_running_visuals(False, warning=False)
        self.status_card.set_value("连接失败", "danger")
        self.set_connection_status("连接失败", "danger")
        self.control_panel.set_notice("数据源不可用", message, "danger")

    @staticmethod
    def _is_warning(status, voltage):
        normalized = str(status).strip().upper()
        return voltage >= WARNING_THRESHOLD or normalized == "WARNING" or "警告" in str(status) or "过高" in str(status)

    def load_history(self):
        if not CSV_FILE.exists():
            self.refresh_dashboard()
            return
        loaded = []
        try:
            with CSV_FILE.open("r", encoding="utf-8", newline="") as file:
                for row in csv.DictReader(file):
                    try:
                        voltage = float(row.get("voltage", ""))
                    except (TypeError, ValueError):
                        continue
                    time_text = row.get("time", "").strip()
                    status = row.get("status", "")
                    loaded.append((time_text, voltage, self._is_warning(status, voltage)))
        except OSError:
            loaded = []
        for index, (_, voltage, _) in enumerate(loaded[-MAX_POINTS:], start=1):
            self.sample_numbers.append(index)
            self.voltages.append(voltage)
        self.sample_count = len(self.sample_numbers)
        for time_text, voltage, warning in reversed(loaded[-4:]):
            display_time = time_text.split()[-1] if time_text else "--:--:--"
            self.recent_records.append((display_time, voltage, warning))
        self.refresh_dashboard()
        if loaded:
            time_text = loaded[-1][0].split()[-1]
            self.last_updated_label.setText(f"最近更新 {time_text} · {SAMPLE_INTERVAL} ms / 次")

    def load_snapshot_state(self):
        self.sample_numbers.extend([1, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50])
        self.voltages.extend([1.15, 1.48, 1.28, 1.94, 1.65, 2.10, 1.82, 2.36, 2.02, 2.25, 2.36])
        self.sample_count = 50
        self.recent_records.extend([
            ("12:48:32", 2.36, False),
            ("12:48:31", 2.83, True),
            ("12:48:30", 2.14, False),
            ("12:48:29", 1.98, False),
        ])
        self.chart_panel.update_series(self.sample_numbers, self.voltages)
        self.samples_panel.set_records(self.recent_records)
        self.current_card.set_value("2.36 V")
        self.average_card.set_value("2.14 V")
        self.maximum_card.set_value("2.83 V", "danger")
        self.last_updated_label.setText(f"最近更新 12:48:32 · {SAMPLE_INTERVAL} ms / 次")
        self.set_running_visuals(True, warning=False)

    def start_collection(self):
        try:
            self.configure_data_source()
            self.data_source.open()
        except DataSourceError as error:
            self.show_source_error(str(error))
            return

        self.timer.start()
        self.set_running_visuals(True, warning=False)
        if self.source_mode == SERIAL_MODE:
            port = self.selected_serial_port()
            self.set_connection_status("串口已连接", "positive")
            self.control_panel.set_notice(
                "串口已连接",
                f"{port} · {DEFAULT_BAUDRATE} baud，等待 STM32 数据。",
            )
        else:
            self.set_connection_status("模拟通道正常", "positive")
            self.control_panel.set_notice(
                "当前使用模拟数据",
                "无需硬件即可验证解析、曲线和 CSV 流程。",
            )

    def stop_collection(self):
        self.timer.stop()
        self.data_source.close()
        self.set_running_visuals(False, warning=False)
        if self.source_mode == SERIAL_MODE:
            self.set_connection_status("串口已断开", "neutral")
            self.control_panel.set_notice(
                "串口采集已停止",
                "端口已安全释放，可重新选择端口或再次开始。",
            )
        else:
            self.set_connection_status("模拟通道待机", "neutral")
            self.control_panel.set_notice(
                "模拟采集已停止",
                "点击开始采集即可继续生成模拟电压。",
            )

    def set_running_visuals(self, running, warning=False):
        self.control_panel.set_running(running)
        self.samples_panel.set_running(running)
        if not running:
            self.status_card.set_value("已停止", "muted")
        elif warning:
            self.status_card.set_value("电压警告", "danger")
        else:
            self.status_card.set_value("运行正常", "positive")

    def update_data(self):
        try:
            raw_data = self.data_source.read()
        except DataSourceError as error:
            self.show_source_error(str(error))
            return

        if raw_data is None:
            if self.source_mode == SERIAL_MODE:
                self.status_card.set_value("等待数据", "muted")
                self.control_panel.set_notice(
                    "串口已连接，等待数据",
                    "STM32 应每行发送一次 VOLT=2.35 并以换行结束。",
                )
            return

        voltage = parse_data(raw_data)
        if voltage is None:
            self.status_card.set_value("解析失败", "danger")
            self.control_panel.set_notice(
                "收到无法解析的数据",
                f"原始内容：{raw_data[:36]}",
                "danger",
            )
            return
        self.sample_count += 1
        self.sample_numbers.append(self.sample_count)
        self.voltages.append(voltage)
        is_warning = voltage >= WARNING_THRESHOLD
        save_data(voltage, "WARNING" if is_warning else "NORMAL")
        current_time = datetime.now().strftime("%H:%M:%S")
        self.recent_records.appendleft((current_time, voltage, is_warning))
        self.last_updated_label.setText(f"最近更新 {current_time} · {SAMPLE_INTERVAL} ms / 次")
        self.refresh_dashboard()
        self.set_running_visuals(True, warning=is_warning)

    def refresh_dashboard(self):
        if self.voltages:
            current = self.voltages[-1]
            average = sum(self.voltages) / len(self.voltages)
            maximum = max(self.voltages)
            self.current_card.set_value(f"{current:.2f} V", "danger" if current >= WARNING_THRESHOLD else "default")
            self.average_card.set_value(f"{average:.2f} V")
            self.maximum_card.set_value(f"{maximum:.2f} V", "danger" if maximum >= WARNING_THRESHOLD else "default")
        self.chart_panel.update_series(self.sample_numbers, self.voltages)
        self.samples_panel.set_records(self.recent_records)

    def closeEvent(self, event):
        self.timer.stop()
        self.data_source.close()
        event.accept()


def load_application_font():
    if FONT_FILE.exists():
        font_id = QFontDatabase.addApplicationFont(str(FONT_FILE))
        if font_id >= 0:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                return families[0]
    return "Microsoft YaHei UI"


def build_style_sheet(font_family):
    return f"""
        * {{ font-family: \"{font_family}\"; color: {COLORS['text']}; }}
        QMainWindow, QWidget#root, QWidget#contentPage {{ background-color: {COLORS['canvas']}; }}
        QScrollArea#contentScroll, QScrollArea#contentScroll > QWidget > QWidget {{ background-color: {COLORS['canvas']}; }}
        QFrame#appHeader {{ background-color: {COLORS['surface']}; border-bottom: 1px solid {COLORS['text_secondary']}; }}
        QFrame#brandMark {{ background-color: {COLORS['brand']}; border-radius: 16px; }}
        QLabel[role="productTitle"] {{ color: {COLORS['text']}; font-size: 22px; font-weight: 700; }}
        QLabel[role="subtitle"], QLabel[role="caption"] {{ color: {COLORS['text_secondary']}; font-size: 12px; font-weight: 400; }}
        QFrame#headerChip {{ background-color: {COLORS['surface_muted']}; border: none; border-radius: 16px; }}
        QFrame#connectionChip {{ background-color: {COLORS['surface']}; border: none; border-radius: 16px; }}
        QFrame#connectionChip[tone="danger"] {{ background-color: {COLORS['danger_bg']}; }}
        QComboBox#modeCombo {{
            color: {COLORS['brand']};
            background-color: {COLORS['surface_muted']};
            border: none;
            border-radius: 16px;
            padding: 0 12px;
            font-size: 12px;
            font-weight: 600;
        }}
        QComboBox#modeCombo::drop-down {{ border: none; width: 22px; }}
        QComboBox#modeCombo QAbstractItemView {{
            color: {COLORS['text']};
            background-color: {COLORS['surface']};
            border: 1px solid {COLORS['border']};
            selection-background-color: {COLORS['surface_muted']};
            outline: none;
        }}
        QLabel[role="chipText"] {{ color: {COLORS['text_secondary']}; font-size: 12px; font-weight: 500; }}
        QLabel[role="chipText"][tone="brand"] {{ color: {COLORS['brand']}; }}
        QLabel[role="chipText"][tone="positive"] {{ color: {COLORS['positive']}; }}
        QLabel[role="sectionTitle"] {{ color: {COLORS['text']}; font-size: 18px; font-weight: 700; }}
        QFrame#metricCard, QFrame#panel {{ background-color: {COLORS['surface']}; border: 1px solid {COLORS['border']}; border-radius: 12px; }}
        QLabel[role="metricTitle"] {{ color: {COLORS['text_secondary']}; font-size: 13px; font-weight: 400; }}
        QLabel[role="metricValue"] {{ color: {COLORS['text']}; font-size: 28px; font-weight: 700; }}
        QLabel[tone="positive"] {{ color: {COLORS['positive']}; }}
        QLabel[tone="danger"] {{ color: {COLORS['danger']}; }}
        QLabel[tone="muted"], QLabel[tone="neutral"] {{ color: {COLORS['text_secondary']}; }}
        QFrame#statusPill {{ background-color: {COLORS['canvas']}; border: none; border-radius: 14px; }}
        QFrame#statusPill[tone="danger"] {{ background-color: {COLORS['danger_bg']}; }}
        QLabel[role="pillText"] {{ color: {COLORS['positive']}; font-size: 11px; font-weight: 600; }}
        QLabel[role="pillText"][tone="neutral"] {{ color: {COLORS['text_secondary']}; }}
        QLabel[role="pillText"][tone="danger"] {{ color: {COLORS['danger']}; }}
        QFrame#divider {{ background-color: {COLORS['border']}; border: none; }}
        QLabel[role="detailLabel"] {{ color: {COLORS['text_secondary']}; font-size: 12px; font-weight: 400; }}
        QLabel[role="detailValue"] {{ color: {COLORS['text']}; font-size: 12px; font-weight: 600; }}
        QComboBox#portCombo {{
            color: {COLORS['text']};
            background-color: {COLORS['surface']};
            border: 1px solid {COLORS['border']};
            border-radius: 6px;
            padding: 0 6px;
            font-size: 10px;
        }}
        QComboBox#portCombo:disabled {{
            color: #A0A0A0;
            background-color: #EFEFEF;
        }}
        QComboBox#portCombo::drop-down {{ border: none; width: 18px; }}
        QComboBox#portCombo QAbstractItemView {{
            background-color: {COLORS['surface']};
            border: 1px solid {COLORS['border']};
            selection-background-color: {COLORS['surface_muted']};
        }}
        QFrame#hardwareNotice {{ background-color: {COLORS['surface_muted']}; border: none; border-radius: 8px; }}
        QLabel[role="noticeTitle"] {{ color: {COLORS['text']}; font-size: 12px; font-weight: 700; }}
        QFrame#legendDot {{ background-color: {COLORS['brand']}; border: none; border-radius: 4px; }}
        QFrame#legendDot[tone="danger"] {{ background-color: {COLORS['danger_dot']}; }}
        QLabel[role="legendText"] {{ color: {COLORS['brand']}; font-size: 11px; }}
        QLabel[role="legendText"][tone="danger"] {{ color: {COLORS['danger']}; }}
        QPushButton {{ min-height: 38px; border-radius: 8px; font-size: 13px; font-weight: 600; }}
        QPushButton#primaryButton {{ color: white; background-color: {COLORS['brand']}; border: 1px solid {COLORS['brand']}; }}
        QPushButton#primaryButton:hover {{ background-color: #444444; }}
        QPushButton#primaryButton:disabled {{ color: #A9A9A9; background-color: {COLORS['surface_muted']}; border: 1px solid #BFBFBF; }}
        QPushButton#neutralButton {{ color: {COLORS['text']}; background-color: #EAEAEA; border: 1px solid {COLORS['text_secondary']}; }}
        QPushButton#neutralButton:hover {{ background-color: #DDDDDD; }}
        QPushButton#neutralButton:disabled {{ color: #A9A9A9; background-color: #F1F1F1; border: 1px solid {COLORS['border']}; }}
        QPushButton#refreshButton {{
            min-height: 24px;
            max-height: 24px;
            color: {COLORS['text_secondary']};
            background-color: {COLORS['surface']};
            border: 1px solid {COLORS['border']};
            border-radius: 6px;
            font-size: 10px;
            font-weight: 600;
        }}
        QPushButton#refreshButton:hover {{ background-color: #EFEFEF; }}
        QPushButton#refreshButton:disabled {{ color: #A9A9A9; background-color: #EFEFEF; }}
        QPushButton:focus {{ border: 2px solid #6B6B6B; }}
        QTableWidget#sampleTable {{ background-color: {COLORS['surface']}; alternate-background-color: {COLORS['surface']}; border: 1px solid {COLORS['border']}; border-radius: 8px; gridline-color: {COLORS['border']}; font-size: 12px; outline: none; }}
        QTableWidget#sampleTable::item {{ padding-left: 12px; border: none; }}
        QHeaderView::section {{ color: {COLORS['text_secondary']}; background-color: {COLORS['surface_muted']}; border: none; border-bottom: 1px solid {COLORS['border']}; padding-left: 16px; text-align: left; font-size: 12px; font-weight: 600; }}
        QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
        QScrollBar::handle:vertical {{ background: #C5C5C5; border-radius: 4px; min-height: 32px; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    """


def create_application():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    font_family = load_application_font()
    app.setFont(QFont(font_family, 10))
    app.setStyleSheet(build_style_sheet(font_family))
    rcParams["font.sans-serif"] = [font_family, "Noto Sans CJK SC", "DejaVu Sans"]
    rcParams["axes.unicode_minus"] = False
    return app


def main():
    app = create_application()
    window = VoltageMonitor()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
