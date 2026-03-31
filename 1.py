# Constant output leveling control 
import pyvisa as py
from pyvisa import constants as ct
from time import sleep
import numpy as np
import matplotlib.pyplot as plt

PD_ID = 'USB::0x0AAD::0x83::100123' # Last string of numbers is power detector serial number
SigGen_ID = 'TCPIP0::192.168.1.247::hislip0::INSTR'  # VISA ID for signal generator, usually using an IP address
SpecAn_ID = "TCPIP0::192.168.1.160::inst0::INSTR" 
FSV3000 = 0
VISA_LIB = 'C:/Windows/System32/visa64.dll' # To speed up Resource Manager initialization.
DEBUG = 0 # Boolean to show visa log output in terminal, good for debugging. 
CONTROL = 50.5
INIT = -30
FREQ = 6*10^9

def ConnectSG(rm, SG_ID): 
    sg = rm.open_resource(SG_ID) 
    if not sg:
        print('Signal Generator could not be found. Exiting...') 
        quit()
    sg.write('*IDN?') 
    rep = sg.read()
    print('Connected to:' + ' ' + str(rep))
    return sg

def ConnectPD(rm, PD_ID): 
    pd = rm.open_resource(PD_ID) 
    if not pd:
        print('Power Detector could not be found. Exiting...') 
        quit()
    pd.write('*IDN?') 
    rep = pd.read()
    print('Connected to:' + ' ' + str(rep))
    return pd

def ConnectSPA(rm, SPA_ID): 
    spa = rm.open_resource(SPA_ID) 
    if not spa:
        print('Spectrum Analyzer could not be found. Exiting...') 
        quit()
    spa.write('*IDN?') 
    rep = spa.read()
    print('Connected to:' + ' ' + str(rep))
    return spa
    
def SigGenSetup(sg):
    sg.write('*CLS;*RST;*WAI')
    sg.write('SOUR:FREQ:MODE CW')
    pass

def PD_Setup(pd,f):
    pd.write('*RST;*OPC?')
    pd.write('SYST:RUT 5')
    pd.write('INIT:CONT ON')
    pd.write(f'SENS:FREQ {f}')
    print(f'Zeroing at {f}Hz...')
    pd.write('CAL:ZERO:AUTO UFR')
    pd.query('*OPC?')
    print('Zeroing complete')
    # pd.write('SENS:AVER:COUN:AUTO ON')
    # pd.write('SENS:AVER:STAT ON')
    pass

def SPASetup(fc, span, rbw, vbw, spa, ref):
    spa.write('*CLS;*RST;*WAI')
    spa.write('*SRE 128')
    sync(spa)
    spa.write('INIT:CONT OFF')
    spa.write(f"SENS:SWEEP:COUN 20")
    spa.write(f"FREQ:CENT {fc}Hz;*WAI;")
    spa.write(f"FREQ:SPAN {span}MHz;*WAI")
    spa.write(f"DISP:TRAC:Y:RLEV {ref}dBm;*WAI")
    spa.write(f"BAND {rbw}Hz;BAND:VID {vbw}Hz;*WAI")
    spa.write(f"DET:AUTO OFF;*WAI")
    spa.write(f"DISP:TRAC1:MODE WRITE; DET POS; *WAI")
    spa.query("*OPC?")
    pass


def SgOUT(fc,sg,pow):
    sg.write(f"POW:POW {pow}")
    sg.write(f"SOUR:FREQ:CW {fc}Hz;OUTP 1;*WAI")
    sg.query("*OPC?")
    pass

def sync(rm):
    opc = rm.query_ascii_values(f"*OPC?")
    print(opc)
    while not opc:
        sleep(1)
        opc = rm.query_ascii_values(f"*OPC?")
        print(opc)
    pass
    

def VAR():
    f_start = 0.25
    f_end = 30
    step = 0.25
    offset = 0.1 # If measuring edge of band
    n = round((f_end - f_start)/step + 1)
    freq = np.linspace(f_start, f_end, n, True)
    freq[-1] = f_end - offset
    freq *= 10**9
    span = 10
    rbw = 500
    vbw = 500
    pow = 10
    ref = 10
    sfdr = np.zeros(n)
    fdelta = np.zeros(n)
    snr = np.zeros(n)
    i = 0
    return freq, span, rbw, vbw, pow, ref, sfdr, fdelta, snr, i

def pow(pd):
    p = pd.query('FETC?')
    return p

def main():
    if DEBUG == True: py.log_to_screen()
    rm = py.ResourceManager(VISA_LIB)
    sg = ConnectSG(rm, SigGen_ID)
    spa = ConnectSPA(rm, SpecAn_ID)
    spa.timeout = 10000
    pd = ConnectPD(rm, PD_ID)
    pd.timeout = 10000
    # freq, span, rbw, vbw, pow, ref, sfdr, fdelta, snr, i = VAR()
    SigGenSetup(sg)
    sg.write(f"OUTP 0;*WAI")
    PD_Setup(pd,FREQ)
    SgOUT(FREQ, sg, INIT)
    alc = CONTROL - pow(pd)
    while abs(alc) > 0.1:
        pin = INIT
        if alc >= 10:
            pin += alc/2
            SgOUT(FREQ, sg, pin)
            
        elif (alc < 10) and (alc > 0.1):
            pin += min(1, alc)
            SgOUT(FREQ, sg, pin)
            
        elif alc < 0:
            SgOUT(FREQ, sg, pin - 1.5)
        alc = CONTROL - pow(pd)
    print(f"Output power is: {pow(pd)}")
    print("Complete!")
    sleep(1)
    quit()
        
    


    
    



    
    
if __name__ == '__main__':
    main()
    
    