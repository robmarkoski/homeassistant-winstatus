# winstatus.py 

A status link for Windows machines and Home Assistant via MQTT

**VERSION:** 0.1.0

- [winstatus.py](#winstatuspy)
  - [Installation](#installation)
  - [Configuration](#configuration)
    - [Setting Up The Python Script](#setting-up-the-python-script)
    - [HOME ASSISTANT CONFIGURATION](#home-assistant-configuration)
  - [EXAMPLES](#examples)
    - [Config File Examples](#config-file-examples)
    - [Sensor Template Memory Used](#sensor-template-memory-used)
    - [Sensor Template for Speedtest](#sensor-template-for-speedtest)
  - [Auto Run Script](#auto-run-script)
  - [Things that dont work.](#things-that-dont-work)
  - [Things I may add.](#things-i-may-add)

This is a small service that packages up the Windows machines data, packages it up via MQTT, and sends the payload to a HomeAssistant installation.

The server uses MQTT Discovery to set itself up, so the only real config you would need in HomeAssistant is using some Template sensors to extract more detailed data from the sensors attributes.

I did my best to make sure to stick with minimal external libraries.

The reason for making this is two fold. One I wanted to learn a bit more programming. Two i didn't find anything SIMPLE that does the same thing. I didn't want anything too bloaty. Just a basic script. Its not mission critical, so if it fails, its not end of the world.

**DISCLAIMER:** *I am a GSOCP (Google Stack Overflow Copy Paster). I code, I get suck, I google for solutions, end up on stack overflow, copy/paste and then repeat. 
So probably(definitely) doesn't use best practices/code is hacky/unreliable at best.
But hey it works sometimes... barely. Hopefully for all of us someone much smarter than me takes this script and makes it better.*

People to thank with this project.
 * Huge Thank you to Steve at [Steve's Internet Guide](http://www.steves-internet-guide.com). If you want to learn about MQTT. Checkout his site.
 * All the people on Stack Overflow. Seriously. Thank you strangers.

## Installation
To use this you will need
  * Python 3 (3.6 Tested Should work on later versions)
  * paho-mqtt Python Module (install with pip3 install paho-mqtt)
  * psutil python module (install with pip3 install psutil)
  * speedtestcli Python Module (if you want speedtests to be run)
  * Rename config.sample.yaml to config.yaml and edit the data.
  * run winstatus.py


## Configuration

### Setting Up The Python Script
Keeping with HomeAssistant configuation scheme, configuration of this script uses YAML


Check out config.yaml file and update as required.

| top level | sub level | comments| defaults |
|-----------|------------|----------|---- |
| general:  | -| General configuration (Required) | - |
|           |device_name: | (REQUIRED) (STRING) Name of device (will be used as suffix for sensors) | - |
|           |status_update: | (OPTIONAL) (INT) Number of scans in seconds | 5 Seconds|
| mqtt      | - |  MQTT Broker Settings         |  | - |
|           | user      | (OPTIONAL) (STRING) Username for MQTT Broker | |
|           | password  | (OPTIONAL) (STRING) Password for MQTT Broker| |
|           | host:     | (REQUIRED) (STRING) IP of Broker              ||
|           | port:     | (OPTIONAL) (INT) Port of MQTT Broker | 1883|
|           | discovery_prefix: | (OPTIONAL) (STRING) Discovery Prefix in Home Assistant | HomeAssistant|
|           | qos:      | (OPTIONAL) (INT) QOS Of MQTT Packets | 0 |
| logging:  | -         | Logger Settings   | |
|           | file_name | (OPTIONAL) (STRING) Filename of Log File |
|           | level     | (OPTIONAL) (STRING) Log Level (DEBUG, ERROR ETC) | |
|           | console   | (OPTIONAL) (STRING) Log Level if you want Console Logging ||
| speedtest:|     -      | Run SpeedTests (requires speedtestcli installed) ||
|           | update:   | (OPTIONAL) (INT) Seconds for updates. Dont hammer the servers | 300 |
|           | monitor: | (OPTIONAL) (LIST) 'download' or 'upload' or both. ping is default||
|   process_check: | -|  (OPTIONAL) (LIST) Put filenames you want to check are running. Case Sensitive ||
| disk_status: | -| (OPTIONAL) (LIST) List your drives you want to status check. Format "C:" ||

### HOME ASSISTANT CONFIGURATION
In Home Assistant you need to [setup mqtt discovery](https://www.home-assistant.io/docs/mqtt/discovery).

In your configuration add to your MQTT settings
```yaml
mqtt:
    discovery: true
    discovery_prefix: HomeAssistant
```
Make your discovery prefix match the one you set in config.yaml.

## EXAMPLES

### Config File Examples
Some examples for the configuration file.

Check out processes are running:
```yaml
process_check:
    - 'vlc.exe'
    - 'Code.exe'
```

Will create a sensor which has a state that provides the number of processes running from your list. With State Attributes that list your process states (either running or not running)

Check out Disk Status:
```yaml
disk_status:
    - "C:"
    - "D:"
```
Creates a sensor per drive. State will be percentage used of that drive. State Attributes will provide further info.

### Sensor Template Memory Used
Some template sensors that may be useful in Home Assistant.

```yaml
sensor:
  - platform: template 
    sensors:
      devicename_used_mem:
        friendly_name: "Devicename Memory Used"
        entity_id: sensor.devicename_memory
        unit_of_measurement: "GB"
        value_template: >-
          {% if states.sensor.devicename_memory.state != "unknown" %}
            {{ (state_attr('sensor.devicename_memory', 'used') / (1024**3)) | round(2) }}
          {% endif %}
```
Will create a sensor with memory used in GB.

### Sensor Template for Speedtest
Get the download speed from speedtest.
```yaml
sensor:
  - platform: template 
    sensors:
      devicename_speedtest_download:
        friendly_name: "devicename - Download"
        entity_id: sensor.devicename_speedtest
        unit_of_measurement: "MB/s"
        value_template: >-
          {% if states.sensor.devicename_speedtest != "unknown" %}
            {{ (state_attr('sensor.devicename_speedtest', 'download') / (1024**2)) | round(1) }}
          {% endif %}
```

## Auto Run Script

So autorunning scripts is not too difficult. You can put the script in the [startup folder](https://www.howtogeek.com/228467/how-to-make-a-program-run-at-startup-on-any-computer/), use [task scheduler](https://www.howtogeek.com/138159/how-to-enable-programs-and-custom-scripts-to-run-at-boot/) or what have you.

Having scripts restart on failure is more difficult.

I have created a script ("start_script.py") that may work.

Essentially change the script to pick your python interpreter. Then set that script to startup on logon.

Have a look anyway. Let me know if it works.

I will continue to look at better ways (create a windows service etc.) but anyway.

## Things that dont work.

* It doesn't look like the "Lock Status" is working. I wanted to be able to check whether PC is locked but it doesnt look like this is possible.

* Script not fully tested. So may break sometimes. (Probably Will)


## Things I may add.
* Add some Wifi metrics
* Add some bluetooth metrics.
* Add some battery sensors for laptops.
* See if I can get Windows Update status...
* Ability to send commands to windows pc. This may be too risky though.
* Add SSL for data. 