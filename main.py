"""
Read ds18B20 sensors and publish to mqtt broker on wlan

Uses pi pico W with sensors on pin 22, GPIO22.
"""

import time
import onewire
import ds18x20
import network
from machine import Pin
from machine import reset
from lib.umqtt.simple import MQTTClient

# passwords etc
import secrets

# mqtt
client_id = 'boiler'

# mqtt topic too ds18b20 sensor ID
sensor_dict = {
    "atc/boiler_out/boiler": bytearray(b'(D^\xcb\x04\x00\x00\xb3'),
    "atc/boiler_return/boiler": bytearray(b'(\x81\xdd\xcb\x04\x00\x00B')
}

# pi pico W on board LED - wont work on standard pi pico
led_pin = Pin("LED", Pin.OUT)
led_pin.off()

# One wire probes are connected to this pin
ds_pin = Pin(22) 

def flash_led(seconds: int, on_pc: float):
    if on_pc > 1.0:
        on_pc = on_pc / 100
    for n in range(0, seconds):
        led_pin.on()
        time.sleep(on_pc)
        led_pin.off()
        time.sleep(1 - on_pc)

def mqtt_connect(sec: dict[str, str]):
    print(f'Connecting to MQTT Broker at {sec["mqtt_broker"]}')
    client = None
    try:
        client = MQTTClient(client_id, sec["mqtt_broker"], keepalive=3600)
        client.connect()
        print(f'Connected to MQTT Broker')
        flash_led(3, 0.5)
    except Exception as s:
        print(f'Something went wrong connecting to MQTT broker')
    return client

def wlan_connect(sec: dict[str, str]):
    wlan = None
    try:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        for wl in wlan.scan():
            print(wl)
        # keep trying
        while not wlan.isconnected():
            print(f'Connecting to wlan, {sec["ssid"]}')
            wlan.connect(sec["ssid"], sec["password"])
            flash_led(1, 0.9)
            time.sleep(3) # give things time to settle on wlan object
        else:
            print(wlan.status(), "rssi", wlan.status('rssi'))
            print(f'Connected to {sec["ssid"]}')
    except Exception as e:
        print("Failed to use wlan, not available?", e)
        raise
    return wlan

def read_and_publish(client: MQTTClient, ds_sensor: ds18x20.DS18X20, sensors: list):
    try:
        ds_sensor.convert_temp()
        
        # about to read, also gives above convert_temp() time to work
        flash_led(1, 0.9)

        for sensor in sensors:
            tempC = ds_sensor.read_temp(sensor)
            if tempC is not None:
                sensor_found = False
                # find correct topic for this sensor
                for topic, addr in sensor_dict.items():
                    if addr == sensor:
                        sensor_found = True
                        print(f'{topic}    {tempC:0.1f} degC')
                        client.publish(topic, f'{tempC:0.1f}')
                        break
                if not sensor_found:
                    print(f'Unexpected sensor: {sensor} {tempC:0.1f} degC')

        # wait 60 seconds between reads
        flash_led(60, 0.2)

    except Exception:
        raise e


# scan for one wire sensors
ds_sensor = ds18x20.DS18X20(onewire.OneWire(ds_pin))
sensors = ds_sensor.scan()
print(f'Found {len(sensors)} sensors')
for sensor in sensors:
    print(sensor)

try: 
    if len(sensors) == 0:
        print("No sensors, exiting")
    else:
        while True:
            wlan = wlan_connect(secrets.my_secrets)

            try:
                client = mqtt_connect(secrets.my_secrets)
                if client is not None:
                    print('Reading sensors and publishing to mqtt server')
                    while True:
                        try:
                            read_and_publish(client, ds_sensor, sensors)
                        except KeyboardInterrupt:
                            break
                        except Exception as e:
                            print(f"Failed to publish: {e}")
                            break

            except OSError as e:
                print(f'Failed to connect to mqttt broker {secrets.my_secrets["mqtt_broker"]}, ', e)

            wlan.disconnect()
            
except Exception:
    pass

for _ in range(5):
    print("Exited")
    flash_led(1, 0.01)
    
reset()


