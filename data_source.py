"""Unified data sources for simulator and serial acquisition modes.

Both sources expose the same small interface: ``open()``, ``read()`` and
``close()``.  The GUI therefore does not need to know how the raw line was
produced; it can keep using the same parser, recorder and chart pipeline.
"""

from dataclasses import dataclass

from simulator import create_data


try:
    import serial
    from serial.tools import list_ports
except ImportError:  # The simulator must still work without pyserial.
    serial = None
    list_ports = None


SIMULATOR_MODE = "simulator"
SERIAL_MODE = "serial"
DEFAULT_BAUDRATE = 115200
DEFAULT_TIMEOUT = 0.08


class DataSourceError(RuntimeError):
    """A user-facing acquisition error that the GUI can display safely."""


@dataclass(frozen=True)
class SerialPortInfo:
    device: str
    description: str

    @property
    def display_name(self):
        if self.description and self.description != "n/a":
            return f"{self.device} · {self.description}"
        return self.device


def is_pyserial_available():
    return serial is not None and list_ports is not None


def list_serial_devices():
    """Return detected COM ports without failing when pyserial is absent."""

    if not is_pyserial_available():
        return []

    try:
        ports = list_ports.comports()
    except Exception as error:
        raise DataSourceError(f"读取串口列表失败：{error}") from error

    return [
        SerialPortInfo(port.device, port.description or "")
        for port in sorted(ports, key=lambda item: item.device)
    ]


class SimulatorSource:
    """Generate the same raw text format that the STM32 will send later."""

    mode = SIMULATOR_MODE
    display_name = "模拟数据"

    @property
    def is_open(self):
        return True

    def open(self):
        return None

    def read(self):
        return create_data()

    def close(self):
        return None


class SerialSource:
    """Read newline-terminated voltage messages from a Windows COM port."""

    mode = SERIAL_MODE

    def __init__(self, port, baudrate=DEFAULT_BAUDRATE, timeout=DEFAULT_TIMEOUT):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._connection = None

    @property
    def display_name(self):
        return f"{self.port} · {self.baudrate} baud" if self.port else "未选择串口"

    @property
    def is_open(self):
        return bool(self._connection and self._connection.is_open)

    def open(self):
        if not is_pyserial_available():
            raise DataSourceError(
                "未安装 pyserial。请运行：python -m pip install pyserial"
            )
        if not self.port:
            raise DataSourceError(
                "未发现可用串口。请连接 USB 转 TTL 后刷新串口列表。"
            )
        if self.is_open:
            return

        try:
            self._connection = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
            )
            self._connection.reset_input_buffer()
        except (serial.SerialException, OSError) as error:
            self._connection = None
            raise DataSourceError(f"无法打开 {self.port}：{error}") from error

    def read(self):
        if not self.is_open:
            raise DataSourceError("串口尚未连接，请先点击“开始采集”。")

        try:
            raw_bytes = self._connection.readline()
        except (serial.SerialException, OSError) as error:
            self.close()
            raise DataSourceError(f"串口读取失败：{error}") from error

        if not raw_bytes:
            return None

        text = raw_bytes.decode("utf-8", errors="replace").strip()
        return text or None

    def close(self):
        if self._connection is None:
            return
        try:
            if self._connection.is_open:
                self._connection.close()
        except (serial.SerialException, OSError):
            pass
        finally:
            self._connection = None


def create_source(mode, port=None, baudrate=DEFAULT_BAUDRATE):
    if mode == SIMULATOR_MODE:
        return SimulatorSource()
    if mode == SERIAL_MODE:
        return SerialSource(port=port, baudrate=baudrate)
    raise ValueError(f"未知数据源模式：{mode}")
