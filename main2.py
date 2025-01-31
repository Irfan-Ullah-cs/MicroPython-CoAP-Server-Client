from machine import Pin
import network
import time
import microcoapy
from coap_macros import COAP_METHOD

# LED setup
led = Pin(13, Pin.OUT)
led_status = False

# Network setup
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

# CoAP server setup
def setup_server():
    server = microcoapy.Coap()
    
    # LED state handler
    def led_handler(packet, sender_ip, sender_port):
        global led_status
        print(f'LED endpoint accessed from: {sender_ip}:{sender_port}')
        
        if packet.method == COAP_METHOD.COAP_GET:
            # Return current LED state
            response = "led:" + str(led_status).lower()
            try:
                server.sendResponse(
                    sender_ip, 
                    sender_port, 
                    packet.messageid,
                    response,
                    0x45,  # 2.05 Content
                    0,     # No specific content format
                    packet.token
                )
                print("GET response sent. LED status:", led_status)
            except Exception as e:
                print("Error sending GET response:", str(e))
            
        elif packet.method == COAP_METHOD.COAP_PUT:
            try:
                # Parse payload
                payload_str = packet.payload.decode('utf-8').strip()
                print("Received payload:", payload_str)
                
                # More flexible payload parsing
                payload_lower = payload_str.lower()
                if "true" in payload_lower or "1" in payload_lower:
                    led_status = True
                    led.value(1)
                elif "false" in payload_lower or "0" in payload_lower:
                    led_status = False
                    led.value(0)
                else:
                    raise ValueError("Invalid payload format")
                
                print("LED status updated to:", led_status)
                
                server.sendResponse(
                    sender_ip,
                    sender_port,
                    packet.messageid,
                    None,
                    0x44,  # 2.04 Changed
                    0,     # No specific content format
                    packet.token
                )
                print("PUT response sent successfully")
                
            except Exception as e:
                print("Error handling PUT request:", str(e))
                try:
                    server.sendResponse(
                        sender_ip,
                        sender_port,
                        packet.messageid,
                        None,
                        0x80,  # 4.00 Bad Request
                        0,     # No specific content format
                        packet.token
                    )
                    print("Error response sent")
                except Exception as send_error:
                    print("Error sending error response:", str(send_error))
    
    # Register endpoints
    server.addIncomingRequestCallback('led', led_handler)
    return server

# Main server execution
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
            # Small delay before continuing
            time.sleep_ms(100)
            continue

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
            time.sleep(5)

if __name__ == '__main__':
    main()