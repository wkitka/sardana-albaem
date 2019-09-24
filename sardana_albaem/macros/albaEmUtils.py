import time
from sardana.macroserver.macro import Macro, Type
from taurus import Device, Attribute
from taurus.core import AttrQuality
import PyTango

#TODO Change to taurus in TEP14
STATE_MOVING = PyTango.DevState.MOVING

RANGES = ['1mA', '100uA', '10uA', '1uA', '100nA', '10nA', '1nA', '100pA']
MIN_VALUE = 5
MAX_VALUE = 95
INTEGRATION_TIME = 0.3
AUTO_RANGE_TIMEOUT = 40


# class findMaxRange(Macro):
#     """
#     Macro to find the best range of the electrommeter channels for the scan.
#
#     The parameter start_pos and end_pos are the position of the motor in the
#     scan.
#     """
#     param_def = [['start_pos', Type.Float, None, 'Start position'],
#                  ['end_pos', Type.Float, None, 'End position']]
#
#     def __init__(self, *args, **kwargs):
#         super(findMaxRange, self).__init__(*args, **kwargs)
#         self.elements = {}
#
#     def prepare_mntgrp(self):
#         mnt_grp_name = self.getEnv("Meas")
#         self.debug("Preparing Meas:  %s" %mnt_grp_name)
#
#         self.meas = self.getObj(mnt_grp_name, type_class=Type.MeasurementGroup)
#         cfg = self.meas.getConfiguration()
#         cfg.prepare()
#         self.extract_conf(cfg)
#         self.meas.putIntegrationTime(INTEGRATION_TIME)
#         self.debug("Meas used to take the Range: %s" %mnt_grp_name)
#
#     def extract_conf(self, cfg):
#         self.debug("Extracting conf of Meas:")
#         self.channels = {}
#         for i in cfg.getChannelsInfoList():
#             if i.full_name.startswith('tango'):
#                 self.channels[i.full_name] = RANGES.index('100pA')
#
#     def acquire_mntgrp(self):
#         self.debug("AcquireMntGrp() entering...")
#         self.count_id = self.meas.start()
#         self.debug("AcquireMntGrp() leaving...")
#
#     def wait_mntgrp(self):
#         self.debug("WaitMntGrp() entering...")
#         self.meas.waitFinish(id=self.count_id)
#         self.debug("WaitMntGrp() leaving...")
#
#     def extract_channels(self):
#         for name in self.channels.keys():
#             dev, attr = str(name).rsplit('/', 1)
#             if dev not in self.elements:
#                 # Saving in the dictionary the taurus Device and the list
#                 # of channels to change the Range
#                 self.elements[dev] = {'tau_dev': Device(dev), 'chn': {}}
#             # Bool, is a Flag to check if the Channel has been checked the Range
#             self.elements[dev]['chn'][attr[-1]] = False
#
#     def conf_channels(self, auto_range):
#         min_value = MIN_VALUE
#         max_value = MAX_VALUE
#         if not auto_range:
#             min_value = 0
#             max_value = 0
#
#         for dev in self.elements.keys():
#             tau_dev = self.elements[dev]['tau_dev']
#             chn = self.elements[dev]['chn']
#             for i in chn:
#                 attr = 'AutoRange_ch%s'%i
#                 tau_dev.write_attribute(attr, auto_range)
#                 attr = 'AutoRangeMin_ch%s'%i
#                 tau_dev.write_attribute(attr, min_value)
#                 attr = 'AutoRangeMax_ch%s'%i
#                 tau_dev.write_attribute(attr, max_value)
#
#     def run(self, start_pos, end_pos):
#         try:
#             self.info('Starting AutoRange Calibration Process')
#             has_been_configured = False
#             mot = self.getEnv("Motor")
#             self.mot = self.getMoveable(mot)
#
#             if self.mot is None:
#                 raise Exception("Error Creating The Motor")
#             self.prepare_mntgrp()
#             self.extract_channels()
#
#             # Configure Channels for AutoRange Mode, True, to enable the
#             # AutoMode
#             self.conf_channels(True)
#             self.debug('The Channels has been Configured in AutoRange Mode')
#
#             has_been_configured = True
#             self.info('Moving the motor to Start Position')
#             self.mot.move(start_pos)
#             t = time.time()
#             self.info('AutoConfiguring Electrometers while the motor is '
#                       'going to end position:')
#             while (time.time() - t) < AUTO_RANGE_TIMEOUT:
#                 time.sleep(0.5)
#                 flag_finish = True
#                 for dev in self.elements.keys():
#                     tau_dev = self.elements[dev]['tau_dev']
#                     chn = self.elements[dev]['chn']
#                     for i, valid in chn.items():
#                         # Check if this channel has been checked previously
#                         if valid:
#                             continue
#                         attr = 'range_ch%s'%i
#                         valid = (tau_dev.read_attribute(attr).quality ==
#                                  AttrQuality.ATTR_VALID)
#                         flag_finish &= valid
#                         chn[i] = valid
#                 if flag_finish:
#                     break
#
#                 self.checkPoint()
#             else:
#                 raise RuntimeError('The AutoRange failed, you should check by '
#                                    'hand some channels')
#
#             self.debug('Starting to Move to end Position')
#             self.mot.write_attribute('position', end_pos)
#             data = []
#             self.debug('Starting to Acquire')
#             while self.mot.state() == STATE_MOVING:
#                 self.acquire_mntgrp()
#                 self.wait_mntgrp()
#                 d = self.meas.getValues()
#                 data.append(d)
#                 self.checkPoint()
#
#             # Unconfigure Channels to AutoRange Mode
#             self.conf_channels(False)
#             has_been_configured = False
#             for line in data:
#                 for attr in line.keys():
#                     if attr in self.channels:
#                         range = RANGES.index(line[attr])
#                         if self.channels[attr] > range:
#                             self.channels[attr] = range
#
#             self.debug(self.channels)
#             self.info('Configuring Electrometers Ranges')
#
#             for i in self.channels.keys():
#                 range = RANGES[self.channels[i]]
#                 d = Attribute(i)
#                 d.write(range)
#
#         except Exception, e:
#             self.error(e)
#         finally:
#             self.mot.stop()
#             while self.mot.state == STATE_MOVING:
#                 pass
#             if has_been_configured:
#                 self.conf_channels(False)


class em_range(Macro):
    """
    Macro to change the electrometer range.
    """
    param_def = [['chns',
                  [['ch', Type.CTExpChannel, None, 'electrometer chn'],
                   ['range',  Type.String, None, 'Amplifier range'],
                   {'min': 1}],
                  None, 'List of [channels,range]']]
    enabled_output = True
    def run(self, chns):
        for ch, rg in chns:
            old_range = ch.read_attribute("Range").value
            ch.write_attribute("Range", rg)
            new_range = ch.read_attribute("Range").value
            if self.enabled_output:
                self.output('%s changed range from %s to %s' % (ch, old_range,
                                                                new_range))


class em_inversion(Macro):
    """
        Macro to change the the polarity.
    """
    param_def = [['chns',
                  [['ch', Type.CTExpChannel, None, 'electrometer chn'],
                   ['enabled', Type.Boolean, None, 'Inversion enabled'],
                   {'min': 1}],
                  None, 'List of [channels, inversion]'], ]

    def run(self, chns):
        for ch, enabled in chns:
            old_state = ch.read_attribute('Inversion').value
            ch.write_attribute('Inversion', enabled)
            new_state = ch.read_attribute('Inversion').value
            self.output('%s changed inversion from %s to %s' % (ch, old_state,
                                                                new_state))


class em_autorange(Macro):
    """
        Macro to start the autorange.
    """
    param_def = [['chns',
                  [['ch', Type.CTExpChannel, None, 'electrometer chn'],
                   ['enabled', Type.Boolean, None, 'Inversion enabled'],
                   {'min': 1}],
                  None, 'List of [channels, inversion]'] ]

    def run(self, chns):
        for ch, enabled in chns:
            old_state = ch.read_attribute('Autorange').value
            ch.write_attribute('Autorange', enabled)
            new_state = ch.read_attribute('Autorange').value
            self.output('{0} changed autorange from {1} '
                        'to {2}'.format(ch, old_state, new_state))


class em_findrange(Macro):
    """
        Macro to find the range.
    """
    param_def = [['chns',
                  [['ch', Type.CTExpChannel, None, 'electrometer chn'],
                   {'min': 1}],
                  None, 'List of [channels]'],
                 ['wait_time', Type.Float, 3, 'time to applied the '
                                               'autorange']]

    def run(self, chns, wait_time):
        chns_enabled = [[chn, True] for chn in chns]
        chns_desabled = [[chn, False] for chn in chns]
        self.em_autorange(chns_enabled)
        t1 = time.time()
        try:
            while time.time()-t1 < wait_time:
                self.checkPoint()
                time.sleep(0.01)
        finally:
            self.em_autorange(chns_desabled)


class em_findmaxrange(Macro):
    """
    Macro to find the electrometer channel range according to the motor
    position

    """
    param_def = [['motor', Type.Moveable, None, 'motor to scan'],
                 ['positions',
                  [['pos', Type.Float, None, 'position'], {'min': 1}],
                  None, 'List of positions'],
                 ['channels',
                  [['chn', Type.CTExpChannel, None, 'electrometer channel'],
                   {'min': 1}],
                  None, 'List of channels'],
                 ['wait_time', Type.Float, 3, 'time to applied the autorange'],
                 ]

    RANGES = ['1mA', '100uA', '10uA', '1uA', '100nA', '10nA', '1nA',
              '100pA', 'none']

    def run(self, motor, positions, chns, wait_time):
        chns_ranges = {}
        previous_chns_ranges = {}

        for chn in chns:
            chns_ranges[chn] = 'none'
            previous_chns_ranges[chn] = chn.range
            self.debug('{0}: {1}'.format(chn.name, 'none'))

        for energy in positions:
            self.umv(motor, energy)

            self.em_findrange(chns, wait_time)
            for chn, prev_range in chns_ranges.items():
                new_range = chn.range
                new_range_idx = self.RANGES.index(new_range)
                prev_range_idx = self.RANGES.index(prev_range)
                if new_range_idx < prev_range_idx:
                    chns_ranges[chn] = new_range

        self.info('Setting maximum range...')
        chns_cfg = []
        for chn, new_range in chns_ranges.items():
            chns_cfg.append([chn, new_range])
        em_range, _ = self.createMacro('em_range', chns_cfg)
        em_range.enabled_output = False
        self.runMacro(em_range)
        for chn, new_range in chns_ranges.items():
            prev_range = previous_chns_ranges[chn]
            self.output('{0} changed range from {1} ' 
                        'to {2}'.format(chn, prev_range, new_range))


