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
class PinConfig:
    DHT_PIN = 21
    LIGHT_SENSOR_PIN = 34
    LED1_PIN = 13  # Red
    LED2_PIN = 12  # Yellow
    LED3_PIN = 27  # Green
    TRIG_PIN = 32
    ECHO_PIN = 33
    MAX_BIN_HEIGHT = 100  # cm

# Network Configuration
class NetworkConfig:
    WIFI_SSID = 'Galaxy A06 0a23'
    WIFI_PASSWORD = '12345678'
    SPRING_SERVER_IP = "192.168.152.113"
    SPRING_SERVER_PORT = 5683
    LED_STATUS_RESOURCE = "led-status"

# Sensor and LED Management
class SensorManager:
    def __init__(self):
        # Initialize sensors
        self.dht_sensor = DHT22(Pin(PinConfig.DHT_PIN))
        self.light_sensor = ADC(Pin(PinConfig.LIGHT_SENSOR_PIN))
        self.light_sensor.atten(ADC.ATTN_11DB)
        self.ultrasonic_sensor = HCSR04(trigger_pin=PinConfig.TRIG_PIN, 
                                      echo_pin=PinConfig.ECHO_PIN)
        
        # Initialize LEDs
        self.led1 = Pin(PinConfig.LED1_PIN, Pin.OUT)
        self.led2 = Pin(PinConfig.LED2_PIN, Pin.OUT)
        self.led3 = Pin(PinConfig.LED3_PIN, Pin.OUT)
        
        # LED states
        self.led_states = {
            "redLed": False,
            "yellowLed": False,
            "greenLed": False
        }

    def update_led_states(self, new_states):
        """Update LED states and physical LED outputs"""
        self.led_states = new_states
        self.led1.value(new_states["redLed"])
        self.led2.value(new_states["yellowLed"])
        self.led3.value(new_states["greenLed"])

    def get_distance(self):
        """Get distance measurement and calculate fill percentage"""
        try:
            distance = self.ultrasonic_sensor.distance_cm()
            if distance is not None and distance <= PinConfig.MAX_BIN_HEIGHT:
                fill_percentage = ((PinConfig.MAX_BIN_HEIGHT - distance) / 
                                 PinConfig.MAX_BIN_HEIGHT) * 100
                return round(fill_percentage, 2)
            return None
        except OSError as e:
            print("Ultrasonic sensor error:", str(e))
            return None

    def get_sensor_data(self):
        """Get data from all sensors"""
        try:
            self.dht_sensor.measure()
            temperature = self.dht_sensor.temperature()
            humidity = self.dht_sensor.humidity()
            light_level = self.light_sensor.read()
            bin_level = self.get_distance()

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

# Network Manager
class NetworkManager:
    @staticmethod
    async def connect_wifi():
        """Connect to WiFi network"""
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        
        if not wlan.isconnected():
            print('Connecting to network...')
            wlan.connect(NetworkConfig.WIFI_SSID, NetworkConfig.WIFI_PASSWORD)
            
            # Wait for connection with timeout
            start_time = utime.time()
            while not wlan.isconnected():
                if utime.time() - start_time > 20:  # 20 second timeout
                    raise Exception("WiFi connection timeout")
                await asyncio.sleep_ms(100)
                
        print('Network config:', wlan.ifconfig())
        return wlan

# CoAP Client for LED Status
class LEDStatusClient:
    def __init__(self, sensor_manager):
        self.sensor_manager = sensor_manager

    async def fetch_led_status(self):
        """Fetch LED status from Spring Boot server"""
        client = microcoapy.Coap()
        
        def received_message_callback(packet, sender):
            print(f"Message received from {sender}: {packet.toString()}")
            
            if packet.method == 0x45:  # 2.05 Content
                try:
                    new_led_states = json.loads(packet.payload.decode('utf-8'))
                    print("Received LED status:", new_led_states)
                    self.sensor_manager.update_led_states(new_led_states)
                except Exception as e:
                    print("Error parsing LED status:", str(e))
            else:
                print(f"Failed to fetch LED status: Response code {hex(packet.method)}")

        try:
            client.start(port=0)
            client.responseCallback = received_message_callback
            
            messageid = client.get(
                NetworkConfig.SPRING_SERVER_IP,
                NetworkConfig.SPRING_SERVER_PORT,
                NetworkConfig.LED_STATUS_RESOURCE
            )
            
            if isinstance(messageid, int):
                start_time = utime.ticks_ms()
                while utime.ticks_diff(utime.ticks_ms(), start_time) < 5000:  # 5s timeout
                    client.poll(100)
                    await asyncio.sleep_ms(100)
            
        except Exception as e:
            print("Error fetching LED status:", str(e))
        finally:
            client.stop()

    async def run(self):
        """Main LED status client loop"""
        while True:
            try:
                await self.fetch_led_status()
                await asyncio.sleep(5)  # 5 second delay between updates
            except Exception as e:
                print("LED client error:", str(e))
                await asyncio.sleep(5)  # Wait before retry

# CoAP Server
class SensorServer:
    def __init__(self, sensor_manager):
        self.sensor_manager = sensor_manager
        self.server = microcoapy.Coap()

    def setup(self):
        """Setup CoAP server and register endpoints"""
        def sensor_handler(packet, sender_ip, sender_port):
            print(f'Sensor endpoint accessed from: {sender_ip}:{sender_port}')
            
            if packet.method == COAP_METHOD.COAP_GET:
                sensor_data = self.sensor_manager.get_sensor_data()
                if sensor_data:
                    response = json.dumps(sensor_data)
                    self.server.sendResponse(
                        sender_ip,
                        sender_port,
                        packet.messageid,
                        response,
                        0x45,  # 2.05 Content
                        0,     # No specific content format
                        packet.token
                    )

        self.server.addIncomingRequestCallback('sensors', sensor_handler)
        self.server.start()
        print('CoAP server started. Waiting for requests...')

    async def run(self):
        """Main server loop"""
        self.setup()
        while True:
            try:
                self.server.poll(1000)  # 1 second poll timeout
                await asyncio.sleep_ms(100)  # Allow other tasks to run
            except Exception as e:
                print("Server error:", str(e))
                await asyncio.sleep_ms(100)

# Main Application
class CoAPApplication:
    def __init__(self):
        self.sensor_manager = SensorManager()
        self.led_client = LEDStatusClient(self.sensor_manager)
        self.sensor_server = SensorServer(self.sensor_manager)

    async def run(self):
        """Run the main application"""
        try:
            # Connect to WiFi
            await NetworkManager.connect_wifi()
            
            # Create tasks
            server_task = asyncio.create_task(self.sensor_server.run())
            client_task = asyncio.create_task(self.led_client.run())
            
            # Wait for both tasks
            await asyncio.gather(server_task, client_task)
            
        except Exception as e:
            print("Application error:", str(e))
        finally:
            # Cleanup if needed
            pass

# Entry point
if __name__ == '__main__':
    app = CoAPApplication()
    asyncio.run(app.run())