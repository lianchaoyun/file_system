"""
fupan.py - 股票复盘工具 (PySide6 GUI 版)
功能：暗色窗口，选策略/日期/终端，◀▶ 切换股票，
      自动打开东方财富/通达信并输入代码，
      可展开显示股票列表
依赖：pip install PySide6 pymysql pywin32
"""

import sys
import os
import time
from pathlib import Path
from typing import List, Tuple, Optional
import tomllib  # Python 3.11+
import pymysql
from PySide6.QtCore import (
    Qt, QThread, Signal, QTimer, QRect,
)
from PySide6.QtGui import (
    QFont, QColor, QPainter, QPen, QBrush, QPaintEvent,
    QKeyEvent, QFocusEvent, QEnterEvent, QPalette,
)
from PySide6.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QFrame,
    QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView,
)

# ── 配置路径 ──────────────────────────────────────
from src.common.paths import CONFIG_TOML
CONFIG_FILE = CONFIG_TOML


# ═══════════════════════════════════════════════════════
#  配色
# ═══════════════════════════════════════════════════════
class Colors:
    WND        = QColor(18, 20, 28)       # 窗口底色
    SURFACE    = QColor(22, 24, 34)       # 面板底色
    SURFACE2   = QColor(28, 31, 42)       # 第二层面板
    ELEVATED   = QColor(34, 37, 50)       # 悬浮层
    BORDER     = QColor(44, 48, 62)       # 默认边框
    BORDER_FOC = QColor(64, 70, 90)       # 聚焦边框
    DIVIDER    = QColor(36, 39, 52)       # 分割线

    TEXT       = QColor(220, 222, 232)    # 主文字
    TEXT_MUTED = QColor(130, 136, 156)    # 次要文字
    TEXT_DIM   = QColor(90, 96, 120)      # 更淡文字

    BTN_BG     = QColor(38, 42, 56)       # 按钮背景
    BTN_HOVER  = QColor(50, 54, 70)       # 按钮悬浮
    BTN_PRESS  = QColor(28, 31, 42)       # 按钮按下
    BTN_BORDER = QColor(52, 56, 72)       # 按钮边框

    ACCENT     = QColor(0, 190, 200)      # 强调色
    ACCENT_HOV = QColor(0, 212, 224)      # 强调悬浮
    ACCENT_BG  = QColor(0, 148, 156)      # 强调背景
    ACCENT_DIM  = QColor(0, 110, 118)     # 强调暗色

    SUCCESS    = QColor(80, 200, 120)     # 成功绿
    WARNING    = QColor(240, 180, 60)     # 警告橙


# ═══════════════════════════════════════════════════════
#  下拉框通用样式
# ═══════════════════════════════════════════════════════
_COMBO_STYLE = f"""
    QComboBox {{
        color: {Colors.TEXT.name()};
        background-color: {Colors.SURFACE2.name()};
        border: 1px solid {Colors.BORDER.name()};
        border-radius: 4px;
        padding: 3px 6px;
        min-height: 22px;
        font-size: 9pt;
    }}
    QComboBox:hover {{
        border: 1px solid {Colors.BORDER_FOC.name()};
    }}
    QComboBox:focus {{
        border: 1px solid {Colors.ACCENT.name()};
    }}
    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 20px;
        border-left: 1px solid {Colors.BORDER.name()};
        border-top-right-radius: 4px;
        border-bottom-right-radius: 4px;
    }}
    QComboBox::down-arrow {{
        width: 8px;
        height: 8px;
    }}
    QComboBox QAbstractItemView {{
        color: {Colors.TEXT.name()};
        background-color: {Colors.ELEVATED.name()};
        border: 1px solid {Colors.BORDER.name()};
        border-radius: 4px;
        selection-background-color: {Colors.ACCENT_BG.name()};
        selection-color: #FFFFFF;
        outline: none;
        padding: 2px 0px;
        margin: 0px;
    }}
    QComboBox QAbstractItemView::item {{
        min-height: 24px;
        padding: 2px 8px;
    }}
    QComboBox QAbstractItemView QScrollBar:vertical {{
        background: {Colors.ELEVATED.name()};
        width: 6px;
        margin: 0;
    }}
    QComboBox QAbstractItemView QScrollBar::handle:vertical {{
        background: {Colors.BORDER.name()};
        border-radius: 3px;
        min-height: 20px;
    }}
    QComboBox QAbstractItemView QScrollBar::handle:vertical:hover {{
        background: {Colors.BORDER_FOC.name()};
    }}
    QComboBox QAbstractItemView QScrollBar::add-line:vertical,
    QComboBox QAbstractItemView QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
"""

_TABLE_STYLE = f"""
    QTableWidget {{
        color: {Colors.TEXT.name()};
        background-color: {Colors.SURFACE.name()};
        border: 1px solid {Colors.BORDER.name()};
        border-top: none;
        gridline-color: {Colors.DIVIDER.name()};
        font-size: 9pt;
    }}
    QTableWidget::item {{
        padding: 5px 6px;
        border-bottom: 1px solid {Colors.DIVIDER.name()};
    }}
    QTableWidget::item:selected {{
        background-color: {Colors.ACCENT_BG.name()};
        color: #FFFFFF;
    }}
    QTableWidget::item:hover:!selected {{
        background-color: {Colors.ELEVATED.name()};
    }}
    QHeaderView::section {{
        color: {Colors.TEXT_MUTED.name()};
        background-color: {Colors.SURFACE2.name()};
        border: none;
        border-bottom: 2px solid {Colors.BORDER.name()};
        padding: 5px 6px;
        font-weight: bold;
        font-size: 8pt;
    }}
    QScrollBar:vertical {{
        background: {Colors.SURFACE.name()};
        width: 6px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {Colors.BORDER.name()};
        border-radius: 3px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {Colors.BORDER_FOC.name()};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
"""


# ═══════════════════════════════════════════════════════
#  策略/日期 加载线程
# ═══════════════════════════════════════════════════════
class QueryThread(QThread):
    """通用数据库查询线程"""
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, config: dict, sql: str, params=None):
        super().__init__()
        self.config = config
        self.sql = sql
        self.params = params or ()

    def run(self):
        try:
            conn = pymysql.connect(
                host=self.config.get("host", "127.0.0.1"),
                port=int(self.config.get("port", 3306)),
                user=self.config.get("username", "root"),
                password=self.config.get("password", ""),
                database=self.config.get("database", "yun"),
                charset="utf8mb4",
            )
            with conn.cursor() as cursor:
                cursor.execute(self.sql, self.params)
                rows = cursor.fetchall()
            conn.close()
            self.finished.emit(rows)
        except Exception as e:
            self.error.emit(str(e))


# ═══════════════════════════════════════════════════════
#  数据库加载线程 (股票列表)
# ═══════════════════════════════════════════════════════
class LoadThread(QThread):
    """后台加载数据库，不阻塞 UI"""
    finished = Signal(list)  # list of (symbol, name)
    error = Signal(str)

    def __init__(self, config: dict, strategy_id: int = None, scan_date: str = None):
        super().__init__()
        self.config = config
        self.strategy_id = strategy_id
        self.scan_date = scan_date

    def run(self):
        try:
            conn = pymysql.connect(
                host=self.config.get("host", "127.0.0.1"),
                port=int(self.config.get("port", 3306)),
                user=self.config.get("username", "root"),
                password=self.config.get("password", ""),
                database=self.config.get("database", "yun"),
                charset="utf8mb4",
            )
            if self.scan_date:
                if self.strategy_id:
                    sql = (
                        "SELECT symbol, name "
                        "FROM stock_scan_result "
                        "WHERE strategy_id = %s AND scan_date = %s "
                        "ORDER BY symbol"
                    )
                    params = (self.strategy_id, self.scan_date)
                else:
                    sql = (
                        "SELECT symbol, name "
                        "FROM stock_scan_result "
                        "WHERE scan_date = %s "
                        "ORDER BY symbol"
                    )
                    params = (self.scan_date,)
            else:
                sql = (
                    "SELECT DISTINCT symbol, name "
                    "FROM stock_scan_result "
                    "WHERE scan_date = (SELECT MAX(scan_date) FROM stock_scan_result) "
                    "ORDER BY symbol"
                )
                params = ()

            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                result = [(row[0], row[1] or "") for row in rows]
            conn.close()
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


# ═══════════════════════════════════════════════════════
#  自定义圆角按钮
# ═══════════════════════════════════════════════════════
class RoundedButton(QPushButton):
    """暗色圆角按钮，支持 hover/press 态"""
    def __init__(self, text="", accent=False, icon_mode=False, parent=None):
        super().__init__(text, parent)
        self._hover = False
        self._press = False
        self._accent = accent
        self._icon_mode = icon_mode
        self.setFixedHeight(28)
        self.setCursor(Qt.PointingHandCursor)

    def _bg_color(self):
        if self._press:
            return Colors.BTN_PRESS
        if self._hover:
            return Colors.BTN_HOVER
        return Colors.BTN_BG

    def _border_color(self):
        if self._press:
            return Colors.ACCENT
        if self._hover:
            return Colors.BORDER_FOC
        return Colors.BTN_BORDER

    def _text_color(self):
        if self._press:
            return Colors.ACCENT_HOV
        if self._accent:
            return Colors.ACCENT
        return Colors.TEXT

    def _radius(self):
        return 5 if self._icon_mode else 4

    def enterEvent(self, event: QEnterEvent):
        self._hover = True
        self.update()

    def leaveEvent(self, event):
        self._hover = False
        self.update()

    def mousePressEvent(self, event):
        self._press = True
        self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._press = False
        self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event: QPaintEvent):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        r = self._radius()
        bg = self._bg_color()
        border = self._border_color()
        bw = 2 if (self._press or self._hover) else 1

        rect = self.rect().adjusted(0, 0, -1, -1)
        p.setPen(QPen(border, bw))
        p.setBrush(QBrush(bg))
        p.drawRoundedRect(rect, r * 2, r * 2)

        p.setPen(self._text_color())
        font = self.font()
        if self._icon_mode:
            font.setPointSize(11)
        else:
            font.setPointSize(9)
        p.setFont(font)

        tr = rect
        if self._press:
            tr.translate(1, 1)

        if self._icon_mode and not self._press:
            sr = QRect(tr)
            sr.translate(0, -1)
            p.setPen(Colors.TEXT_DIM)
            p.drawText(sr, Qt.AlignCenter, self.text())
            p.setPen(self._text_color())

        p.drawText(tr, Qt.AlignCenter, self.text())
        p.end()


# ═══════════════════════════════════════════════════════
#  股票名称面板
# ═══════════════════════════════════════════════════════
class StockPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(28)
        self.setStyleSheet(
            f"background-color: {Colors.SURFACE.name()};"
            f"border: 1px solid {Colors.BORDER.name()};"
            f"border-radius: 5px;"
        )

        self.name_label = QLabel("加载中...", self)
        font_name = QFont("Microsoft YaHei", 9)
        font_name.setBold(True)
        self.name_label.setFont(font_name)
        self.name_label.setStyleSheet(
            f"color: #FFFFFF; background: transparent;"
        )

        self.code_label = QLabel("", self)
        font_code = QFont("Consolas", 11, QFont.Bold)
        self.code_label.setFont(font_code)
        self.code_label.setStyleSheet(
            f"color: {Colors.ACCENT.name()}; background: transparent;"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(5)
        layout.addWidget(self.name_label)
        layout.addWidget(self.code_label)
        layout.addStretch()

    def set_stock(self, name: str, symbol: str):
        self.name_label.setText(name if name else symbol)
        self.code_label.setText(symbol)


# ═══════════════════════════════════════════════════════
#  主窗口
# ═══════════════════════════════════════════════════════
class FupanWindow(QWidget):
    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.stocks: List[Tuple[str, str]] = []
        self.current_index = 0
        self.load_thread: Optional[LoadThread] = None
        self._strategy_query: Optional[QueryThread] = None
        self._date_query: Optional[QueryThread] = None
        self._list_visible = False
        self._strategies: List[Tuple[int, str, str]] = []  # (id, code, name)
        self._current_strategy_id: Optional[int] = None
        self._current_scan_date: Optional[str] = None
        self._init_ui()
        self._start_load_strategies()

    # ══════════════════════════════════════════════════
    #  UI 构建
    # ══════════════════════════════════════════════════
    def _init_ui(self):
        """导航行 + 可展开筛选行（在表格上方）"""
        self.setWindowTitle("股票复盘")
        self.setFixedHeight(34)
        self.setFixedWidth(390)

        self.setStyleSheet(f"background-color: {Colors.WND.name()};")
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowStaysOnTopHint
        )

        MARGIN, GAP = 5, 3

        # ══ 导航行（始终显示） ══

        self.btn_prev = RoundedButton("\u25C0", icon_mode=True)
        self.btn_prev.setFixedWidth(26)

        self.stock_panel = StockPanel()
        self.stock_panel.setFixedWidth(142)

        self.lbl_count = QLabel("0 / 0")
        font_count = QFont("Segoe UI", 9)
        self.lbl_count.setFont(font_count)
        self.lbl_count.setStyleSheet(
            f"color: {Colors.TEXT_DIM.name()}; background: transparent;"
        )
        self.lbl_count.setFixedWidth(44)
        self.lbl_count.setAlignment(Qt.AlignCenter)

        self.btn_next = RoundedButton("\u25B6", icon_mode=True)
        self.btn_next.setFixedWidth(26)

        self.btn_list = RoundedButton("\u2630", icon_mode=True)
        self.btn_list.setFixedWidth(26)

        self.nav_frame = QFrame()
        self.nav_frame.setFixedSize(390, 34)
        self.nav_frame.setStyleSheet(
            f"background-color: {Colors.WND.name()};"
            f"border-bottom: 1px solid {Colors.DIVIDER.name()};"
        )
        row_nav = QHBoxLayout(self.nav_frame)
        row_nav.setContentsMargins(MARGIN, 2, MARGIN, 0)
        row_nav.setSpacing(GAP)
        row_nav.addWidget(self.btn_prev)
        row_nav.addWidget(self.stock_panel)
        row_nav.addWidget(self.lbl_count)
        row_nav.addWidget(self.btn_next)
        row_nav.addWidget(self.btn_list)

        # ══ 筛选行（展开时显示在表格上方） ══

        self.filter_frame = QFrame()
        self.filter_frame.setStyleSheet(
            f"background-color: {Colors.SURFACE.name()};"
            f"border-bottom: 1px solid {Colors.DIVIDER.name()};"
        )

        self.combo_strategy = QComboBox()
        self.combo_strategy.setFixedWidth(98)
        self.combo_strategy.setStyleSheet(_COMBO_STYLE)

        self.combo_date = QComboBox()
        self.combo_date.setFixedWidth(94)
        self.combo_date.setStyleSheet(_COMBO_STYLE)

        self.combo_terminal = QComboBox()
        self.combo_terminal.setFixedWidth(72)
        self.combo_terminal.setStyleSheet(_COMBO_STYLE)
        self.combo_terminal.addItems(["东方财富", "通达信"])
        self.combo_terminal.setCurrentIndex(1)  # 默认通达信

        self.btn_refresh = RoundedButton("\u21BB", icon_mode=True)
        self.btn_refresh.setFixedWidth(26)

        filter_layout = QHBoxLayout(self.filter_frame)
        filter_layout.setContentsMargins(MARGIN, 4, MARGIN, 4)
        filter_layout.setSpacing(GAP)
        filter_layout.addWidget(self.combo_strategy)
        filter_layout.addWidget(self.combo_date)
        filter_layout.addWidget(self.combo_terminal)
        filter_layout.addWidget(self.btn_refresh)
        filter_layout.addStretch()

        # ══ 股票列表（默认隐藏） ══

        self.stock_table = QTableWidget(0, 3)
        self.stock_table.setHorizontalHeaderLabels(["#", "代码", "名称"])
        self.stock_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Fixed
        )
        self.stock_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Fixed
        )
        self.stock_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.Stretch
        )
        self.stock_table.setColumnWidth(0, 32)
        self.stock_table.setColumnWidth(1, 82)
        self.stock_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.stock_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.stock_table.verticalHeader().setDefaultSectionSize(26)
        self.stock_table.verticalHeader().setVisible(False)
        self.stock_table.setFocusPolicy(Qt.ClickFocus)
        self.stock_table.setStyleSheet(_TABLE_STYLE)
        self.stock_table.setShowGrid(False)

        # ══ 展开容器（筛选行 + 表格） ══

        self.expand_widget = QWidget()
        self.expand_widget.setVisible(False)
        expand_layout = QVBoxLayout(self.expand_widget)
        expand_layout.setContentsMargins(0, 0, 0, 0)
        expand_layout.setSpacing(0)
        expand_layout.addWidget(self.filter_frame)
        expand_layout.addWidget(self.stock_table)

        # ══ 总布局 ══

        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)
        vbox.addWidget(self.nav_frame)
        vbox.addWidget(self.expand_widget)
        self.setLayout(vbox)

        # ══ 信号连接 ══

        self.combo_strategy.currentIndexChanged.connect(self._on_strategy_changed)
        self.combo_date.currentIndexChanged.connect(self._on_date_changed)
        self.btn_prev.clicked.connect(self._on_prev)
        self.btn_next.clicked.connect(self._on_next)
        self.btn_refresh.clicked.connect(self._start_load)
        self.btn_list.clicked.connect(self._toggle_list)
        self.stock_table.cellClicked.connect(self._on_table_click)
        self.stock_table.cellDoubleClicked.connect(self._on_table_double_click)

        self.setFocusPolicy(Qt.StrongFocus)

    # ══════════════════════════════════════════════════
    #  加载策略列表
    # ══════════════════════════════════════════════════
    def _start_load_strategies(self):
        sql = (
            "SELECT id, code, name "
            "FROM stock_scan_strategies "
            "WHERE enabled = 1 "
            "ORDER BY id"
        )
        self._strategy_query = QueryThread(self.config, sql)
        self._strategy_query.finished.connect(self._on_strategies_loaded)
        self._strategy_query.error.connect(self._on_strategy_error)
        self._strategy_query.start()

    def _on_strategies_loaded(self, rows):
        """策略加载完成，填充下拉框（含"全部"选项）"""
        self.combo_strategy.blockSignals(True)
        self.combo_strategy.clear()
        # 插入"全部"选项
        self.combo_strategy.addItem("全部", 0)
        self._strategies = [(0, "", "全部")]
        for row in rows:
            sid, code = row[0], row[1]
            name = row[2] if row[2] else f"策略{row[0]}"
            self._strategies.append((sid, code, name))
            self.combo_strategy.addItem(f"{sid} - {name}", sid)
        self.combo_strategy.blockSignals(False)

        self.combo_strategy.setCurrentIndex(0)
        self._current_strategy_id = 0
        self._start_load_dates(0)

    def _on_strategy_error(self, err: str):
        print(f"[ERROR] 加载策略失败: {err}")
        self._start_load()  # fallback: 不加策略筛选

    # ══════════════════════════════════════════════════
    #  加载日期列表
    # ══════════════════════════════════════════════════
    def _start_load_dates(self, strategy_id: int):
        if strategy_id == 0:
            sql = (
                "SELECT DISTINCT scan_date "
                "FROM stock_scan_result "
                "ORDER BY scan_date DESC"
            )
            params = ()
        else:
            sql = (
                "SELECT DISTINCT scan_date "
                "FROM stock_scan_result "
                "WHERE strategy_id = %s "
                "ORDER BY scan_date DESC"
            )
            params = (strategy_id,)
        self._date_query = QueryThread(self.config, sql, params)
        self._date_query.finished.connect(self._on_dates_loaded)
        self._date_query.error.connect(self._on_date_error)
        self._date_query.start()

    def _on_dates_loaded(self, rows):
        """日期加载完成，填充日期下拉框"""
        self.combo_date.blockSignals(True)
        self.combo_date.clear()
        self._current_scan_date = None

        for row in rows:
            d = row[0]
            if hasattr(d, "strftime"):
                date_str = d.strftime("%Y-%m-%d")
            else:
                date_str = str(d)
            self.combo_date.addItem(date_str, date_str)

        self.combo_date.blockSignals(False)

        if self.combo_date.count() > 0:
            self.combo_date.setCurrentIndex(0)
            self._current_scan_date = self.combo_date.currentData()
            self._start_load()

    def _on_date_error(self, err: str):
        print(f"[ERROR] 加载日期失败: {err}")
        self._start_load()

    # ══════════════════════════════════════════════════
    #  信号处理
    # ══════════════════════════════════════════════════
    def _on_strategy_changed(self, index: int):
        if index < 0:
            return
        sid = self.combo_strategy.currentData()
        if sid is None:
            return
        self._current_strategy_id = int(sid)
        self._start_load_dates(self._current_strategy_id)

    def _on_date_changed(self, index: int):
        if index < 0:
            return
        self._current_scan_date = self.combo_date.currentData()
        self._start_load()

    # ══════════════════════════════════════════════════
    #  数据加载
    # ══════════════════════════════════════════════════
    def _start_load(self):
        """启动后台加载股票列表"""
        self.stock_panel.name_label.setText("加载中...")
        self.stock_panel.code_label.setText("")
        self.lbl_count.setText("... / ...")
        self.btn_refresh.setText("\u21BB")
        self.btn_refresh.setEnabled(False)

        self.load_thread = LoadThread(
            self.config,
            strategy_id=self._current_strategy_id,
            scan_date=self._current_scan_date,
        )
        self.load_thread.finished.connect(self._on_loaded)
        self.load_thread.error.connect(self._on_load_error)
        self.load_thread.start()

    def _on_loaded(self, stocks: list):
        self.stocks = stocks
        self.current_index = 0
        self.btn_refresh.setText("\u21BB")
        self.btn_refresh.setEnabled(True)
        self._update_display()
        self._rebuild_table()

    def _on_load_error(self, err: str):
        self.stock_panel.name_label.setText("加载失败")
        self.stock_panel.code_label.setText(err[:40])
        self.btn_refresh.setText("\u21BB")
        self.btn_refresh.setEnabled(True)

    # ══════════════════════════════════════════════════
    #  显示更新
    # ══════════════════════════════════════════════════
    def _update_display(self):
        if not self.stocks:
            self.stock_panel.set_stock("无数据", "")
            self.lbl_count.setText("0 / 0")
            return
        symbol, name = self.stocks[self.current_index]
        self.stock_panel.set_stock(name, symbol)
        self.lbl_count.setText(f"{self.current_index + 1} / {len(self.stocks)}")
        self._highlight_table_row()

    # ══════════════════════════════════════════════════
    #  表格操作
    # ══════════════════════════════════════════════════
    def _rebuild_table(self):
        """根据当前股票列表重建表格"""
        self.stock_table.setRowCount(len(self.stocks))
        for i, (symbol, name) in enumerate(self.stocks):
            # 序号列
            idx_item = QTableWidgetItem(str(i + 1))
            idx_item.setTextAlignment(Qt.AlignCenter)
            idx_item.setForeground(Colors.TEXT_DIM)
            self.stock_table.setItem(i, 0, idx_item)

            # 代码列
            sym_item = QTableWidgetItem(symbol)
            sym_item.setForeground(Colors.TEXT)
            self.stock_table.setItem(i, 1, sym_item)

            # 名称列
            name_item = QTableWidgetItem(name if name else "")
            self.stock_table.setItem(i, 2, name_item)

            # 斑马纹
            if i % 2 == 1:
                for col in range(3):
                    item = self.stock_table.item(i, col)
                    if item:
                        item.setBackground(Colors.SURFACE)
            else:
                for col in range(3):
                    item = self.stock_table.item(i, col)
                    if item:
                        item.setBackground(Colors.WND)

        self._highlight_table_row()

    def _highlight_table_row(self):
        """高亮当前选中的行"""
        self.stock_table.blockSignals(True)
        self.stock_table.clearSelection()
        if 0 <= self.current_index < len(self.stocks):
            self.stock_table.selectRow(self.current_index)
            self.stock_table.scrollToItem(
                self.stock_table.item(self.current_index, 0),
                QAbstractItemView.PositionAtCenter,
            )
        self.stock_table.blockSignals(False)

    def _on_table_click(self, row: int, col: int):
        """点击表格行 → 切换到该股票"""
        if row < 0 or row >= len(self.stocks):
            return
        if row != self.current_index:
            self.current_index = row
            self._update_display()
            self._open_client()

    def _on_table_double_click(self, row: int, col: int):
        """双击表格行 → 打开客户端（handle 单/双击分离）"""
        if row < 0 or row >= len(self.stocks):
            return
        if row != self.current_index:
            self.current_index = row
            self._update_display()
        self._open_client()

    def _toggle_list(self):
        """展开/收起股票列表容器（筛选行 + 表格）"""
        if self._list_visible:
            self.expand_widget.setVisible(False)
            self.setFixedHeight(34)
            self.btn_list.setText("\u2630")
            self._list_visible = False
        else:
            self.expand_widget.setVisible(True)
            self.setMinimumHeight(380)
            self.setMaximumHeight(16777215)
            self.setFixedHeight(440)
            self.btn_list.setText("\u2715")
            self._list_visible = True
            self._highlight_table_row()

    # ══════════════════════════════════════════════════
    #  导航
    # ══════════════════════════════════════════════════
    def _on_prev(self):
        if not self.stocks:
            return
        self.current_index = (self.current_index - 1) % len(self.stocks)
        self._update_display()
        self._open_client()

    def _on_next(self):
        if not self.stocks:
            return
        self.current_index = (self.current_index + 1) % len(self.stocks)
        self._update_display()
        self._open_client()

    # ══════════════════════════════════════════════════
    #  客户端调用（统一入口）
    # ══════════════════════════════════════════════════
    def _open_client(self):
        """根据终端选择分发到东方财富或通达信"""
        if not self.stocks:
            return
        terminal = self.combo_terminal.currentText()
        if terminal == "通达信":
            self._open_tdx()
        else:
            self._open_eastmoney()

    # ── 东方财富 ──────────────────────────────────
    def _open_eastmoney(self):
        """打开东方财富并输入股票代码（优先复用已有窗口）"""
        if not self.stocks:
            return
        symbol, _ = self.stocks[self.current_index]
        pure = symbol.split(".")[0] if "." in symbol else symbol

        em_path = self.config.get("eastmoney_path", "")
        if not em_path or not Path(em_path).exists():
            return

        hwnd = 0
        try:
            import win32gui

            def enum_cb(h, _):
                nonlocal hwnd
                if win32gui.IsWindowVisible(h) and "东方财富" in win32gui.GetWindowText(h):
                    hwnd = h
                    return False
                return True

            win32gui.EnumWindows(enum_cb, None)
        except Exception:
            hwnd = 0

        if hwnd:
            self._type_code_win32(pure)
        else:
            os.startfile(em_path)
            QTimer.singleShot(5000, lambda: self._type_code_win32(pure))

    def _type_code_win32(self, code: str):
        """用 win32api 向东方财富窗口输入代码"""
        if sys.platform != "win32":
            return
        try:
            import win32gui
            import win32con
            import win32api

            hwnd = 0

            def enum_cb(h, _):
                nonlocal hwnd
                if win32gui.IsWindowVisible(h) and "东方财富" in win32gui.GetWindowText(h):
                    hwnd = h
                    return False
                return True

            win32gui.EnumWindows(enum_cb, None)

            if not hwnd:
                return

            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.3)

            for char in code:
                win32api.keybd_event(ord(char), 0, 0, 0)
                win32api.keybd_event(ord(char), 0, win32con.KEYEVENTF_KEYUP, 0)
                time.sleep(0.05)

            time.sleep(0.2)
            win32api.keybd_event(win32con.VK_RETURN, 0, 0, 0)
            win32api.keybd_event(win32con.VK_RETURN, 0, win32con.KEYEVENTF_KEYUP, 0)
        except Exception:
            pass

    # ── 通达信 ────────────────────────────────────
    def _open_tdx(self):
        """通过 tqcenter 在通达信中打开当前股票"""
        if not self.stocks:
            return
        symbol, _ = self.stocks[self.current_index]
        pure = symbol.split(".")[0] if "." in symbol else symbol

        tdx_plugins = self.config.get("tdx_plugins", "")
        if not tdx_plugins:
            print("[TDX] 未配置 tdx_plugins 路径")
            return

        try:
            user_path = os.path.join(tdx_plugins, "user")
            if user_path not in sys.path:
                sys.path.insert(0, user_path)

            from tqcenter import tq
            tq.initialize(__file__)
            result = tq.exec_to_tdx(url=f"http://www.treeid/code_{pure}")
            if result.get("ErrorId") != "0":
                print(f"[TDX] 打开失败: {result.get('Msg', '未知错误')}")
        except ImportError:
            print(f"[TDX] tqcenter 未找到，请检查 tdx_plugins 路径: {tdx_plugins}")
        except Exception as e:
            print(f"[TDX] 调用异常: {e}")

    # ══════════════════════════════════════════════════
    #  键盘快捷键
    # ══════════════════════════════════════════════════
    def keyPressEvent(self, event: QKeyEvent):
        if not self.stocks:
            return super().keyPressEvent(event)

        ctrl = event.modifiers() & Qt.ControlModifier

        if event.key() == Qt.Key_Left:
            self._on_prev()
        elif event.key() == Qt.Key_Right:
            self._on_next()
        elif event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            if self.stock_table.hasFocus():
                row = self.stock_table.currentRow()
                if 0 <= row < len(self.stocks):
                    self.current_index = row
                    self._update_display()
                    self._open_client()
        elif event.key() == Qt.Key_F5:
            self._start_load()
        elif ctrl and event.key() == Qt.Key_R:
            self._start_load()
        elif ctrl and event.key() == Qt.Key_L:
            self._toggle_list()
        else:
            super().keyPressEvent(event)


# ═══════════════════════════════════════════════════════
#  配置加载
# ═══════════════════════════════════════════════════════
def load_config(path: Path) -> dict:
    """从 TOML 配置文件加载数据库 + fupan 配置"""
    cfg = {}
    if not path.exists():
        print(f"[WARN] 配置文件不存在: {path}")
        return cfg
    with open(path, "rb") as f:
        data = tomllib.load(f)

    # 从 [database0] 读取数据库配置
    db = data.get("database0", {})
    cfg["host"]     = db.get("host", "127.0.0.1")
    cfg["port"]     = db.get("port", 3306)
    cfg["username"] = db.get("user", "root")
    cfg["password"] = db.get("password", "")
    cfg["database"] = db.get("db_name", "yun")

    # 从 [fupan] 读取复盘专用配置
    fp = data.get("fupan", {})
    cfg["eastmoney_path"] = fp.get("eastmoney_path", "")
    cfg["tdx_plugins"]    = fp.get("tdx_plugins", "")
    return cfg


# ═══════════════════════════════════════════════════════
#  入口
# ═══════════════════════════════════════════════════════
def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # ── 暗色全局调色板（标题栏黑化） ──
    dark = QPalette()
    dark.setColor(QPalette.Window,          QColor(18, 20, 28))
    dark.setColor(QPalette.WindowText,      QColor(220, 222, 232))
    dark.setColor(QPalette.Base,            QColor(22, 24, 34))
    dark.setColor(QPalette.AlternateBase,   QColor(28, 31, 42))
    dark.setColor(QPalette.Text,            QColor(220, 222, 232))
    dark.setColor(QPalette.Button,          QColor(38, 42, 56))
    dark.setColor(QPalette.ButtonText,      QColor(220, 222, 232))
    dark.setColor(QPalette.Highlight,       QColor(0, 148, 156))
    dark.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    dark.setColor(QPalette.ToolTipBase,     QColor(34, 37, 50))
    dark.setColor(QPalette.ToolTipText,     QColor(220, 222, 232))
    app.setPalette(dark)

    app.setStyleSheet(f"""
        QToolTip {{
            color: {Colors.TEXT.name()};
            background-color: {Colors.ELEVATED.name()};
            border: 1px solid {Colors.BORDER.name()};
            border-radius: 4px;
            padding: 3px 8px;
            font-size: 9pt;
        }}
    """)

    config = load_config(CONFIG_FILE)
    window = FupanWindow(config)
    window.show()

    # ── Windows 暗色标题栏 ──
    if sys.platform == "win32":
        try:
            import ctypes
            hwnd = int(window.winId())
            # DWMWA_USE_IMMERSIVE_DARK_MODE = 20 (Win10 20H1+ / Win11)
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
                ctypes.byref(ctypes.c_int(1)), ctypes.sizeof(ctypes.c_int(2)),
            )
        except Exception:
            pass

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
