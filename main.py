from machine import Pin, ADC
import network
import utime
import microcoapy
from coap_macros import COAP_METHOD
from hcsr04 import HCSR04
from dht import DHT22
import json
import binascii
import uasyncio as asyncio

# Pin Definitions
DHT_PIN = 21  # Pin for DHT22 temperature and humidity sensor
LIGHT_SENSOR_PIN = 34  # Pin for light sensor (ADC)
LED1_PIN = 13  # Pin for red LED
LED2_PIN = 12  # Pin for yellow LED
LED3_PIN = 27  # Pin for green LED
TRIG_PIN = 32  # Pin for ultrasonic sensor trigger
ECHO_PIN = 33  # Pin for ultrasonic sensor echo
MAX_BIN_HEIGHT = 100  # Maximum height of the bin in centimeters

# Initialize Sensors and Pins
dht_sensor = DHT22(Pin(DHT_PIN))  # DHT22 sensor for temperature and humidity
light_sensor = ADC(Pin(LIGHT_SENSOR_PIN))  # Light sensor (ADC)
light_sensor.atten(ADC.ATTN_11DB)  # Set ADC attenuation for full range

led1 = Pin(LED1_PIN, Pin.OUT)  # Red LED
led2 = Pin(LED2_PIN, Pin.OUT)  # Yellow LED
led3 = Pin(LED3_PIN, Pin.OUT)  # Green LED

ultrasonic_sensor = HCSR04(trigger_pin=TRIG_PIN, echo_pin=ECHO_PIN)  # Ultrasonic sensor for distance measurement

# Global Variables
led_states = {
    "redLed": False,
    "yellowLed": False,
    "greenLed": False
}

# Spring Boot CoAP Server Details
SPRING_SERVER_IP = "192.168.152.113"  # Replace with your Spring Boot server IP
SPRING_SERVER_PORT = 5683  # Default CoAP port
LED_STATUS_RESOURCE = "led-status"  # CoAP resource for LED status

# WiFi Connection
def connect_wifi(ssid, password):
    """
    Connect to a WiFi network.
    :param ssid: WiFi SSID
    :param password: WiFi password
    """
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print('Connecting to network...')
        wlan.connect(ssid, password)
        while not wlan.isconnected():
            pass
    print('Network config:', wlan.ifconfig())
    return wlan

# Ultrasonic Sensor: Get Distance and Calculate Fill Percentage
def get_distance():
    """
    Measure the distance using the ultrasonic sensor and calculate the fill percentage of the bin.
    :return: Fill percentage (0-100) or None if an error occurs.
    """
    try:
        distance = ultrasonic_sensor.distance_cm()
        if distance is not None and distance <= MAX_BIN_HEIGHT:
            fill_percentage = ((MAX_BIN_HEIGHT - distance) / MAX_BIN_HEIGHT) * 100
            return round(fill_percentage, 2)
        return None
    except OSError as e:
        print("Ultrasonic sensor error:", str(e))
        return None

# Read Sensor Data
def get_sensor_data():
    """
    Read data from all sensors (DHT22, light sensor, ultrasonic sensor).
    :return: A dictionary containing sensor data or None if an error occurs.
    """
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

# Fetch LED Status from Spring Boot CoAP Server
async def fetch_led_status():
    """
    Fetch the LED status from the Spring Boot CoAP server and update the LEDs.
    """
    global led_states
    client = microcoapy.Coap()

    # Callback function to handle the CoAP response
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
                    await asyncio.sleep_ms(100)  # Small delay to avoid busy-waiting

            if not response_received:
                print("Timeout: No response received from the server")
        else:
            print("Unexpected response type:", type(messageid))
    except Exception as e:
        print("Error fetching LED status:", str(e))
    finally:
        client.stop()

# CoAP Server Setup
def setup_server():
    """
    Set up the CoAP server and register the sensor data endpoint.
    :return: CoAP server instance.
    """
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

    # Register the sensor data endpoint
    server.addIncomingRequestCallback('sensors', sensor_handler)
    return server

# Main Server Loop
async def run_server():
    """
    Run the CoAP server and periodically fetch the LED status.
    """
    # Connect to WiFi
    connect_wifi('Galaxy A06 0a23', '12345678')

    # Setup and start the CoAP server
    server = setup_server()
    server.start()  # Initialize the socket
    print('CoAP server started. Waiting for requests...')

    while True:
        try:
            # Poll the server for incoming requests
            server.poll(10000)

            # Fetch LED status from the Spring Boot server every 5 seconds
            await fetch_led_status()
            await asyncio.sleep(5)  # Wait for 5 seconds before fetching again
        except Exception as e:
            print("Error in main loop:", str(e))
            await asyncio.sleep_ms(100)

# Main Function
async def main():
    """
    Main function to start the server and client tasks.
    """
    while True:
        try:
            await run_server()
        except KeyboardInterrupt:
            print("Server stopped by user")
            break
        except Exception as e:
            print("Server error:", str(e))
            print("Restarting server in 5 seconds...")
            await asyncio.sleep(5)

# Entry Point
if __name__ == '__main__':
    asyncio.run(main())