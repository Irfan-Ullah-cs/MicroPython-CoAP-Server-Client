from machine import Pin, ADC
import network
import utime
import microcoapy
from coap_macros import COAP_METHOD
from hcsr04 import HCSR04
from dht import DHT22
import json
import binascii

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
    "redLed": False,
    "yellowLed": False,
    "greenLed": False
}

# Spring Boot CoAP server details
SPRING_SERVER_IP = "192.168.152.113"  # Replace with your Spring Boot server IP
SPRING_SERVER_PORT = 5683
LED_STATUS_RESOURCE = "led-status"

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

def fetch_led_status():
    global led_states
    client = microcoapy.Coap()

    # Define a callback function to handle the response
    def received_message_callback(packet, sender):
        global led_states
        print(f"Message received from {sender}: {packet.toString()}")
        print(f"Message payload: {packet.payload.decode('unicode_escape')}")

        # Check if the response code is 2.05 Content
        if packet.method == 0x45:  # 2.05 Content
            try:
                # Parse the JSON response
                new_led_states = json.loads(packet.payload.decode('utf-8'))
                print("Received LED status:", new_led_states)

                # Update the LED states
                led_states = new_led_states

                # Control the LEDs based on the received status
                led1.value(led_states["redLed"])
                led2.value(led_states["yellowLed"])
                led3.value(led_states["greenLed"])
            except Exception as e:
                print("Error parsing LED status:", str(e))
        else:
            print(f"Failed to fetch LED status: Response code {hex(packet.method)}")

    try:
        # Initialize the socket without binding to a specific port
        client.start(port=0)  # Port 0 lets the OS assign an available port
        print("Socket initialized for fetching LED status")

        # Set the response callback
        client.responseCallback = received_message_callback

        # Send a GET request to the Spring Boot CoAP server
        messageid = client.get(SPRING_SERVER_IP, SPRING_SERVER_PORT, LED_STATUS_RESOURCE)

        # Debug: Print the messageid and request details
        print(f"Message ID: {messageid}")
        print(f"Sending GET request to coap://{SPRING_SERVER_IP}:{SPRING_SERVER_PORT}/{LED_STATUS_RESOURCE}")

        if isinstance(messageid, int):
            # Wait for the response with a timeout
            start_time = utime.ticks_ms()
            response_received = False

            while utime.ticks_diff(utime.ticks_ms(), start_time) < 10000:  # Wait for 10 seconds
                try:
                    # Poll the server for incoming responses
                    client.poll(100)  # Poll every 100ms
                except Exception as e:
                    print("Error in poll:", str(e))
                    utime.sleep_ms(100)  # Small delay to avoid busy-waiting

            if not response_received:
                print("Timeout: No response received from the server")
        else:
            print("Unexpected response type:", type(messageid))
    except Exception as e:
        print("Error fetching LED status:", str(e))
    finally:
        client.stop()


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
    
    # Register endpoints
    server.addIncomingRequestCallback('sensors', sensor_handler)
    return server

def run_server():
    # Connect to WiFi
    connect_wifi('Galaxy A06 0a23', '12345678')
    
    # Setup and start server
    server = setup_server()
    server.start()  # Initialize the socket
    print('CoAP server started. Waiting for requests...')
    
    while True:
        try:
            # Poll the server for incoming requests
            server.poll(10000)

            # Fetch LED status from the Spring Boot server every 5 seconds
            fetch_led_status()
            utime.sleep(5)  # Wait for 5 seconds before fetching again
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