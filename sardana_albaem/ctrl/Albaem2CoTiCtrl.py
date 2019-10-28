#!/usr/bin/env python
import time

from sardana import State, DataAccess
from sardana.pool import AcqSynch
from sardana.pool.controller import CounterTimerController, Type, Access, \
    Description, Memorize, Memorized, NotMemorized
from sardana.sardanavalue import SardanaValue

from .em2 import Em2


__all__ = ['Albaem2CoTiCtrl']

TRIGGER_INPUTS = {'DIO_1': 0, 'DIO_2': 1, 'DIO_3': 2, 'DIO_4': 3,
                  'DIFF_IO_1': 4, 'DIFF_IO_2': 5, 'DIFF_IO_3': 6,
                  'DIFF_IO_4': 7, 'DIFF_IO_5': 8, 'DIFF_IO_6': 9,
                  'DIFF_IO_7': 10, 'DIFF_IO_8': 11, 'DIFF_IO_9': 12}


class Albaem2CoTiCtrl(CounterTimerController):
    MaxDevice = 5

    ctrl_properties = {
        'AlbaEmHost': {
            Description: 'AlbaEm Host name',
            Type: str
        },
        'Port': {
            Description: 'AlbaEm Host name',
            Type: int
        },
    }

    ctrl_attributes = {
        'ExtTriggerInput': {
            Type: str,
            Description: 'ExtTriggerInput',
            Access: DataAccess.ReadWrite,
            Memorize: Memorized
        },
        'AcquisitionMode': {
            Type: str,
            # TODO define the modes names ?? (I_AVGCURR_A, Q_CHARGE_C)
            Description: 'Acquisition Mode: CHARGE, INTEGRATION',
            Access: DataAccess.ReadWrite,
            Memorize: Memorized
        },
    }

    axis_attributes = {
        "Range": {
            Type: str,
            Description: 'Range for the channel',
            Memorize: NotMemorized,
            Access: DataAccess.ReadWrite,
        },
        "Inversion": {
            Type: bool,
            Description: 'Channel Digital inversion',
            Memorize: NotMemorized,
            Access: DataAccess.ReadWrite,

        },
        "FORMULA":
            {
                Type: str,
                Description: 'The formula to get the real value.\n '
                             'e.g. "(value/10)*1e-06"',
                Access: DataAccess.ReadWrite
            },
    }

    def __init__(self, inst, props, *args, **kwargs):
        """Class initialization."""
        CounterTimerController.__init__(self, inst, props, *args, **kwargs)
        msg = "__init__(%s, %s): Entering...", repr(inst), repr(props)
        self._log.debug(msg)

        self.em2 = Em2(self.AlbaEmHost, self.Port)
        self.index = 0
        self.master = None
        self._latency_time = 0.001  # In fact, it is just 320us
        self._repetitions = 0
        self.formulas = {1: 'value', 2: 'value', 3: 'value', 4:'value'}

    def AddDevice(self, axis):
        """Add device to controller."""
        self._log.debug("AddDevice(%d): Entering...", axis)
        # count buffer for the continuous scan
        if axis != 1:
            self.index = 0

    def DeleteDevice(self, axis):
        """Delete device from the controller."""
        self._log.debug("DeleteDevice(%d): Entering...", axis)

    def StateAll(self):
        """Read state of all axis."""
        # self._log.debug("StateAll(): Entering...")
        state = self.em2.acquisition_state

        if state in ['ACQUIRING', 'RUNNING']:
            self.state = State.Moving

        elif state == 'ON':
            self.state = State.On

        elif state == 'FAULT':
            self.state = State.Fault

        else:
            self.state = State.Fault
            self._log.debug("StateAll(): %r %r UNKNWON STATE: "
                            "%s" % self.state, self.status, state)
        self.status = state
        # self._log.debug("StateAll(): %r %r" %(self.state, self.status))

    def StateOne(self, axis):
        """Read state of one axis."""
        # self._log.debug("StateOne(%d): Entering...", axis)
        return self.state, self.status

    def LoadOne(self, axis, value, repetitions):
        # self._log.debug("LoadOne(%d, %f, %d): Entering...", axis, value,
        #                 repetitions)
        if axis != 1:
            raise Exception('The master channel should be the axis 1')

        self.itime = value
        self.index = 0

        # Set Integration time in ms
        if value < 1E-4:   # minimum integration time
            self._log.debug("The minimum integration time is 0.1 ms")
            value = 1E-4
        self.em2.acquisition_time = value

        if self._synchronization in [AcqSynch.SoftwareTrigger,
                                     AcqSynch.SoftwareGate]:
            # self._log.debug("SetCtrlPar(): setting synchronization "
            #                 "to SoftwareTrigger")
            self._repetitions = 1
            source = 'SOFTWARE'

        elif self._synchronization == AcqSynch.HardwareTrigger:
            # self._log.debug("SetCtrlPar(): setting synchronization "
            #                 "to HardwareTrigger")
            source = 'HARDWARE'
            self._repetitions = repetitions
        elif self._synchronization == AcqSynch.HardwareGate:
            # self._log.debug("SetCtrlPar(): setting synchronization "
            #                 "to HardwareGate")
            source = 'GATE'
            self._repetitions = repetitions
        self.em2.trigger_mode = source

        # Set Number of Triggers
        self.nb_points = self._repetitions

    def PreStartOneCT(self, axis):
        # self._log.debug("PreStartOneCT(%d): Entering...", axis)
        if axis != 1:
            self.index = 0

        #Check if the communication is stable before start
        state = self.em2.acquisition_state
        if state is None:
            return False

        return True

    def StartAllCT(self):
        """
        Starting the acquisition is done only if before was called
        PreStartOneCT for master channel.
        """
        # self._log.debug("StartAllCT(): Entering...")
        swtrig = self._synchronization in [AcqSynch.SoftwareTrigger,
                                           AcqSynch.SoftwareGate]
        self.em2.start_acquisition(swtrig)
        # THIS PROTECTION HAS TO BE REVIEWED
        # FAST INTEGRATION TIMES MAY RAISE WRONG EXCEPTIONS
        # e.g. 10ms ACQTIME -> self.state MAY BE NOT MOVING BECAUSE
        # FINISHED, NOT FAILED
        self.StateAll()
        t0 = time.time()
        while (self.state != State.Moving):
            if time.time() - t0 > 3:
                raise Exception('The HW did not start the acquisition')
            self.StateAll()
        return True

    def ReadAll(self):
        # self._log.debug("ReadAll(): Entering...")
        # TODO Change the ACQU:MEAS command by CHAN:CURR
        data_ready = self.em2.nb_points_ready
        self.new_data = []
        try:
            if self.index < data_ready:
                data_len = data_ready - self.index
                # THIS CONTROLLER IS NOT YET READY FOR TIMESTAMP DATA
                self.timestamp_data = False

                data = self.em2.read(self.index - 1, data_len)
                axis = 1
                for chn_name, values in data.items():

                    # Apply the formula for each value
                    formula = self.formulas[axis]
                    formula = formula.lower()
                    values_formula = [eval(formula, {'value': val}) for val
                                      in values]
                    self.new_data.append(values_formula)
                    axis +=1
                time_data = [self.itime] * len(self.new_data[0])
                self.new_data.insert(0, time_data)
                if self._repetitions != 1:
                    self.index += len(time_data)

        except Exception as e:
            raise Exception("ReadAll error: %s: " + str(e))

    def ReadOne(self, axis):
        # self._log.debug("ReadOne(%d): Entering...", axis)
        if len(self.new_data) == 0:
            return None

        if self._synchronization in [AcqSynch.SoftwareTrigger,
                                     AcqSynch.SoftwareGate]:
            return SardanaValue(self.new_data[axis - 1][0])
        else:
            val = self.new_data[axis - 1]
            return val

    def AbortOne(self, axis):
        # self._log.debug("AbortOne(%d): Entering...", axis)
        self.em2.stop_acquisition()

###############################################################################
#                Axis Extra Attribute Methods
###############################################################################

    def GetExtraAttributePar(self, axis, name):
        self._log.debug("GetExtraAttributePar(%d, %s): Entering...", axis,
                        name)
        if axis == 1:
            raise ValueError('The axis 1 does not use the extra attributes')

        name = name.lower()
        axis -= 2
        if name == "range":
            return self.em2[axis].range
        elif name == 'inversion':
            return self.em2[axis].inversion

    def SetExtraAttributePar(self, axis, name, value):
        if axis == 1:
            raise ValueError('The axis 1 does not use the extra attributes')

        name = name.lower()
        axis -= 2
        if name == "range":
            self.em2[axis].range = value
        elif name == 'inversion':
            self.em2[axis].inversion = int(value)


###############################################################################
#                Controller Extra Attribute Methods
###############################################################################

    def SetCtrlPar(self, parameter, value):
        param = parameter.lower()
        if param == 'exttriggerinput':
            self.em2.trigger_input = value
        elif param == 'acquisitionmode':
            self.em2.acquisition_mode = value
        else:
            CounterTimerController.SetCtrlPar(self, parameter, value)

    def GetCtrlPar(self, parameter):
        param = parameter.lower()
        if param == 'exttriggerinput':
            value = self.em2.trigger_input
        elif param == 'acquisitionmode':
            value = self.em2.acquisition_mode
        else:
            value = CounterTimerController.GetCtrlPar(self, parameter)
        return value


def main():
    host = 'electproto38'
    port = 6025
    ctrl = Albaem2CoTiCtrl('test', {'AlbaEmHost': host, 'Port': port})
    ctrl.AddDevice(1)
    ctrl.AddDevice(2)
    ctrl.AddDevice(3)
    ctrl.AddDevice(4)
    ctrl.AddDevice(5)

    ctrl._synchronization = AcqSynch.SoftwareTrigger
    # ctrl._synchronization = AcqSynch.HardwareTrigger
    acqtime = 1.1
    ctrl.LoadOne(1, acqtime, 10)
    t0 = time.time()
    ctrl.StartAllCT()
    ctrl.StateAll()
    while ctrl.StateOne(1)[0] != State.On:
        ctrl.StateAll()
        time.sleep(0.1)
    print(time.time() - t0 - acqtime)
    ctrl.ReadAll()
    print(ctrl.ReadOne(2))
    return ctrl

if __name__ == '__main__':
    main()
