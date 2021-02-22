import chipfail_lib
import serial
import Setup_Generic

import holoviews as hv


def setup_cw(scope, offset, nr_samples):
    scope.default_setup()
    scope.adc.offset = offset
    scope.gain.gain = 50
    scope.adc.samples = nr_samples
    #scope.adc.presamples = 400
    
    # per docs has to be like that for DecodeIO and SAD
    scope.adc.basic_mode = "rising_edge"

def setup_basic(scope, offset, nr_samples):
    setup_cw(scope, offset, nr_samples)

    scope.adc.basic_mode = "rising_edge"
    scope.trigger.module = "basic"
    scope.trigger.triggers = "tio4"

def collect_trace_basic():
    scope.arm()
    
    # As long as only the A7's power port is connected to reset this will issue a 1us reset
    # The CW can trigger on the reset release
    chipfail_lib.manual_glitch(fpga)
    
    scope.capture()
    return scope.get_last_trace()

def setup_glitcher(scope):
    scope.glitch.clk_src = "clkgen"
    # scope.glitch.width = 10
    # scope.glitch.width_fine = 0
    scope.glitch.repeat = 4000
    scope.glitch.ext_offset = 0
    scope.glitch.trigger_src = "ext_continuous"
    scope.glitch.output = "enable_only"
    scope.glitch.arm_timing = 'before_scope'

    scope.io.glitch_hp = True
    scope.io.glitch_lp = False

if __name__ == "__main__":

    SCOPETYPE = 'OPENvADC'
    PLATFORM = 'CWLITEXMEGA'
    CRYPTO_TARGET = 'AVRCRYPTOLIB'

    scope, target, prog = Setup_Generic.setup(version=None, platform=PLATFORM)
    # Initialize connection to ARTY A7 FPGA
    fpga = serial.Serial("/dev/ttyUSB1", baudrate=115200)
    chipfail_lib.setup(fpga)

    offset = 0
    nr_samples = 24400
    setup_basic(scope, offset, nr_samples)
    setup_glitcher(scope)
    for i in range(0, 10):
        trace = collect_trace_basic()
        foo = input("next?")
        if foo == "y":
            continue
        if foo == "n":
            break
    
    