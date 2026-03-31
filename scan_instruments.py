import pyvisa

def scan():
    try:
        rm = pyvisa.ResourceManager()
        resources = rm.list_resources()
        print(f"Found {len(resources)} resources:")
        
        for res in resources:
            print(f"\n- Resource: {res}")
            try:
                inst = rm.open_resource(res, timeout=2000)
                idn = inst.query("*IDN?")
                print(f"  IDN: {idn.strip()}")
                inst.close()
            except Exception as e:
                print(f"  Could not read IDN. Error: {e}")
    except Exception as e:
        print(f"Failed to initialize pyvisa ResourceManager: {e}")

if __name__ == "__main__":
    scan()