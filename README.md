# Solar-Monitor
This python code monitors a solar panel performance using INA219 Current sensors and DHT22 temp/hum sensor and post the data to an MQTT server.
It uses the INA219 sensor library @ https://github.com/scottjw/subfact_pi_ina219.
IT uses the DHT22 temperature sensor librbary from https://github.com/adafruit/Adafruit_Python_DHT
Also required is the MQTT client libarys @ https://pypi.org/project/paho-mqtt/
A seperate text file called 'mqtt_config' is required containing the hostname, username and password of the MQTT server on seperate lines.
