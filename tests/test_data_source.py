import unittest

import data_source
from parse import parse_data


class FakeSerialConnection:
    def __init__(self, **settings):
        self.settings = settings
        self.is_open = True
        self.buffer_reset = False

    def reset_input_buffer(self):
        self.buffer_reset = True

    def readline(self):
        return b"VOLT=2.35\r\n"

    def close(self):
        self.is_open = False


class FakeSerialModule:
    SerialException = OSError

    @staticmethod
    def Serial(**settings):
        return FakeSerialConnection(**settings)


class DataSourceTests(unittest.TestCase):
    def test_simulator_returns_parser_compatible_text(self):
        raw_data = data_source.SimulatorSource().read()
        self.assertIsNotNone(parse_data(raw_data))

    def test_serial_source_requires_a_port(self):
        source = data_source.SerialSource(None)
        with self.assertRaises(data_source.DataSourceError):
            source.open()

    def test_serial_source_reads_and_closes_a_line(self):
        original_serial = data_source.serial
        data_source.serial = FakeSerialModule
        try:
            source = data_source.SerialSource("COM_TEST")
            source.open()
            self.assertTrue(source.is_open)
            self.assertEqual(source.read(), "VOLT=2.35")
            source.close()
            self.assertFalse(source.is_open)
        finally:
            data_source.serial = original_serial


if __name__ == "__main__":
    unittest.main()
