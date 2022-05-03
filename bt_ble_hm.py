#!/usr/bin/env python3
# Test script to push data to HM18 BLE module via RPI

import pydbus
import sys
import re

class BT_BLE_HM():
    def __init__(self):
        self.dev_id = MAC_ADDRESS

        self.bluez_service = 'org.bluez'
        adapter_path = '/org/bluez/hci0'
        device_path = f"{adapter_path}/dev_{self.dev_id.replace(':', '_')}"
        self.bus = pydbus.SystemBus()
        self.adapter = self.bus.get(self.bluez_service, adapter_path)
        self.device = self.bus.get(self.bluez_service, device_path)


    def connect(self):
        self.device.Connect()
        self.mngr = self.bus.get(self.bluez_service, '/')

        def get_characteristic_path(dev_path, uuid):
            mng_objs = self.mngr.GetManagedObjects()
            for path in mng_objs:
                chr_uuid = mng_objs[path].get('org.bluez.GattCharacteristic1', {}).get('UUID')
                if path.startswith(dev_path) and chr_uuid == uuid:
                    return path


        hm_uuid = "0000ffe1-0000-1000-8000-00805f9b34fb"
        self.char_path = get_characteristic_path(self.device._path, hm_uuid)

        #btn = bus.get(bluez_service, char_path)
        #print(btn.ReadValue({}))

        self.hm_path = get_characteristic_path(self.device._path, hm_uuid)
        self.hm_period = self.bus.get(self.bluez_service, self.hm_path)


    def transmit(self, data):
        self.connect()
        new_value = str(data).encode('ascii')
        self.hm_period.WriteValue(new_value, {})
        self.device.Disconnect()



def main():
    hm = BT_BLE_HM()
    hm.transmit(12345678901234567890123456789012345678901234567890123456789012345678901234567890)



# call main
if __name__ == '__main__':
    main()
