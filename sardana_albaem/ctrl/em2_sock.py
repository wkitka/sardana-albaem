import sys
import socket
import logging
import functools
import threading


PY34 = sys.version_info >= (3, 4)

if not PY34:
    class ConnectionResetError(socket.error):
        pass


log = logging.getLogger('sockio')


def ensure_connected(f):
    assert not f.__name__.startswith('_')
    @functools.wraps(f)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            if not self.connected:
                self._open()
                return f(self, *args, **kwargs)
            else:
                try:
                    return f(self, *args, **kwargs)
                except socket.error:
                    self._open()
                    return f(self, *args, **kwargs)
    return wrapper


def ensure_closed_on_error(f):
    assert f.__name__.startswith('_')
    @functools.wraps(f)
    def wrapper(self, *args, **kwargs):
        try:
            return f(self, *args, **kwargs)
        except socket.error:
            self._close()
            raise
    return wrapper


class TCP(object):

    def __init__(self, host, port, timeout=1.0):
        self.host = host
        self.port = port
        self.conn = None
        self.timeout = timeout
        self._log = log.getChild('TCP({0}:{1})'.format(host, port))
        self._lock = threading.Lock()
        self.connection_counter = 0

    def _open(self):
        if self.conn is not None:
            raise ConnectionError('socket already open')
        self._log.debug('openning connection (#%d)...',
                        self.connection_counter + 1)
        self.conn = socket.create_connection((self.host, self.port))
        self.conn.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)
        self.conn.settimeout(self.timeout)
        self.fobj = self.conn.makefile('rwb', 0)
        self.connection_counter += 1

    def _close(self):
        if self.conn is not None:
            self.conn.close()
        self.conn = None
        self.fobj = None

    @ensure_closed_on_error
    def _readline(self):
        data = self.fobj.readline()
        if not data:
            raise ConnectionResetError('remote end disconnected')
        return data

    @ensure_closed_on_error
    def _read(self, n=-1):
        data = self.fobj.read(n)
        if not data:
            raise ConnectionResetError('remote end disconnected')
        return data

    @ensure_closed_on_error
    def _write(self, data):
        return self.fobj.write(data)

    @ensure_closed_on_error
    def _writelines(self, lines):
        return self.fobj.writelines(lines)

    # API

    def open(self):
        with self._lock:
            self._open()

    def close(self):
        with self._lock:
            self._close()

    @property
    def connected(self):
        return self.conn is not None

    @ensure_connected
    def write(self, data):
        return self._write(data)

    @ensure_connected
    def read(self, n=-1):
        return self._read(n)

    @ensure_connected
    def readline(self):
        return self._readline()

    @ensure_connected
    def writelines(self, lines):
        return self._writelines(lines)

    @ensure_connected
    def write_readline(self, data):
        self._write(data)
        return self._readline()

    @ensure_connected
    def writelines_readlines(self, lines, n=None):
        if n is None:
            n = len(lines)
        self._writelines(lines)
        return [self._readline() for i in range(n)]


def main(args=None):
    import argparse
    parser = argparse.ArgumentParser()
    log_level_choices = ["critical", "error", "warning", "info", "debug"]
    log_level_choices += [i.upper() for i in log_level_choices]
    parser.add_argument('--host', default='0',
                        help='host / IP')
    parser.add_argument('-p', '--port', type=int, help='port')
    parser.add_argument("--log-level", choices=log_level_choices,
                        default="warning")
    options = parser.parse_args(args)
    fmt = '%(asctime)-15s %(levelname)-5s %(threadName)s %(name)s: %(message)s'
    logging.basicConfig(level=options.log_level.upper(), format=fmt)
    return TCP(options.host, options.port)


if __name__ == '__main__':
    conn = main()
