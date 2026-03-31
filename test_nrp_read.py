import pyvisa
import time

def test_read():
    try:
        rm = pyvisa.ResourceManager()
        resources = rm.list_resources()
        print("Connected VISA resources:")
        
        nrp_found = False
        for res in resources:
            if 'USB' in res or 'RSNRP' in res or '0AAD' in res:
                try:
                    inst = rm.open_resource(res, timeout=2000)
                    idn = inst.query('*IDN?').strip()
                    print(f" -> Found: {res} | IDN: {idn}")
                    
                    if 'NRP' in idn or 'Z85' in idn:
                        nrp_found = True
                        print("    [!] Attempting to read power from this sensor...")
                        inst.write('INIT:CONT ON')
                        time.sleep(0.5)
                        try:
                            # Standard SCPI fetch for R&S power sensors
                            val = inst.query('FETCH?').strip()
                            print(f"    [+] Raw Fetch reading: {val} Watts")
                        except Exception as e:
                            print(f"    [-] Failed to fetch power: {e}")
                            
                    inst.close()
                except Exception as e:
                    pass
                    
        if not nrp_found:
            print("\nDid not find any active R&S NRP sensors in the VISA list.")
            print("Full resource list was:")
            for r in resources:
                print(f"  {r}")
                
    except Exception as e:
        print(f"VISA Error: {e}")

if __name__ == "__main__":
    test_read()