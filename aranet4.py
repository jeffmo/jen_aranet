# Dirty hack to get around libaranet4's __init__.py which assumes a registered
# aranet4 package
import sys
sys.path.append("libaranet4/")

import asyncio
import client as libaranet4
import collections
import datetime
import json
import logging

def _temp_c_to_f(temp_c):
    return round((temp_c * (9/5)) + 32, 2)

class CurrentReading:
    def __init__(self, r):
        self.battery_pct = None if r.battery == -1 else r.battery / 100
        self.co2_ppm = None if r.co2 == -1 else r.co2
        self.color = None if r.status == -1 else r.status.name
        self.humidity_pct = None if r.humidity == -1 else r.humidity / 100
        self.name = None if r.name == "" else r.name
        self.pressure_hPa = None if r.pressure == -1 else r.pressure
        self.temp_c = None if r.temperature == -1 else r.temperature

        self.temp_f = None
        if self.temp_c is not None:
            self.temp_f = _temp_c_to_f(self.temp_c)

    def __str__(self):
        return json.dumps(self.get_dict())

    def get_dict(self):
        return {
            "battery_pct": self.battery_pct,
            "co2_ppm": self.co2_ppm,
            "color": self.color,
            "humidity_pct": self.humidity_pct,
            "name": self.name,
            "pressure_hPa": self.pressure_hPa,
            "temp_c": self.temp_c,
            "temp_f": self.temp_f,
        }

class HistoricalReading:
    def __init__(self, time, co2, humidity, pressure, temp):
        self.co2_ppm = co2
        self.humidity_pct = humidity
        self.pressure_hPa = pressure
        self.temp_c = temp
        self.time = time

        self.temp_f = None
        if self.temp_c is not None:
            self.temp_f = _temp_c_to_f(self.temp_c)

    def __str__(self):
        d = self.get_dict()
        d['time'] = str(d['time'])
        return json.dumps(d)

    def get_dict(self):
        return {
            "co2_ppm": self.co2_ppm,
            "humidity_pct": self.humidity_pct,
            "pressure_hPa": self.pressure_hPa,
            "temp_c": self.temp_c,
            "temp_f": self.temp_f,
            "time": self.time,
        }


class Aranet4:
    """
    Use this method to discover a nearby Aranet4 object. If multiple are
    discovered, one will be chosen effectively at random.

    Returns an Aranet4 object or None if no devices were found.
    """
    @classmethod
    async def discover(cls):
        devices = await cls.discover_multiple()
        if len(devices) == 0:
            return None
        return devices[0]

    """
    If you have multiple Aranet4 devices (uncommon), use this method to
    discover a list of them.

    Returns a list of discovered Aranet4 objects.
    """
    @classmethod
    async def discover_multiple(cls):
        devices = await libaranet4._find_nearby(
            on_detect=lambda x: x,
            duration=5,
        )
        return [Aranet4(device.address) for device in devices]

    async def fetch_current_readings(self):
        self.__verify_connected()
        return CurrentReading(await self.__client.current_readings(details=True))

    async def fetch_historical_readings(self):
        self.__verify_connected()

        last_log = await self.__client.get_seconds_since_update()
        now = datetime.datetime.now(datetime.timezone.utc)
        now = now.replace(microsecond=0)
        interval = await self.__client.get_interval()
        next_log = interval - last_log

        if next_log < 10:
            logging.debug("Waiting {next_log}s for next datapoint...")
            await asyncio.sleep(next_log)
            last_log = await self.__client.get_seconds_since_update()
            now = datetime.datetime.now(datetime.timezone.utc)
            now = now.replace(microsecond=0)

        num_records = await self.__client.get_total_readings()
        logging.debug("Fetching historical temperature values...")
        temp_vals = await self.__client.get_records(
            libaranet4.Param.TEMPERATURE,
            log_size=num_records
        )

        logging.debug("Fetching historical humidity values...")
        humidity_vals = await self.__client.get_records(
            libaranet4.Param.HUMIDITY,
            log_size=num_records
        )

        logging.debug("Fetching historical pressure values...")
        pressure_vals = await self.__client.get_records(
            libaranet4.Param.PRESSURE,
            log_size=num_records
        )

        logging.debug("Fetching historical co2 values...")
        co2_vals = await self.__client.get_records(
            libaranet4.Param.CO2,
            log_size=num_records
        )

        start = now - datetime.timedelta(
            seconds=((num_records - 1) * interval) + last_log
        )
        records = collections.OrderedDict()
        for i in range(num_records):
            time = start + datetime.timedelta(seconds=interval * i)
            records[time] = HistoricalReading(
                co2=co2_vals[i],
                humidity=humidity_vals[i],
                pressure=pressure_vals[i],
                temp=temp_vals[i],
                time=time,
            )
        return records

    def __init__(self, address):
        self.__address = address
        self.__client = None

    async def __aenter__(self):
        logging.debug(
            "Attempting to connect to device(%s)...",
            self.__address,
        )
        self.__client = libaranet4.Aranet4(self.__address)
        await self.__client.connect()
        return self

    async def __aexit__(self, _exc_cls, _exc_inst, _exception_trace):
        await self.__client.device.disconnect()
        self.__client = None

    def __verify_connected(self):
        if self.__client is None:
            raise IOError(
                "Device not connected! This Aranet4 object is designed "
                "to be used as an async context manager: \n"
                "\n"
                "   async def main():\n"
                "       aranet4 = await Aranet4.discover()\n"
                "       if aranet4 is None:\n"
                "           print(\"No devices found nearby!\")\n"
                "       \n"
                "       async with aranet4 as device:\n"
                "           print(await device.get_battery_level())\n"
            )

        if not self.__client.device.is_connected:
            raise IOError("Connection with the device was lost!")
