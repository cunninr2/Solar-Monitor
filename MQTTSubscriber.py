#!/usr/bin/python
# to make script run from boot:
# sudo nano /etc/rc.local
# at bottom of rc.local file, befor exit 0 add line 'python /home/pi/{name}.py
#from subprocess import check_output
import sys
import RPi.GPIO as GPIO
import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish
import time
import os
import signal

#Define friendly names for GPIO pins 
relay1 = 27 # garden fountain
relay2 = 26 # garden fountain light
relay3 = 19 # spare
relay4 = 13 # spare

#Set numbering scheme that corresponds to breakout board and pin layout.
#BCM refers to GPIO numbering mode.
GPIO.setmode(GPIO.BCM)

#Switch off the port warnings. use GPIO.cleanup() to exit GPIO correcly and ret$
GPIO.setwarnings(False)

#setup GPIO ports as inputs or outputs 
# relays
GPIO.setup(relay1,GPIO.OUT,initial = 1)  
GPIO.setup(relay2,GPIO.OUT,initial = 1)
GPIO.setup(relay3,GPIO.OUT,initial = 1)
GPIO.setup(relay4,GPIO.OUT,initial = 1)

# Functions -----------------------------------------------------------------------------------------------------------------------------------

def signal_handler(signal, frame):


  if signal == 15:
    GPIO.output(relay1,GPIO.HIGH)
    GPIO.output(relay2,GPIO.HIGH)
    GPIO.output(relay3,GPIO.HIGH)
    GPIO.output(relay4,GPIO.HIGH)
    publish.single("yo105ay/garden/pisolar/switch/1/status", payload="OFF", qos=0, retain=True, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
    publish.single("yo105ay/garden/pisolar/switch/2/status", payload="OFF", qos=0, retain=True, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
    publish.single("yo105ay/garden/pisolar/switch/3/status", payload="OFF", qos=0, retain=True, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
    publish.single("yo105ay/garden/pisolar/switch/4/status", payload="OFF", qos=0, retain=True, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
    publish.single("yo105ay/homeassistant/alerts", payload="SolarPi: MQTTSubscriber - Signal interrupt %2.0f - Quitting" % signal, qos=0, retain=False, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})

  return;

# refer to https://pypi.python.org/pypi/paho-mqtt/1.1 for more information on Mqtt connections
# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    global start_time
    
    start_time = time.time()
    print("Connected to MQTT broker with result code "+str(rc))

# Subscribing in on_connect() means that if we lose the connection and reconnect then subscriptions will be renewed.
    client.subscribe("yo105ay/garden/pisolar/switch/1/set_status")
    client.subscribe("yo105ay/garden/pisolar/switch/2/set_status")
    client.subscribe("yo105ay/garden/pisolar/switch/3/set_status")
    client.subscribe("yo105ay/garden/pisolar/switch/4/set_status")
    client.subscribe("yo105ay/garden/pisolar/switch/all")

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
# print(msg.topic+" "+str(msg.payload))
  global start_time

  if (start_time + 5) > time.time(): 
    print "Set to Ignore any reported retained messages for first 5 seconds"
    return;

  relay_control(msg.topic, msg.payload)

# function to control fountain from messages from broker.
def relay_control(topic, payload):

# if switch 1 action received signal to solarmonitor process for control of this relay
  if topic == "yo105ay/garden/pisolar/switch/1/set_status":
    if payload == "OFF":
      os.system("killall -s SIGUSR1 solarmonitor.py")
    if payload == "ON":
      os.system("killall -s SIGUSR2 solarmonitor.py")

# if switch 2 action received
  if topic == "yo105ay/garden/pisolar/switch/2/set_status":
    if payload == "OFF":
      GPIO.output(relay2,GPIO.HIGH)
      publish.single("yo105ay/garden/pisolar/switch/2/status", payload="OFF", qos=0, retain=True, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
    if payload == "ON":
      GPIO.output(relay2,GPIO.LOW)
      publish.single("yo105ay/garden/pisolar/switch/2/status", payload="ON", qos=0, retain=True, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})

# if switch 3 action received
  if topic == "yo105ay/garden/pisolar/switch/3/set_status":
    if payload == "OFF":
      GPIO.output(relay3,GPIO.HIGH)
      publish.single("yo105ay/garden/pisolar/switch/3/status", payload="OFF", qos=0, retain=True, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
    if payload == "ON":
      GPIO.output(relay3,GPIO.LOW)
      publish.single("yo105ay/garden/pisolar/switch/3/status", payload="ON", qos=0, retain=True, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})

# if switch 4 action received
  if topic == "yo105ay/garden/pisolar/switch/4/set_status":
    if payload == "OFF":
      GPIO.output(relay4,GPIO.HIGH)
      publish.single("yo105ay/garden/pisolar/switch/4/status", payload="OFF", qos=0, retain=True, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
    if payload == "ON":
      GPIO.output(relay4,GPIO.LOW)
      publish.single("yo105ay/garden/pisolar/switch/4/status", payload="ON", qos=0, retain=True, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})

# if report switch status received
  if topic == "yo105ay/garden/pisolar/switch/all":
    if payload == "STATUS":
      get_status()

# if perform relay cycle test received 
  if topic == "yo105ay/garden/pisolar/switch/all":
    if payload == "TEST":
      cycle = 0
      while cycle < 3:
         GPIO.output(relay1,GPIO.LOW)
         time.sleep(1)
         GPIO.output(relay2,GPIO.LOW)
         time.sleep(1)
         GPIO.output(relay3,GPIO.LOW)
         time.sleep(1)
         GPIO.output(relay4,GPIO.LOW)
         time.sleep(1)
         GPIO.output(relay1,GPIO.HIGH)
         GPIO.output(relay2,GPIO.HIGH)
         GPIO.output(relay3,GPIO.HIGH)
         GPIO.output(relay4,GPIO.HIGH)
         time.sleep(1)
         cycle += 1
      publish.single("yo105ay/homeassistant/alerts", payload="SolarPi: MQTTSubscriber.py - Relay cycle request completed", qos=0, retain=False, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})

    return;

def get_status():

      if GPIO.input(relay1): # if port == 1 (relay is off)
         publish.single("yo105ay/garden/pisolar/switch/1/status", payload="OFF", qos=0, retain=True, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
      else:
         publish.single("yo105ay/garden/pisolar/switch/1/status", payload="ON", qos=0, retain=True, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})

      if GPIO.input(relay2): # if port == 1 (relay is off)
         publish.single("yo105ay/garden/pisolar/switch/2/status", payload="OFF", qos=0, retain=True, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
      else:
         publish.single("yo105ay/garden/pisolar/switch/2/status", payload="ON", qos=0, retain=True, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})

      if GPIO.input(relay3): # if port == 1 (relay is off)
         publish.single("yo105ay/garden/pisolar/switch/3/status", payload="OFF", qos=0, retain=True, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
      else:
         publish.single("yo105ay/garden/pisolar/switch/3/status", payload="ON", qos=0, retain=True, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})

      if GPIO.input(relay4): # if port == 1 (relay is off)
         publish.single("yo105ay/garden/pisolar/switch/4/status", payload="OFF", qos=0, retain=True, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
      else:
         publish.single("yo105ay/garden/pisolar/switch/4/status", payload="ON", qos=0, retain=True, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})

      return;

# Main program -----------------------------------------------------------------------------------------------------------------------------------
# watch for signal interrupt by supervisord
signal.signal(signal.SIGTERM, signal_handler)

if os.path.isfile('mqtt_config'):
  print "Reading mqtt config"
  f = open('mqtt_config', 'r')
  lines = f.read().split("\n")
  # load date strings to variabless
  MQTT_hostname = lines[0]
  MQTT_username = lines[1]
  MQTT_password = lines[2]
  f.close()
else:
  print "No mqtt config file found"

publish.single("yo105ay/homeassistant/alerts", payload="SolarPi: MQTTSubscriber.py - process was re-started", qos=0, retain=False, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
print "publish"


while True:
  try:
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.username_pw_set(MQTT_username, MQTT_password) 
    client.connect(MQTT_hostname, 1883, 60)
    client.loop_forever()
  except KeyboardInterrupt:
    GPIO.cleanup() # this ensures a clean exit
    sys.exit("\nKeyboard exit actioned")
  except:
    GPIO.cleanup() # this ensures a clean exit
    publish.single("yo105ay/homeassistant/alerts", payload="SolarPi: MQTTSubscriber.py - Other error or exception occurred!", qos=0, retain=False, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
    sys.exit("\nOther error or exception occurred!")
    


