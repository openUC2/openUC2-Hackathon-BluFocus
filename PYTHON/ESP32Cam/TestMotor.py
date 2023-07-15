import uc2rest

mPort ="/dev/cu.usbserial-A50285BI"
ESP32 = uc2rest.UC2Client(serialport=mPort, DEBUG=True)
# setting debug output of the serial to true - all message will be printed
ESP32.serial.DEBUG=True

5
# move and measure
print("Current position: "+ str(ESP32.motor.get_position(axis=1)))
ESP32.motor.move_z(steps=1000, speed=1000, is_blocking=True, is_absolute=False, is_enabled=True)

# 
ESP32.motor.move_z(steps=-1000, speed=1000, is_blocking=True, is_absolute=False, is_enabled=True)
