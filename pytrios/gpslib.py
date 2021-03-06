"""
Multithreaded GPS library
Terry C provided this
"""
import datetime
import logging
import re
import threading
import time

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.WARNING)
logger = logging.getLogger(__name__)


class GPSParser(object):
    """
    Class which contains a parse and checksum method.
    Will parse GPGGA, GPRMC, GPVTG, and HCHDG NMEA sentences
    """
    @staticmethod
    def checksum(sentence):
        """
        Check and validate GPS NMEA sentence

        :param sentence: NMEA sentence
        :type sentence: str

        :return: True if checksum is valid, False otherwise
        :rtype: bool
        """
        sentence = sentence.strip()
        match = re.search(r'^\$(.*\*.*)$', sentence)
        if match:
            sentence = match.group(1)
            nmeadata, cksum = re.split(r'\*', sentence)
            calc_cksum = 0
            for char in nmeadata:
                calc_cksum ^= ord(char)
            return '0x'+cksum.lower() == hex(calc_cksum)
        return False

    @staticmethod
    def parse(gps_string):
        """
        Parse a GPS NMEA sentence, Returns NMEA dictionary or None

        :param gps_string: NMEA sentence.
        :type gps_string: str

        :return: Function output or None
        """
        if GPSParser.checksum(gps_string):
            try:
                if gps_string.startswith('$GPGSA'):
                    return GPSParser.parse_gpgsa(gps_string)
                if gps_string.startswith('$GPGGA'):
                    return GPSParser.parse_gpgga(gps_string)
                elif gps_string.startswith('$GPRMC'):
                    return GPSParser.parse_gprmc(gps_string)
                elif gps_string.startswith('$GPVTG'):
                    return GPSParser.parse_gpvtg(gps_string)
                elif gps_string.startswith('$HCHDG'):
                    return GPSParser.parse_hchdg(gps_string)
            except ValueError:
                pass
        return None

    @staticmethod
    def parse_gpgsa(gpgsa_string):
        """
        Parses a GPGSA sentence. Satellite Status (fix info)

        :param gpgsa_string: NMEA Sentence
        :type gpgsa_string: str

        :return: Returns dictionary with data extracted from the string
        :rtype: dict
        """
        gps_parts = gpgsa_string.split(',')[1:-1]
        #  $GPGSA,A,3,04,05,,09,12,,,24,,,,,2.5,1.3,2.1*39
        #           3 3D fix - values include: 1 = no fix
        #                                      2 = 2D fix
        #                                      3 = 3D fix

        result = {
            'type': 'gpgsa',
            'fix_quality': int(gps_parts[1])
        }

        return result

    @staticmethod
    def parse_gpgga(gpgga_string):
        """
        Parses a GPGGA sentence. Essential fix info.

        :param gpgga_string: NMEA Sentence
        :type gpgga_string: str

        :return: Returns dictionary with data extracted from the string
        :rtype: dict
        """
        gps_parts = gpgga_string.split(',')[1:-1]

        lat = int(gps_parts[1][0:2]) + (float(gps_parts[1][2:])/60.0)
        lon = int(gps_parts[3][0:3]) + (float(gps_parts[3][3:])/60.0)

        if gps_parts[2] == 'S':
            lat *= -1
        if gps_parts[4] == 'W':
            lon *= -1

        hour = int(gps_parts[0][0:2])
        mins = int(gps_parts[0][2:4])
        seconds = int(round(float(gps_parts[0][4:]), ndigits=0))

        date = datetime.datetime.now()
        date.replace(hour=hour, minute=mins, second=seconds)

        result = {
            'type': 'gpgga',
            'hour': hour,
            'min': mins,
            'seconds': seconds,
            'date': date,
            'lat': lat,
            'lon': lon,
            'alt': float(gps_parts[8]),
            'fix_type': int(gps_parts[5])
        }

        return result

    @staticmethod
    def parse_gprmc(gprmc_string):
        """
        Parses a GPRMC sentence.

        :param gprmc_string: NMEA Sentence
        :type gprmc_string: str

        :return: Returns a dictionary with data extracted from the string.
        :rtype: dict
        """
        gps_parts = gprmc_string.split(',')[1:-1]
        # $GPRMC,113623.12,A,5021.9979,N,00407.9635,W,0.0,358.1,310315,2.2,W,A*3A
        #        0         1 2         3 4          5 6   7     8      9   10
        hour = int(gps_parts[0][0:2])
        mins = int(gps_parts[0][2:4])
        seconds = int(round(float(gps_parts[0][4:]), ndigits=0))

        day = int(gps_parts[8][0:2])
        month = int(gps_parts[8][2:4])
        year = int(gps_parts[8][4:6])
        if year < 1900:
            year += 2000

        date = datetime.datetime(year, month, day, hour, mins, seconds)

        lat = int(gps_parts[2][0:2]) + (float(gps_parts[2][2:])/60.0)
        lon = int(gps_parts[4][0:3]) + (float(gps_parts[4][3:])/60.0)
        if gps_parts[3] == 'S':
            lat *= -1
        if gps_parts[5] == 'W':
            lon *= -1

        result = {
            'type': 'gprmc',
            'hour': hour,
            'min': mins,
            'seconds': seconds,
            'day': day,
            'month': month,
            'year': year,
            'date': date,
            'lat': lat,
            'lon': lon,
            'speed': float(gps_parts[6]),
            'heading': float(gps_parts[7])
        }

        return result

    @staticmethod
    def parse_gpvtg(gpvtg_string):
        """
        Parses a GPVTG sentence.

        :param gpvtg_string: NMEA Sentence
        :type gpvtg_string: str

        :return: Returns a dictionary with data extracted from the string.
        :rtype: dict
        """
        gps_parts = gpvtg_string.split(',')[1:-1]
        # $GPVTG,232.7,T,234.9,M,1.3,N,2.4,K,A*2F
        #        0     1 2     3 4   5 6   7

        result = {
            'type': 'gpvtg',
            'heading': float(gps_parts[0]),
            'speed': float(gps_parts[4])
        }

        return result

    @staticmethod
    def parse_hchdg(hchdg_string):
        """
        Parses a HCHDG sentence.

        :param hchdg_string: NMEA Sentence
        :type hchdg_string: str

        :return: Returns a dictionary with data extracted from the string.
        :rtype: dict
        """
        gps_parts = hchdg_string.split(',')[1:-1]
        # $HCHDG,359.6,0.0,E,2.2,W*59
        #        0     1   2 3

        result = {
            'type': 'hchdg',
            'heading': float(gps_parts[0])
        }

        return result


class GPSSerialReader(threading.Thread):
    """
    Thread to read from a serial port
    """
    def __init__(self, serial_port, parent):
        threading.Thread.__init__(self)
        self.serial_port = serial_port
        self.parent = parent

        self.observers = []

        self.current_gps_dict = None
        logger.info("Starting GPS reader thread")

    def run(self):
        """
        Main loop of the thread.

        This will run and read from a GPS string and when it is valid
        and decoded it'll be passed via the observer design pattern.
        """
        while not self.parent.stop_gps:
            gps_string = self.serial_port.readline()

            logger.info("NMEA: {0}".format(gps_string.strip()))

            self.current_gps_dict = GPSParser.parse(gps_string)
            self.notify_observers()

            time.sleep(0.08)  # Sleep for a millisecond to spare CPU

    def register_observer(self, observer):
        """
        Register an observer of the GPS thread.

        Observers must implement a method called "update"
        :param observer: An observer object.
        :type observer: object
        """
        if observer not in self.observers:
            self.observers.append(observer)

    def notify_observers(self):
        """
        This pushes the GPS dict to all observers.
        """
        if self.current_gps_dict is not None:
            for observer in self.observers:
                observer.update(self.current_gps_dict)


class WatchdogTimer(object):
    """
    Simple Watchdog timer.

    Timer to call callback function after timer runs out.
    """
    def __init__(self, callback, timeout=5):
        self.timeout = timeout
        self.callback = callback
        self.timer = threading.Timer(self.timeout, self.timer_callback)
        self.timer.start()

    def timer_callback(self):
        """
        Calls the passed in callback function and resets the timer
        """
        self.callback()
        self.reset()

    def reset(self):
        """
        Stops the timer and starts it again.
        """
        self.timer.cancel()
        self.timer = threading.Timer(self.timeout, self.timer_callback)
        self.timer.start()

    def stop(self):
        """
        Stops the timer.
        """
        self.timer.cancel()


class GPSManager(object):
    """
    Main GPS class which oversees the management and reading of GPS ports.
    """
    def __init__(self):
        self.serial_ports = []
        self.stop_gps = False

        self.watchdog = None

        self.started = False
        self.threads = []

        self.heading = None
        self.lat = None
        self.lon = None
        self.alt = None
        self.speed = None
        self.fix_type = 0
        self.fix_quality = 0
        self.datetime = None
        self.old = False
        self.proper_compass = False
        self.gps_lock = threading.Lock()
        self.gps_observers = []
        self.watchdog_callbacks = []

    def __del__(self):
        self.disable_watchdog()
        self.stop()

    def add_serial_port(self, serial_port):
        """
        Add a serial port to the list of ports to read from.

        The serial port must be an instance of serial.Serial,
        and the open() method must have been called.

        :param serial_port: Serial object
        :type serial_port: serial.Serial
        """
        if serial_port not in self.serial_ports:
            self.serial_ports.append(serial_port)

    def remove_serial_port(self, serial_port):
        """
        Remove serial port from the list of ports to remove.

        This wont kill any threads reading serial ports.
        Run stop then remove then start again.
        :param serial_port: Serial object
        :type serial_port: serial.Serial
        """
        if serial_port in self.serial_ports:
            self.serial_ports.remove(serial_port)

    def start(self):
        """
        Starts serial reading threads.
        """
        if not self.started:
            self.started = True
            for port in self.serial_ports:
                new_thread = GPSSerialReader(port, self)
                new_thread.register_observer(self)
                self.threads.append(new_thread)

            for thread in self.threads:
                thread.start()

            logger.info("Started GPS manager")
        else:
            logger.warn("GPS manager already started")

    def stop(self):
        """
        Tells the serial threads to stop.
        """
        self.stop_gps = True
        time.sleep(1)

        for thread in self.threads:
            thread.join(1)
        self.threads = []
        self.started = False

        logger.info("Stopping GPS manager")

    def enable_watchdog(self, interval):
        """
        Start watchdog timer to callback when gps data > interval secs old.

        :param inteval: Number of seconds before GPS data is old.
        :type inteval: int
        """
        self.watchdog = WatchdogTimer(self.watchdog_callback, interval)
        logger.debug("Starting watchdog timer")

    def disable_watchdog(self):
        """
        Stop watchdog timer.
        """
        self.watchdog.stop()
        self.watchdog = None
        logger.debug("Stopped watchdog timer")

    def watchdog_callback(self):
        """
        Sets the watchdog field of old to True
        """
        self.old = True
        for wdg in self.watchdog_callbacks:
            wdg()

    def update(self, gps_dict):
        """
        Updates the gps info held by this class,
        a lock is used to prevent corruption.

        :param gps_dict: GPS Dictionary passed.
        :type gps_dict: dict
        """
        self.gps_lock.acquire(True)
        if gps_dict is not None:
            self.old = False
            if self.watchdog is not None:
                self.watchdog.reset()
            if gps_dict['type'] == 'gpgsa':
                self.fix_quality = gps_dict['fix_quality']
            elif gps_dict['type'] == 'hchdg':
                self.proper_compass = True
                self.heading = gps_dict['heading']
            elif gps_dict['type'] == 'gpvtg':
                # Use track made good? for heading if no proper compass
                self.speed = gps_dict['speed']

                if not self.proper_compass:
                    self.heading = gps_dict['heading']
            elif gps_dict['type'] == 'gpgga':
                self.lat = gps_dict['lat']
                self.lon = gps_dict['lon']
                self.alt = gps_dict['alt']
                self.fix_type = gps_dict['fix_type']
                if self.datetime is not None:
                    # Update if we have date (GPRMC should set that eventually)
                    self.datetime.replace(hour=gps_dict['hour'],
                                          minute=gps_dict['min'],
                                          second=gps_dict['seconds'])
                else:
                    self.datetime = gps_dict['date']
            elif gps_dict['type'] == 'gprmc':
                self.lat = gps_dict['lat']
                self.lon = gps_dict['lon']
                self.datetime = gps_dict['date']
                self.speed = gps_dict['speed']
                # Use track made good? for heading if no proper compass
                if not self.proper_compass:
                    self.heading = gps_dict['heading']
            self.notify_observers()
        self.gps_lock.release()

    def register_observer(self, gps_object):
        """
        Add object to the observing list

        :param gps_object: Observing object
        :type gps_object: object
        """
        if gps_object not in self.gps_observers:
            self.gps_observers.append(gps_object)

    def remove_observer(self, gps_object):
        """
        Remove the given observer from the list of observers

        :param gps_object: Observing object
        :type gps_object: object
        """
        self.gps_observers.remove(gps_object)

    def notify_observers(self):
        """
        Notify all observers that there is new GPS data.
        """

        logger.debug("Update observers")
        for gps_object in self.gps_observers:
            gps_object.update()

    def register_watchdog_callback(self, wdg_callback):
        """
        Register a callback function with the watchdog

        :param wdg_callback: Callback function
        :type wdg_callback: function
        """
        if wdg_callback not in self.watchdog_callbacks:
            self.watchdog_callbacks.append(wdg_callback)

    def remove_watchdog_callback(self, wdg_callback):
        """
        Stop the watchdog timer running the given callback
        :param wdg_callback: Callback function
        :type wdg_callback: function
        """
        self.watchdog_callbacks.remove(wdg_callback)
