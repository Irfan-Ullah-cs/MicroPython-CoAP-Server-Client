# MicroPython-CoAP-Server-Client

This repository contains a **MicroPython-based CoAP (Constrained Application Protocol) Server and Client** implementation for IoT devices. The project demonstrates how to use CoAP for communication between IoT devices and a server, enabling efficient and lightweight data exchange in constrained environments.

---

## Features

- **CoAP Server**:
  - Hosts a CoAP resource for sensor data (e.g., temperature, humidity, light level, bin fill level).
  - Responds to GET requests with sensor data in JSON format.
  - Supports multiple endpoints for different resources.

- **CoAP Client**:
  - Fetches LED status from a remote CoAP server (e.g., Spring Boot CoAP server).
  - Updates LEDs based on the received status.

- **Sensor Integration**:
  - Reads data from:
    - DHT22 (temperature and humidity sensor).
    - Light sensor (ADC).
    - Ultrasonic sensor (bin fill level).

- **LED Control**:
  - Controls LEDs (red, yellow, green) based on the status received from the CoAP server.

- **Asynchronous Operation**:
  - Uses `uasyncio` for non-blocking server and client operations.

---

## Hardware Requirements

- Microcontroller: ESP32 or similar MicroPython-compatible device.
- Sensors:
  - DHT22 (temperature and humidity).
  - Light sensor (ADC).
  - Ultrasonic sensor (HC-SR04).
- LEDs: Red, Yellow, Green.
- Wi-Fi connectivity.

---

## Software Requirements

- **MicroPython**: Firmware for the microcontroller.
- **Python Libraries**:
  - `microcoapy`: CoAP implementation for MicroPython.
  - `DHT22`: Library for reading temperature and humidity.
  - `HCSR04`: Library for ultrasonic sensor.
- **Spring Boot CoAP Server**: For testing the client (optional).

---

## Installation

1. **Flash MicroPython**:
   - Download the latest MicroPython firmware for your microcontroller from [micropython.org](https://micropython.org/download/).
   - Flash the firmware using `esptool` or a similar tool.

2. **Upload Code**:
   - Use `ampy`, `rshell`, or Thonny IDE to upload the Python files to your microcontroller.

3. **Install Dependencies**:
   - Upload the following libraries to your microcontroller:
     - `microcoapy.py`
     - `dht.py`
     - `hcsr04.py`

4. **Configure Wi-Fi**:
   - Update the `connect_wifi()` function in the code with your Wi-Fi SSID and password.

---

## Usage

### 1. **CoAP Server**
- The server hosts a CoAP resource at `/sensors`.
- To fetch sensor data, send a GET request to:
  ```
  coap://<device-ip>/sensors
  ```
- Example response:
  ```json
  {
    "timestamp": "2025-01-30 14:22:15",
    "temperature": 25.6,
    "humidity": 45.0,
    "lightLevel": 512,
    "binLevel": 75.5
  }
  ```

### 2. **CoAP Client**
- The client fetches LED status from a remote CoAP server (e.g., Spring Boot CoAP server).
- The server should host a resource at `/led-status`.
- Example response:
  ```json
  {
    "redLed": false,
    "yellowLed": true,
    "greenLed": false
  }
  ```

### 3. **Run the Code**
- Upload the `main.py` file to your microcontroller and reset the device.
- The server will start automatically, and the client will periodically fetch the LED status.

---

## Example Code

### **CoAP Server with Sensors**
```python
from machine import Pin, ADC
import network
import utime
import microcoapy
from coap_macros import COAP_METHOD
from hcsr04 import HCSR04
from dht import DHT22
import json

# Initialize sensors and pins
dht_sensor = DHT22(Pin(21))
light_sensor = ADC(Pin(34))
ultrasonic_sensor = HCSR04(trigger_pin=32, echo_pin=33)

# CoAP server setup
def setup_server():
    server = microcoapy.Coap()

    def sensor_handler(packet, sender_ip, sender_port):
        sensor_data = get_sensor_data()
        if sensor_data:
            response = json.dumps(sensor_data)
            server.sendResponse(sender_ip, sender_port, packet.messageid, response, 0x45, 0, packet.token)

    server.addIncomingRequestCallback('sensors', sensor_handler)
    return server

# Run the server
def run_server():
    connect_wifi('your-ssid', 'your-password')
    server = setup_server()
    server.start()
    print('CoAP server started. Waiting for requests...')

    while True:
        server.poll(10000)

# Main function
if __name__ == '__main__':
    run_server()
```

### **CoAP Client for LED Control**
```python
import microcoapy
import json

def fetch_led_status():
    client = microcoapy.Coap()

    def received_message_callback(packet, sender):
        if packet.method == 0x45:  # 2.05 Content
            led_states = json.loads(packet.payload.decode('utf-8'))
            print("Received LED status:", led_states)
            # Update LEDs here

    client.responseCallback = received_message_callback
    client.start(port=0)
    client.get('192.168.1.2', 5683, 'led-status')
    client.poll(10000)
    client.stop()

# Main function
if __name__ == '__main__':
    fetch_led_status()
```

---

## Contributing
Contributions are welcome! Please follow these steps:

1. Fork the repository.
2. Create a new branch:
   ```
   git checkout -b feature-branch
   ```
3. Commit your changes:
   ```
   git commit -m 'Add new feature'
   ```
4. Push to the branch:
   ```
   git push origin feature-branch
   ```
5. Open a pull request.

---

## License
This project is licensed under the MIT License. See the LICENSE file for details.

---

## Acknowledgments
- MicroPython for providing the firmware.
- CoAP for the lightweight communication protocol.
- Spring Boot CoAP for the CoAP server implementation.

---

## Contact
For questions or feedback, please open an issue or contact the maintainer:

**Irfan Ullah**
- **GitHub**: [Irfan-Ullah-cs](https://github.com/Irfan-Ullah-cs)
- **Email**: [imirfan.cs@gmail.com](mailto:imirfan.cs@gmail.com)
