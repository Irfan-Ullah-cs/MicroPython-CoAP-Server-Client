import utime
from machine import Pin, time_pulse_us

class HCSR04:
    def __init__(self, trigger_pin, echo_pin):
        self.trigger = Pin(trigger_pin, Pin.OUT)
        self.echo = Pin(echo_pin, Pin.IN)
    
    def distance_cm(self):
        self.trigger.value(0)
        utime.sleep_us(2)
        self.trigger.value(1)
        utime.sleep_us(10)
        self.trigger.value(0)
        
        # Wait for pulse and measure duration
        duration = time_pulse_us(self.echo, 1, 30000)
        
        # Calculate distance 
        distance = (duration / 2) / 29.1
        return distance