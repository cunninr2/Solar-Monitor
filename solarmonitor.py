#!/usr/bin/python
# To make script run from boot:
# sudo nano /etc/rc.local
# at bottom of rc.local file, befor exit 0 add line 'python /home/pi/{name}.py

import socket
import sys
import signal
import RPi.GPIO as GPIO
import paho.mqtt.publish as publish
import Adafruit_DHT
import time
import os
from Subfact_ina219 import INA219
import datetime
import subprocess

# Setup DHT22 temperature sensor.
#sensor_args = { '11': Adafruit_DHT.DHT11,
#                '22': Adafruit_DHT.DHT22,
#                '2302': Adafruit_DHT.AM2302 }
#if len(sys.argv) == 3 and sys.argv[1] in sensor_args:
dht22sensor = 22
dht22pin = 4

#Define GPIO pin names
buttonPin = 17
#fountainSig = 5 
outputPin = 27
LED = 22

#Set numbering scheme that corresponds to breakout board and pin layout.
#BCM refers to GPIO numbering mode.
GPIO.setmode(GPIO.BCM)

#Switch off the port warnings. use GPIO.cleanup() to exit GPIO correcly and ret$
GPIO.setwarnings(False)

#setup GPIO pin and startup status to 'off'
GPIO.setup(outputPin,GPIO.OUT,initial = 1)
GPIO.setup(buttonPin,GPIO.IN, pull_up_down = GPIO.PUD_UP) # with pull up resistor state
#GPIO.setup(fountainSig,GPIO.OUT, initial = 0) # with pull up resistor state
GPIO.setup(LED,GPIO.OUT,initial = 0)

# Functions --------------------------------------------------------------------------------------------------------$

def signal_handler(signal, frame):

  global AccPower,AccPowerGen,BatteryWatts
  if signal == 15:
    f = open('tempvar.txt', 'w')
    f.write ("%.3f %.3f %.3f\n" % (AccPower,AccPowerGen,BatteryWatts))
    f.close()
    GPIO.output(outputPin,GPIO.HIGH)
    publish.single("yo105ay/garden/pisolar/switch/1/status", payload="OFF", qos=0, retain=True, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
    publish.single("yo105ay/homeassistant/alerts", payload="SolarPi: SolarMonitor.py received signal interrupt %2.0f - Quitting" % signal, qos=0, retain=False, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
  
  if signal == 10: #sigusr message from MQTTSubscriber
    req_fountain_off()

  if signal == 12: #sigusr message from MQTTSubscriber
    req_fountain_on()
    
  return;

def req_fountain_on():

  global BatteryWarning, outputPinCheck

# Ignore button press if there is a battery warning and flash warning message
  if BatteryWarning == 1: # skip over if there is a battery warning
    publish.single("yo105ay/homeassistant/alerts", payload="SolarPi: fountain switch denied - battery low", qos=0, retain=False, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
    count = 0 # blink LED
    while count < 3:
      GPIO.output(LED,GPIO.HIGH)
      time.sleep(.3)
      GPIO.output(LED,GPIO.LOW)
      time.sleep(.3)
      count += 1
    return;

  GPIO.output(outputPin,GPIO.LOW)
  outputPinCheck = 0 # set this flag so that status is not published again in def_readtimes
  publish.single("yo105ay/garden/pisolar/switch/1/status", payload="ON", qos=0, retain=True, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
  count = 0 # blink LED to confirm action
  while count < 5:
     GPIO.output(LED,GPIO.LOW)
     time.sleep(.1)
     GPIO.output(LED,GPIO.HIGH)
     time.sleep(.1)
     count += 1

  return;

def req_fountain_off():

  global  outputPinCheck

  GPIO.output(outputPin,GPIO.HIGH)
  outputPinCheck = 1  # set this flag so that status is not published again in def_readtimes
  publish.single("yo105ay/garden/pisolar/switch/1/status", payload="OFF", qos=0, retain=True, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
  count = 0 # blink LED to confirm action
  while count < 5:
     GPIO.output(LED,GPIO.HIGH)
     time.sleep(.1)
     GPIO.output(LED,GPIO.LOW)
     time.sleep(.1)
     count += 1

  return;


def readtimes():
  
  global BatteryWarning, ButtonPressed, LastFullCharge, outputPinCheck

 # skip routine if any of below flags are set
  if LastFullCharge > 7: # full charge needed
    return;
  if ButtonPressed == 1: # fountain already actived on timer
    return;
  if BatteryWarning == 1: # battery warning in place
    return;

  # open trigger times file and search each for a current time match
  flag = 0 # reset flag in for loop
  f = open('times.txt', 'r')
  for line in f:   # for each line in times.txt
    # load date strings to variabless
    string1,string2 = line.strip().split()
    # convert variables to datetime
    FMT = '%H:%M:%S'
    datetime1 = datetime.datetime.strptime(string1, FMT)
    datetime2 = datetime.datetime.strptime(string2, FMT)
    # combine time variable with todays date for later comparison with current datetime
    starttime = datetime.datetime.combine(datetime.datetime.now().date(), datetime1.time())
    stoptime = datetime.datetime.combine(datetime.datetime.now().date(), datetime2.time())
    # compare with current time and turn on fountain if within time settings
    if starttime <= datetime.datetime.now() <= stoptime:
      flag = 1 # set flag if any line in file has positive search

  f.close()

  # take action based on flag setting
  if flag == 0: # switch off fountain
    GPIO.output(outputPin,GPIO.HIGH)
    publish.single("yo105ay/garden/pisolar/switch/1/status", payload="OFF", qos=0, retain=True, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
  else:  # switch on fountain
    GPIO.output(outputPin,GPIO.LOW)
    publish.single("yo105ay/garden/pisolar/switch/1/status", payload="ON", qos=0, retain=True,hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})

  return;


# if button pressed on raspberry pi
def buttonpress(channel):

  global ButtonPressed, ButtonPressedTime, debouncetime, BatteryWarning, outputPinCheck

# de-bounce button press in case mltiple presses
  time_now = time.time()
  if (time_now - debouncetime) >= 0.3: # software debounce loop to ignore further callbacks within 0.3 seconds

# Ignore button press if there is a battery warning and flash warning message
    if BatteryWarning == 1: # skip over if there is a battery warning
      publish.single("yo105ay/homeassistant/alerts", payload="SolarPi: fountain switch denied - battery low", qos=0, retain=False, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
      count = 0 # blink LED
      while count < 3:
        GPIO.output(LED,GPIO.HIGH)
        time.sleep(.3)
        GPIO.output(LED,GPIO.LOW)
        time.sleep(.3)
        count += 1
        debouncetime = time.time()
      return;

# Toggle fountain status
    if GPIO.input(outputPin):
      ButtonPressed = 1
      ButtonPressedTime = datetime.datetime.now()
      GPIO.output(outputPin,GPIO.LOW)
      outputPinCheck = 0 # set this flag so that status is not published again in def_readtimes
      publish.single("yo105ay/garden/pisolar/switch/1/status", payload="ON", qos=0, retain=True, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
      count = 0 # blink LED to confirm action
      while count < 5:
         GPIO.output(LED,GPIO.LOW)
         time.sleep(.1)
         GPIO.output(LED,GPIO.HIGH)
         time.sleep(.1)
         count += 1
    else:
      ButtonPressed = 0
      GPIO.output(outputPin,GPIO.HIGH)
      outputPinCheck = 1  # set this flag so that status is not published again in def_readtimes
      publish.single("yo105ay/garden/pisolar/switch/1/status", payload="OFF", qos=0, retain=True, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
      count = 0 # blink LED to confirm action
      while count < 5:
         GPIO.output(LED,GPIO.HIGH)
         time.sleep(.1)
         GPIO.output(LED,GPIO.LOW)
         time.sleep(.1)
         count += 1

    debouncetime = time.time()

  return;


def checkother():
  
  global BatteryWarning, BatteryLevel, LastFullCharge, ButtonPressed, ButtonPressedTime, currentday, AccPower, AccPowerGen, outputPinCheck, publishedflag

# if button press trigeers fountain - set timer to 1 hr to switch back off
  if ButtonPressed == 1:
      if datetime.datetime.now() > (ButtonPressedTime + datetime.timedelta(seconds=3600)):
        GPIO.output(outputPin,GPIO.HIGH)
        outputPinCheck = 1
        GPIO.output(LED,GPIO.LOW)
        ButtonPressed = 0 #Clear buttonpressed flag when  timer expires so that sheddule may resume
        publish.single("yo105ay/garden/pisolar/switch/1/status", payload="OFF", qos=0, retain=True, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
 
# Check if new day rolled over and zero daily power counters
  if currentday < datetime.datetime.now().date():
    currentday = datetime.datetime.now().date()
    publish.single("yo105ay/garden/pisolar/PowerUsedDaily", payload=('{0:.3f}'.format(AccPower)), qos=0, retain=False, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
    publish.single("yo105ay/garden/pisolar/PowerGenDaily", payload=('{0:.3f}'.format(AccPowerGen)), qos=0, retain=False, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
    AccPower = 0
    AccPowerGen = 0
    LastFullCharge += 1

# if battery drops below 75% enable full charge 
  if BatteryLevel < float(75): # 75 percent level of battery
    LastFullCharge = 8

# if battery has not had full charge for more than 1 week enable full charge
  if LastFullCharge > 7 and  BatteryWarning == 0:
     if publishedflag != 7:
       publish.single("yo105ay/homeassistant/alerts", payload="SolarPi: Battery needs full recharge - schedule suspended", qos=0, retain=False, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
       publishedflag = 7

  return;

    
def temphum():
    # Note that sometimes you won't get a reading and
    # the results will be null (because Linux can't
    # guarantee the timing of calls to read the sensor).
    # If this happens try again!
    # Grab a temperature sensor reading.  Use the read_retry method which will retry up
    # to 15 times to get a sensor reading (waiting 2 seconds between each retry).  
    humidity, temperature = Adafruit_DHT.read_retry(dht22sensor, dht22pin)

    # Un-comment the line below to convert the temperature to Fahrenheit.
    # temperature = temperature * 9/5.0 + 32
 
    if humidity is not None and temperature is not None:
#       print('Temp={0:0.1f},Humidity={1:0.1f}'.format(temperature, humidity))
       publish.single("yo105ay/garden/pisolar/Battery_Temp", payload=('{0:.2f}'.format(temperature)), qos=0, retain=False, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
       publish.single("yo105ay/garden/pisolar/Battery_Humidity", payload=('{0:.2f}'.format(humidity)), qos=0, retain=False, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})

    else:
       print('Failed to get temperature and humidity reading')

    return;

  
def voltages():
#   declare global variables to access in this function
    global BatteryLevel, BatteryWatts, SolarPanelI, SolarPanelV, BatteryI, BatteryV, LoadI, LoadV, AccPower, AccPowerGen, CurrPower, GenPower, BatteryWarning, outputPinCheck, timeinteval, ProgRunTime 

#   Examples
#   print "Bus voltage: %.3f V" % INA219(0x40).getBusVoltage_V()
#   print "Shunt voltage: %.3f mV" % INA219(0x40).getShuntVoltage_mV()
#   print "Solar Panel Current: %.0f mA" % INA219(0x40).getCurrent_mA()

#   Grab reading 10 time over time interval and store average result
    SolarPanelI = 0
    SolarPanelV = 0
    BatteryI = 0
    BatteryV = 0
    LoadI = 0
    LoadV = 0
    count = 0
    while count < 10:
      SolarPanelI += (INA219(0x40).getCurrent_mA()*10)
      SolarPanelV += INA219(0x40).getBusVoltage_V() + (INA219(0x40).getShuntVoltage_mV() / 1000)
      BatteryI += ((INA219(0x41).getCurrent_mA()*10) + 30) # 30 adjustment for current calibration
      BatteryV += INA219(0x41).getBusVoltage_V() + (INA219(0x41).getShuntVoltage_mV() / 1000)
      LoadI += ((INA219(0x44).getCurrent_mA()*10) + 55) # 55 adjustment for raspberry pi current added
      LoadV += INA219(0x44).getBusVoltage_V() + (INA219(0x44).getShuntVoltage_mV() / 1000)
      count += 1
      time.sleep(timeinteval/10)

    SolarPanelI = float(SolarPanelI)/10/1000
    SolarPanelV = float(SolarPanelV)/10
    BatteryI = float(BatteryI)/10/1000
    BatteryV = float(BatteryV)/10
    LoadI = float(LoadI)/10/1000
    LoadV = float(LoadV)/10

    if BatteryI < 0: # Eradicate negative values from charge current. this is already shown in LoadI
      BatteryI = 0

#   Calculate current power consumption/generation readings
    CurrPower = (LoadV * LoadI)
    CurrPower = float(CurrPower)    

    GenPower = (BatteryV * BatteryI)
    GenPower = float(GenPower)

#   Calculate cumulative power used/generated over 24hr period and battery capacity

    # check precise number in seconds to cycle back to this point. More accurate calculation than using the timeinterval setting as program runtime is taken into account..
    T1 = time.time()-ProgRunTime
    # power calcs over time
    AccPower += (LoadV * LoadI) / (60/T1*60) 
    AccPower = float(AccPower)
    AccPowerGen += (BatteryV * BatteryI) / (60/T1*60)
    AccPowerGen = float(AccPowerGen)
    # Battery wattage over time
    BatteryWatts = (BatteryWatts - ((LoadV * LoadI) / (60/T1*60)))
    BatteryWatts = float(BatteryWatts)
    ProgRunTime = time.time()  

    # if battery wattage count is above battery rated maximum, then do not increment further
    if BatteryWatts > float(840): # check for battery level over 100%
      BatteryWatts = float(840)
    BatteryLevel = BatteryWatts/float(840)*float(100) # est. % batt level from current wattage count since full charge
    BatteryLevel = float(BatteryLevel)

#   Publish sensor readings
    publish.single("yo105ay/garden/pisolar/SolarPanelI", payload=('{0:.3f}'.format(SolarPanelI)), qos=0, retain=False, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
    publish.single("yo105ay/garden/pisolar/SolarPanelV", payload=('{0:.3f}'.format(SolarPanelV)), qos=0, retain=False, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
    publish.single("yo105ay/garden/pisolar/BatteryI", payload=('{0:.3f}'.format(BatteryI)), qos=0, retain=False, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
    publish.single("yo105ay/garden/pisolar/BatteryV", payload=('{0:.3f}'.format(BatteryV)), qos=0, retain=False, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
    publish.single("yo105ay/garden/pisolar/LoadI", payload=('{0:.3f}'.format(LoadI)), qos=0, retain=False, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
    publish.single("yo105ay/garden/pisolar/LoadV", payload=('{0:.3f}'.format(LoadV)), qos=0, retain=False, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
    publish.single("yo105ay/garden/pisolar/LoadPAcc", payload=('{0:.3f}'.format(AccPower)), qos=0, retain=False, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
    publish.single("yo105ay/garden/pisolar/GenPAcc", payload=('{0:.3f}'.format(AccPowerGen)), qos=0, retain=False, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
    publish.single("yo105ay/garden/pisolar/BattLevel", payload=('{0:.2f}'.format(BatteryLevel)), qos=0, retain=False, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
    publish.single("yo105ay/garden/pisolar/LoadP", payload=('{0:.3f}'.format(CurrPower)), qos=0, retain=False, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
    publish.single("yo105ay/garden/pisolar/GenP", payload=('{0:.3f}'.format(GenPower)), qos=0, retain=False, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})

#   uncomment to print readings to console
#    print "Volatge and current measurements"
#    print "Solar Panel Current = %.3f A" % SolarPanelI
#    print "Solar Panel Voltage = %.3f V" % SolarPanelV
#    print "Battery Current = %.3f A" % BatteryI
#    print "Battery Voltage = %.3f V" % BatteryV
#    print "Load Current = %.3f A" % LoadI
#    print "Load Voltage = %.3f V" % LoadV
#    print "Accumulated Power use = %.3f W" % AccPower
#    print "Accumulated Power Generated  = %.3f W" % AccPowerGen
#    print "Current Power use = %.3f W" % CurrPower
#    print "Current Power Generated =  %.3f W" % GenPower
#    print "Battery wattage estimate = %.3f " % BatteryWatts
#    print "Battery level estimate = %.3f " % BatteryLevel

    return;

def rules():

    global BatteryLevel, LastFullCharge, BatteryWatts, sparepower, SolarPanelI, SolarPanelV, BatteryI, BatteryV, LoadI, LoadV, AccPower, AccPowerGen, CurrPower, GenPower, BatteryWarning, outputPinCheck, timeinteval, publishedflag, ButtonPressed

# Defining some rules on what to do at key battery levels

#   Check battery drain below 11v and send critical warning, cut relays and turn off raspberry pi
    while  BatteryV < float(11):
        publish.single("yo105ay/homeassistant/alerts", payload=("SolarPi: Battery Critical (%.2f v) - Turning off fountain and shutting down" % BatteryV), qos=0, retain=False, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
        GPIO.output(outputPin,GPIO.HIGH)
        GPIO.output(LED,GPIO.LOW)
        publish.single("yo105ay/garden/pisolar/switch/1/status", payload="OFF", qos=0, retain=True, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
        GPIO.cleanup()
        subprocess.call(['poweroff'], shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return;

#   Check battery drain below 11.5v and send warning or cut power and turn off raspberry pi
    while BatteryV < float(11.5):
        GPIO.output(outputPin,GPIO.HIGH)
        GPIO.output(LED,GPIO.LOW)
        BatteryWarning = 1
        if publishedflag != 1:
          publish.single("yo105ay/homeassistant/alerts", payload=("SolarPi: Battery very low (%.2f v) - Turning off fountain" % BatteryV), qos=0, retain=False, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
          publish.single("yo105ay/garden/pisolar/switch/1/status", payload="OFF", qos=0, retain=True, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
          publishedflag = 1
        return;

#   Check battery if fully charged and calibrate battery watts count, whic calibrates battery level
    while (BatteryV > float(14.3) and BatteryI < float(0.8)):
        BatteryWarning = 0 # cancel battery warning to allow schedule to resume
        LastFullCharge = 0 # resetting the last full charge counter to allow schedule to resume
        BatteryWatts = 840 # re-calibrate the battery level to full-70AH /840 watts (100%)     
        if publishedflag != 2:
          publish.single("yo105ay/homeassistant/alerts", payload="SolarPi: Battery fully charged", qos=0, retain=False, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
          publishedflag = 2
        return;

    return;

# Main program -----------------------------------------------------------------------------------------------------$


# Setup interrupt to watch for event on gpio pin (button pressed)
GPIO.add_event_detect(buttonPin, GPIO.FALLING, callback=buttonpress, bouncetime=200)
# setup interrupt to detect program termination requests by outside process (e.g. supervisor)
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGUSR1, signal_handler)
signal.signal(signal.SIGUSR2, signal_handler)


#set up global variables needed in functions
debouncetime = time.time()
publishedflag = 0
BatteryWarning = 0
outputPinCheck = 1 #fountain pin initially set high
ButtonPressed = 0
ButtonPressedTime = datetime.datetime.now()
AccPower = 0 # the true power going in/out of the battery
AccPowerGen = 0 # the power generated by the solar panel, may be small negative when drawing power for internal charger cct.
timeinteval = 30
ProgRunTime = time.time()
currentday = datetime.datetime.now().date()
BatteryWatts = 0
BatteryLevel = 0
LastFullCharge = 3 # set halfway between recharges in case app needs to be re-started

try:
# load mqtt server credentials
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

# confirm application has started by publishing message. Reset switch to off.
  publish.single("yo105ay/homeassistant/alerts", payload="SolarPi: solarmonitor.py - Application started", qos=0, retain=False, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
  publish.single("yo105ay/garden/pisolar/switch/1/status", payload="OFF", qos=0, retain=True, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})

# Assess battery level under fountain load
  GPIO.output(LED,GPIO.LOW)
  time.sleep(5)
  BatteryV = INA219(0x41).getBusVoltage_V() + (INA219(0x41).getShuntVoltage_mV() / 1000)
  BatteryWatts = ((float(BatteryV)-float(10))/float(2.6))*float(840)
  BatteryLevel = BatteryWatts/float(840)*float(100) # est. % batt level from full charge wattage rating of battery (840w)
  BatteryLevel = float(BatteryLevel)
  publish.single("yo105ay/homeassistant/alerts", payload=("SolarPi: Battery level assesed as (%.2f %%)" % BatteryLevel), qos=0, retain=False, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
  GPIO.output(LED,GPIO.HIGH)

except socket.error:
  print "\nCould not find MQTT broker host at startup! - continuing program"
  pass

# run main program loop
while True:
  try:
    # Report temp and humidity readings
    # print "getting temps"
    temphum()
    # Report voltage, Current and power readings
    # print "getting voltages"
    voltages()
    # run through rules based on voltage and current readings
    # print "parsing rules"
    rules() 
    # check items which must not be skipped and checked every cycle
    # print "checking other"
    checkother()
    # read timetable
    # print "reading event timetable"
    # uncomment the line below to activate schedule. Currently disabled as now automated in homeassistant.
    # readtimes()    
       	
  except KeyboardInterrupt:
    GPIO.cleanup() # this ensures a clean exit
    print "\nGPIO Pins reset"
    sys.exit("\nKeyboard exit actioned")
  except socket.error:
    # perform ping test and report any failures
    ping_count = 0
    while ping_count < 5:
      while (subprocess.call(['ping -c 2 -w 1 -q 192.168.1.20 |grep "1 received" > /dev/null 2> /dev/null'], shell=True)) == 1:
        ping_count += 1
        if ping_count == 5:
          break
    if ping_count > 0 and ping_count < 5:
      publish.single("yo105ay/homeassistant/alerts", payload=("SolarPi: Pisolar network connection unreliable - ping failed multiple times"), qos=0, retain=False, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
    if ping_count > 4:#  break out of ping test if connection down
      print "\nMQTT server host not reachable! Ping failed %2.0f times. Will retry indefinately" % ping_count
      while (subprocess.call(['ping -c 2 -w 1 -q 192.168.1.20 |grep "1 received" > /dev/null 2> /dev/null'], shell=True)) == 1:
        time.sleep(5)
      print "\nMQTT server now avialable. Continuing program"
    pass
  except:
    GPIO.cleanup() # this ensures a clean exit
    print "\nGPIO Pins reset"
    f = open('tempvar.txt', 'w')
    f.write ("%.3f %.3f %.3f\n" % (AccPower,AccPowerGen,BatteryWatts))
    f.close()
    publish.single("yo105ay/garden/pisolar/switch/1/status", payload="OFF", qos=0, retain=True, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
    publish.single("yo105ay/homeassistant/alerts", payload="SolarPi: Solarmonitor.py reports other error or exception occurred!", qos=0, retain=False, hostname=MQTT_hostname, auth={'username':MQTT_username,'password':MQTT_password})
    sys.exit("\nSolarmonitor.py reports other error or exception occurred!")


