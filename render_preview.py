"""Render the dashboard to a PNG for visual regression checks."""

import argparse
import os
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("VOLTAGE_MONITOR_SNAPSHOT", "1")

from data_source import SERIAL_MODE  # noqa: E402
from gui import VoltageMonitor, create_application  # noqa: E402


BASE_DIR = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=BASE_DIR / "artifacts" / "implementation.png",
    )
    parser.add_argument(
        "--mode",
        choices=("simulator", "serial"),
        default="simulator",
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    app = create_application()
    window = VoltageMonitor()
    window.resize(1440, 1024)
    window.show()
    if args.mode == "serial":
        window.mode_combo.setCurrentIndex(window.mode_combo.findData(SERIAL_MODE))
    window.chart_panel.canvas.draw()
    app.processEvents()

    image = window.dashboard_root.grab()
    if not image.save(str(args.output), "PNG"):
        raise RuntimeError(f"无法保存预览图：{args.output}")

    print(args.output.resolve())
    window.close()


if __name__ == "__main__":
    main()
