from machine import Pin, ADC
import network
import utime
import microcoapy
from coap_macros import COAP_METHOD
from hcsr04 import HCSR04
from dht import DHT22
import json

# Pins
DHT_PIN = 21
LIGHT_SENSOR_PIN = 34
LED1_PIN = 13
LED2_PIN = 12
LED3_PIN = 27
TRIG_PIN = 32
ECHO_PIN = 33
MAX_BIN_HEIGHT = 100

# Initialize sensors and pins
dht_sensor = DHT22(Pin(DHT_PIN))
light_sensor = ADC(Pin(LIGHT_SENSOR_PIN))
light_sensor.atten(ADC.ATTN_11DB)

led1 = Pin(LED1_PIN, Pin.OUT)
led2 = Pin(LED2_PIN, Pin.OUT)
led3 = Pin(LED3_PIN, Pin.OUT)

ultrasonic_sensor = HCSR04(trigger_pin=TRIG_PIN, echo_pin=ECHO_PIN)

# Global variables
led_states = {
    "led1": False,
    "led2": False,
    "led3": False
}

def connect_wifi(ssid, password):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print('Connecting to network...')
        wlan.connect(ssid, password)
        while not wlan.isconnected():
            pass
    print('Network config:', wlan.ifconfig())
    return wlan

def get_distance():
    try:
        distance = ultrasonic_sensor.distance_cm()
        if distance is not None and distance <= MAX_BIN_HEIGHT:
            fill_percentage = ((MAX_BIN_HEIGHT - distance) / MAX_BIN_HEIGHT) * 100
            return round(fill_percentage, 2)
        return None
    except OSError as e:
        print("Ultrasonic sensor error:", str(e))
        return None

def get_sensor_data():
    try:
        dht_sensor.measure()
        temperature = dht_sensor.temperature()
        humidity = dht_sensor.humidity()
        light_level = light_sensor.read()
        bin_level = get_distance()

        current_time = utime.localtime()
        timestamp = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
            current_time[0], current_time[1], current_time[2],
            current_time[3], current_time[4], current_time[5]
        )

        return {
            "timestamp": timestamp,
            "temperature": temperature,
            "humidity": humidity,
            "lightLevel": light_level,
            "binLevel": bin_level
        }
    except Exception as e:
        print("Error reading sensors:", str(e))
        return None

def setup_server():
    server = microcoapy.Coap()
    
    # Handler for sensor data requests
    def sensor_handler(packet, sender_ip, sender_port):
        print(f'Sensor endpoint accessed from: {sender_ip}:{sender_port}')
        
        if packet.method == COAP_METHOD.COAP_GET:
            sensor_data = get_sensor_data()
            if sensor_data:
                response = json.dumps(sensor_data)
                server.sendResponse(
                    sender_ip, 
                    sender_port, 
                    packet.messageid,
                    response,
                    0x45,  # 2.05 Content
                    0,     # No specific content format
                    packet.token
                )
    
    # Handler for LED control
    def led_handler(packet, sender_ip, sender_port):
        global led_states
        print(f'LED endpoint accessed from: {sender_ip}:{sender_port}')


        
        if packet.method == COAP_METHOD.COAP_GET:
            response = json.dumps(led_states)
            server.sendResponse(
                sender_ip, 
                sender_port, 
                packet.messageid,
                response,
                0x45,  # 2.05 Content
                0,     # No specific content format
                packet.token
            )
        
        if packet.method == COAP_METHOD.COAP_PUT:
            try:
                # Print the raw payload for debugging
                print("Received payload:", packet.payload)
                
                # Handle simple format like "led:2,state:1"
                payload_str = packet.payload.decode('utf-8').strip()
                if ',' in payload_str:
                    led_part, state_part = payload_str.split(',')
                    led_num = int(led_part.split(':')[1])
                    state = int(state_part.split(':')[1])
                    
                    print(f"Parsed values - LED: {led_num}, State: {state}")
                    
                    if led_num == 1:
                        led1.value(state)
                        led_states['led1'] = bool(state)
                    elif led_num == 2:
                        led2.value(state)
                        led_states['led2'] = bool(state)
                    elif led_num == 3:
                        led3.value(state)
                        led_states['led3'] = bool(state)
                    
                    server.sendResponse(
                        sender_ip,
                        sender_port,
                        packet.messageid,
                        None,
                        0x44,  # 2.04 Changed
                        0,
                        packet.token
                    )
                else:
                    raise ValueError("Invalid payload format")
                    
            except Exception as e:
                print("Error handling LED request:", str(e))
                server.sendResponse(
                    sender_ip,
                    sender_port,
                    packet.messageid,
                    str(e),
                    0x80,  # 4.00 Bad Request
                    0,
                    packet.token
                )
    
    # Register endpoints
    server.addIncomingRequestCallback('sensors', sensor_handler)
    server.addIncomingRequestCallback('led', led_handler)
    return server

def run_server():
    # Connect to WiFi
    connect_wifi('Galaxy A06 0a23', '12345678')
    
    # Setup and start server
    server = setup_server()
    server.start()
    print('CoAP server started. Waiting for requests...')
    
    while True:
        try:
            server.poll(10000)
        except Exception as e:
            print("Error in main loop:", str(e))
            utime.sleep_ms(100)

def main():
    while True:
        try:
            run_server()
        except KeyboardInterrupt:
            print("Server stopped by user")
            break
        except Exception as e:
            print("Server error:", str(e))
            print("Restarting server in 5 seconds...")
            utime.sleep(5)

if __name__ == '__main__':
    main()


# PS C:\Users\Irfan> coap put coap://192.168.152.226/led -p "led:2,state:1"
# (2.04)
# PS C:\Users\Irfan> coap get coap://192.168.152.226/led
# (2.05)  {"led3": false, "led1": true, "led2": true}
# PS C:\Users\Irfan> coap get coap://192.168.152.226/sensors
# (2.05)  {"timestamp": "2000-01-01 02:08:43", "temperature": 25.0, "lightLevel": 197, "binLevel": null, "humidity": 33.0}
# PS C:\Users\Irfan>