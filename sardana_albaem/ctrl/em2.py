'''
ALBA EM2 client
'''

import time
import logging

from sockio.sio import TCP

class Em2Error(Exception):
    pass


CHANNEL_TEMPLATE = """\
Channel {o.nb}:
  Range: {o.range}
  inverson: {o.inversion}"""

class Channel:

    def __init__(self, em, nb):
        self.em = em
        self.nb = nb

    @property
    def range(self):
        return self.em.command('CHAN{:02d}:CABO:RANGE?'.format(self.nb))

    @range.setter
    def range(self, value):
        return self.em.command('CHAN{:02d}:CABO:RANGE {}'.format(self.nb, value))

    @property
    def inversion(self):
        return self.em.command('CHAN{:02d}:CABO:INVE?'.format(self.nb)) == 'On'

    @inversion.setter
    def inversion(self, value):
        value = 'Off' if value in (0, 'off', 'OFF', 'Off') else 'On'
        return self.em.command('CHAN{:02d}:CABO:INVE {}'.format(self.nb, value))

    @property
    def current(self):
        return self.em.command('CHAN{:02d}:INSC?'.format(self.nb))

    @property
    def voltage(self):
        return eval(self.em.command('CHAN{:02d}:INSV?'.format(self.nb)))

    @property
    def voltage_buffer(self):
        return eval(self.em.command('CHAN{:02d}:VOLT?'.format(self.nb)))

    @property
    def current_buffer(self):
        return eval(self.em.command('CHAN{:02d}:CURR?'.format(self.nb)))

    def __repr__(self):
        return CHANNEL_TEMPLATE.format(o=self)


TEMPLATE = """\
{o.idn}
connection: {o.host}:{o.port}
timestamp data: {o.timestamp_data}
Acquisition:
  state: {o.acquisition_state}
  mode: {o.acquisition_mode}
  time: {o.acquisition_time}s
  nb. points: {o.nb_points}
  nb. points ready: {o.nb_points_ready}
Trigger:
  mode: {o.trigger_mode}
  input: {o.trigger_input}
  delay: {o.trigger_delay}
  polarity: {o.trigger_polarity}
  precise: {o.trigger_precision}
{channels}"""


class Em2:

    def __init__(self, host, port=5025):
        self.host = host
        self.port = port
        self._sock = TCP(host, port)
        self.log = logging.getLogger('em2.Em2({}:{})'.format(host, port))
        self.channels = [Channel(self, i) for i in range(1, 5)]

    def __getitem__(self, i):
        return self.channels[i]

    def open(self):
        self._sock.open()

    def commands(self, *cmds):
        cmds = [cmd.encode() + b'\n' for cmd in cmds]
        self.log.debug('-> %r', cmds)
        result = [line.strip().decode()
                  for line in self._sock.writelines_readlines(cmds)]
        self.log.debug('<- %r', result)
        return result

    def command(self, cmd):
        result = self.commands(cmd)[0]
        if result.startswith('ERROR:'):
            raise Em2Error(result.split(' ', 1)[-1])
        return result

    @property
    def idn(self):
        return self.command('*idn?')

    @property
    def acquisition_state(self):
        return self.command('ACQU:STAT?').split('_', 1)[1]

    @property
    def acquisition_time(self):
        return float(self.command('ACQU:TIME?')) * 1E-3

    @acquisition_time.setter
    def acquisition_time(self, t):
        return self.command('ACQU:TIME {}'.format(t*1E3))

    @property
    def nb_points(self):
        return int(self.command('ACQU:NTRIG?'))

    @nb_points.setter
    def nb_points(self, value):
        return self.command('ACQU:NTRIG {}'.format(value))

    @property
    def nb_points_ready(self):
        return int(self.command('ACQU:NDAT?'))

    @property
    def trigger_input(self):
        return self.command('TRIG:INPU?')

    @trigger_input.setter
    def trigger_input(self, value):
        return self.command('TRIG:INPU {}'.format(value))

    @property
    def trigger_mode(self):
        return self.command('TRIG:MODE?')

    @trigger_mode.setter
    def trigger_mode(self, value):
        return self.command('TRIG:MODE {}'.format(value))

    @property
    def trigger_polarity(self):
        return self.command('TRIG:POLA?')

    @trigger_polarity.setter
    def trigger_polarity(self, value):
        return self.command('TRIG:POLA {}'.format(value))

    @property
    def trigger_polarity(self):
        return self.command('TRIG:POLA?')

    @trigger_polarity.setter
    def trigger_polarity(self, value):
        return self.command('TRIG:POLA {}'.format(value))

    @property
    def trigger_precision(self):
        return self.command('TRIG:PREC?').lower() == 'true'

    @trigger_precision.setter
    def trigger_precision(self, value):
        return self.command('TRIG:PREC {}'.format('True' if value else 'False'))

    @property
    def trigger_delay(self):
        return float(self.command('TRIG:DELA?')) * 1E-3

    @trigger_delay.setter
    def trigger_delay(self, value):
        return self.command('TRIG:DELA {}'.format(value*1E3))

    def software_trigger(self):
        return self.command('TRIG:SWSE True')

    @property
    def acquisition_mode(self):
        return self.command('ACQU:MODE?')

    @acquisition_mode.setter
    def acquisition_mode(self, value):
        return self.command('ACQU:MODE {}'.format(value))

    @property
    def timestamp_data(self):
        return self.command('TMST?').lower() == 'true'

    @timestamp_data.setter
    def timestamp_data(self, value):
        return self.command('TMST {}'.format('True' if value else 'False'))

    def start_acquisition(self, soft_trigger=True):
        self.command('ACQU:START' + (' SWTRIG' if soft_trigger else ''))

    def stop_acquisition(self):
        return self.command('ACQU:STOP')

    def read(self, index, nb):
        return dict(eval(self.command('ACQU:MEAS? {},{}'.format(index, nb))))

    def read_all(self):
        nb_points = self.nb_points_ready
        return self.read(-1, nb_points)

    def __repr__(self):
        channels = '\n'.join(repr(c) for c in self.channels)
        return TEMPLATE.format(o=self, channels=channels)


def acquire(em, acq_time=None, nb_points=None, read=True):
    start = time.time()
    try:
        return _acquire(em, acq_time, nb_points, read)
    except KeyboardInterrupt:
        em.stop_acquisition()
    finally:
        logging.info('took {}'.format(time.time()-start))


def _acquire(em, acq_time=None, nb_points=None, read=True):
    if acq_time is not None:
        em.acquisition_time = acq_time
        em.nb_points = nb_points
    start = time.time()
    em.start_acquisition()
    time.sleep(max(acq_time-0.1, 0.001))
    while em.acquisition_state != 'ON':
        time.sleep(0.01)
    logging.info('acq took {}'.format(time.time()-start))
    if read:
        return em.read_all()


if __name__ == '__main__':
    fmt = "%(asctime)-15s %(levelname)-5s %(name)s: %(message)s"
    logging.basicConfig(format=fmt, level=logging.INFO)
    em = Em2('electproto38')
    em.log.setLevel(logging.DEBUG)

    print(em.acquisition_mode)
