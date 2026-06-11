from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable
import re

import pyqtgraph as pg
from PySide6.QtCore import QEvent, QObject, QTime, Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from pkusleeper.domain import SleepGoal, SleepRecord, SleepType
from pkusleeper.reports import SleepReportBuilder
from pkusleeper.ui.base import UiController
from pkusleeper.ui.bridge import ServiceBridge
from pkusleeper.ui.dialogs import SleepConfigDialog, TimeAxisItem

NavigateCallback = Callable[[str], None]
RefreshCallback = Callable[[], None]


class ReportChartMixin:
    def _draw_7_days_charts(self, records: list[SleepRecord]) -> None:
        assert self.duration_plot is not None
        assert self.time_plot is not None
        self._reset_plots()

        today = datetime.now().date()
        date_list = [today - timedelta(days=i) for i in range(6, -1, -1)]
        x_ticks = [(i, d.strftime("%m/%d")) for i, d in enumerate(date_list)]
        record_dict = {self.bridge.record_date(r): r for r in records}

        durations: list[float] = []
        sleep_times: list[int] = []
        wake_times: list[int] = []
        x_indices: list[int] = []

        for idx, day in enumerate(date_list):
            record = record_dict.get(day)
            if record is None:
                continue
            durations.append((record.ended_at - record.started_at).total_seconds() / 3600)
            sleep_times.append(self._minutes_for_sleep_start(record.started_at))
            wake_times.append(record.ended_at.hour * 60 + record.ended_at.minute)
            x_indices.append(idx)

        self.duration_plot.getAxis("bottom").setTicks([x_ticks])
        self.time_plot.getAxis("bottom").setTicks([x_ticks])
        self.duration_plot.setXRange(-0.5, 6.5, padding=0)
        self.time_plot.setXRange(-0.5, 6.5, padding=0)

        if not x_indices:
            self.duration_plot.setYRange(0, 10)
            self.time_plot.setYRange(18 * 60, 32 * 60)
            return

        self.duration_plot.setYRange(0, max(max(durations) + 0.8, 10))
        self.duration_plot.plot(
            x_indices,
            durations,
            pen=pg.mkPen("#c2151d", width=3),
            symbol="o",
            symbolSize=8,
            symbolBrush="#c2151d",
        )

        all_time_values = sleep_times + wake_times
        self.time_plot.setYRange(min(all_time_values) - 60, max(all_time_values) + 60)
        self.time_plot.plot(
            x_indices,
            sleep_times,
            pen=pg.mkPen("#c2151d", width=2),
            symbol="x",
            symbolSize=7,
            symbolBrush="#c2151d",
        )
        self.time_plot.plot(
            x_indices,
            wake_times,
            pen=pg.mkPen("#f0a12d", width=2),
            symbol="o",
            symbolSize=7,
            symbolBrush="#f0a12d",
        )


    def _draw_30_days_charts(self, records: list[SleepRecord]) -> None:
        assert self.duration_plot is not None
        assert self.time_plot is not None
        self._reset_plots()

        today = datetime.now().date()
        date_list = [today - timedelta(days=i) for i in range(29, -1, -1)]
        x_ticks = [(i, d.strftime("%m/%d") if i % 5 == 0 else "") for i, d in enumerate(date_list)]
        record_dict = {self.bridge.record_date(r): r for r in records}

        durations = [0.0] * 30
        for idx, day in enumerate(date_list):
            record = record_dict.get(day)
            if record is not None:
                durations[idx] = (record.ended_at - record.started_at).total_seconds() / 3600

        self.duration_plot.addItem(
            pg.BarGraphItem(
                x=list(range(30)),
                height=durations,
                width=0.62,
                brush="#c2151d",
                pen=None,
            )
        )
        self.duration_plot.getAxis("bottom").setTicks([x_ticks])
        self.duration_plot.setXRange(-0.5, 29.5, padding=0)
        self.duration_plot.setYRange(0, max(max(durations) + 1, 10))

        all_ranges: list[int] = []
        for idx, day in enumerate(date_list):
            record = record_dict.get(day)
            if record is None:
                continue
            start_min = self._minutes_for_sleep_start(record.started_at)
            end_min = record.ended_at.hour * 60 + record.ended_at.minute
            if end_min < start_min:
                end_min += 1440
            duration_min = max(1, end_min - start_min)
            all_ranges.extend([start_min, end_min])
            self.time_plot.addItem(
                pg.BarGraphItem(
                    x=[idx],
                    y0=[start_min],
                    height=[duration_min],
                    width=0.72,
                    brush="#f0a12d",
                    pen=None,
                )
            )

        self.time_plot.getAxis("bottom").setTicks([x_ticks])
        self.time_plot.setXRange(-0.5, 29.5, padding=0)
        if all_ranges:
            self.time_plot.setYRange(min(all_ranges) - 60, max(all_ranges) + 60)
        else:
            self.time_plot.setYRange(18 * 60, 32 * 60)


    def _reset_plots(self) -> None:
        assert self.duration_plot is not None
        assert self.time_plot is not None
        for plot in (self.duration_plot, self.time_plot):
            plot.clear()
            item = plot.getPlotItem()
            item.clear()
            item.enableAutoRange(False)
            plot.getAxis("left").setTicks(None)
            plot.getAxis("bottom").setTicks(None)


    @staticmethod
    def _minutes_for_sleep_start(value: datetime) -> int:
        minutes = value.hour * 60 + value.minute
        return minutes + 1440 if minutes < 12 * 60 else minutes
