#!/usr/bin/env python3
# Test script to push data to HM18 BLE module via RPI


import pydbus

class BT_BLE_HM:

    def __init__(self):
        self.dev_id = get_MAC
        self.bluez_service = "org.bluez"
        self.bus = pydbus.SystemBus()
        self.adapter_path = "/org/bluez/hci0"
        self.mngr = self.bus.get( self.bluez_service, "/")
        self.adapter = self.bus.get(
            self.bluez_service,
            self.adapter_path
        )

        self.device = None
        self.device_path = None
        self.char = None
        self.connected = False
        self._error = 0

    def find_device(self):
        objects = self.mngr.GetManagedObjects()
        for path, interfaces in objects.items():
            dev = interfaces.get( "org.bluez.Device1")

            if not dev:
                continue

            if dev.get("Address") == self.dev_id:
                self.device_path = path
                self.device = self.bus.get(
                    self.bluez_service,
                    path
                )

                return True
        return False

    def find_characteristic(self):
        hm_uuid = "0000ffe1-0000-1000-8000-00805f9b34fb"
        start = time.time()
        while time.time() - start < 5:
            objects = self.mngr.GetManagedObjects()
            for path, interfaces in objects.items():
                ch = interfaces.get( "org.bluez.GattCharacteristic1")
                if not ch:
                    continue

                if ch.get("UUID") == hm_uuid and path.startswith(self.device_path):
                    self.char = self.bus.get(
                        self.bluez_service,
                        path
                    )
                    return True
            time.sleep(0.2)
        return False
    
    def connect(self):
        if self.connected:
            return True

        if not self.find_device():
            raise Exception("Device not found")

        print("Connecting...")
        self.device.Connect()
        print("Connected")
        if not self.find_characteristic():
            raise Exception("Characteristic not found")
        print("Characteristic resolved")
        self.connected = True
        return True


    def transmit(self, data):
        if not self.connected:
            self.connect()
        payload = str(data).encode("ascii")
        print(f"Transmitting {payload}.")
        try:
            self.char.WriteValue(payload, {})
        except Exception as e:
            print("Write failed:", e)
            self.connected = False
            try:
                self.device.Disconnect()
            except:
                pass

            print("Reconnecting...")
            self.connect()
            self.char.WriteValue(payload, {})


    def disconnect(self):
        if self.device:
            try:
                self.device.Disconnect()
            except:
                pass
        self.connected = False


    @property
    def error(self):
        return self._error


def main():
    hm = BT_BLE_HM()
    hm.transmit(1234)
    hm.disconnect()

if __name__ == "__main__":
    main()
