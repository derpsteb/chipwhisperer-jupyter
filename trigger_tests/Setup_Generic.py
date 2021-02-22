import chipwhisperer as cw
import time

def reset_target(scope, platform):
        if platform == "CW303" or platform == "CWLITEXMEGA":
            scope.io.pdic = 'low'
            time.sleep(0.1)
            scope.io.pdic = 'high_z' #XMEGA doesn't like pdic driven high
            time.sleep(0.1) #xmega needs more startup time
        else:  
            scope.io.nrst = 'low'
            time.sleep(0.05)
            scope.io.nrst = 'high_z'
            time.sleep(0.05)

def setup(version, platform):
    try:
        if not scope.connectStatus:
            scope.con()
    except NameError:
        scope = cw.scope()
        
    try:
        if version == "SS_VER_2_0":
            target_type = cw.targets.SimpleSerial2
        else:
            target_type = cw.targets.SimpleSerial
    except:
        version="SS_VER_1_1"
        target_type = cw.targets.SimpleSerial

    try:
        target = cw.target(scope, target_type)
    except IOError:
        print("INFO: Caught exception on reconnecting to target - attempting to reconnect to scope first.")
        print("INFO: This is a work-around when USB has died without Python knowing. Ignore errors above this line.")
        scope = cw.scope()
        target = cw.target(scope)

    print("INFO: Found ChipWhisperer😍")

    if "STM" in platform or platform == "CWLITEARM" or platform == "CWNANO":
        prog = cw.programmers.STM32FProgrammer
    elif platform == "CW303" or platform == "CWLITEXMEGA":
        prog = cw.programmers.XMEGAProgrammer
    else:
        prog = None


    time.sleep(0.05)
    scope.default_setup()
    return (scope, target, prog)