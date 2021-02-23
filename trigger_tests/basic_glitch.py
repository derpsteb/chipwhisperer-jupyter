import chipfail_lib
import serial
import Setup_Generic

import matplotlib.pyplot as plt

def setup_cw(scope, offset, nr_samples):
    scope.default_setup()
    scope.adc.offset = offset
    scope.gain.gain = 50
    scope.adc.samples = nr_samples
    scope.clock.adc_src = "clkgen_x1"
    scope.clock.clkgen_freq = 150E6
    
    # per docs has to be like that for DecodeIO and SAD
    scope.adc.basic_mode = "rising_edge"

def setup_basic(scope, offset, nr_samples):
    setup_cw(scope, offset, nr_samples)

    scope.adc.basic_mode = "rising_edge"
    scope.trigger.module = "basic"
    scope.trigger.triggers = "tio4"

def collect_trace_basic():
    scope.io.tio1 = "gpio_low"
    scope.arm()
    
    # As long as only the A7's power port is connected to reset this will issue a 1us reset
    # The CW can trigger on the reset release
    chipfail_lib.manual_glitch(fpga)
    
    scope.io.tio1 = "gpio_high"
    scope.capture()
    return scope.get_last_trace()

def setup_glitcher(scope, offset=0, width=1):
    scope.glitch.clk_src = "clkgen"
    # scope.glitch.width = 10
    # scope.glitch.width_fine = 0
    scope.glitch.repeat = width
    scope.glitch.ext_offset = offset
    scope.glitch.trigger_src = "ext_single"
    scope.glitch.output = "enable_only"
    scope.glitch.arm_timing = 'before_scope'

    scope.io.glitch_hp = True
    scope.io.glitch_lp = False

if __name__ == "__main__":

    SCOPETYPE = 'OPENADC'
    PLATFORM = 'CWLITEXMEGA'
    CRYPTO_TARGET = 'AVRCRYPTOLIB'

    scope, target, prog = Setup_Generic.setup(version=None, platform=PLATFORM)
    # Initialize connection to ARTY A7 FPGA
    fpga = serial.Serial("/dev/ttyUSB1", baudrate=115200)
    target = serial.Serial("/dev/ttyUSB2", baudrate=115200, timeout=0.2)

    offset = 0
    nr_samples = 24400

    setup_basic(scope, offset, nr_samples)
    setup_glitcher(scope)
    chipfail_lib.setup(fpga, power_cycle_before_glitch=1)

    scope.adc.decimate = 50

    MIN_OFFSET = 100
    MAX_OFFSET = 3000
    OFFSET_STEP = 1
    MIN_WIDTH = 960
    MAX_WIDTH = 990
    WIDTH_STEP = 1

    print(scope.clock.clkgen_freq)

    success = False
    while not success:
        for offset in range(MIN_OFFSET, MAX_OFFSET, OFFSET_STEP):
            scope.glitch.ext_offset = offset

            for width in range(MIN_WIDTH, MAX_WIDTH, WIDTH_STEP):
                scope.glitch.repeat = width
                trace = collect_trace_basic()    
                # plt.plot(trace)
                # plt.show()
                success = chipfail_lib.success_uart(target, offset, width)
                chipfail_lib.wait_until_rdy(fpga)