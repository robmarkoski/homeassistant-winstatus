"""
    HomeAssistant - Windows Device - Status Server
    This is script that runs on Windows PC and provides MQTT feedback to HomeAssistant
    
    Version: 0.1

    TODO:
        [ ] Clean up code in general.
        [ ] Maybe split get_data functions. 
        [ ] Fix locking/unlocking method, or just get rid of it. 
"""

__version__ = "0.1.0"

from ctypes import Structure, windll, c_uint, sizeof, byref
import yaml
import time
import datetime
import platform
import os
import json
import logging

import sys

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))


try:
    import paho.mqtt.client as mqtt
except ImportError as error:
    raise ImportError("Can't Import paho-mqtt. \n Install with \"pip3 install paho-mqtt\"\n {}".format(error))

try:
    import psutil
except ImportError as error:
    raise ImportError("Can't Import psutil. \n Install with \"pip3 install psutil\"\n {}".format(error))
 
# Try open log file.
try:
    ymlfile = open(SCRIPT_DIR + "\\config.yaml", 'r') 
except IOError:
    raise IOError("Error: Cant open config file")

with ymlfile:
    cfg = yaml.load(ymlfile)
RUNSPEEDTEST = False #Initialise
##############################################
######## SETUP LOGGER ########################
##############################################
LOG_FILE_NAME = cfg['logging']['file_name']
LOG_FILE = SCRIPT_DIR + "/" + LOG_FILE_NAME
LOG_LEVEL = cfg['logging'].get('level', "INFO")                      
LOG_LEVEL_NUM = getattr(logging, LOG_LEVEL.upper(), None)   # Set log level https://docs.python.org/3/howto/logging.html#logging-basic-tutorial
if not isinstance(LOG_LEVEL_NUM, int):
    raise ValueError("Invalid log level: %s" % LOG_LEVEL)
LOG_FORMAT = "%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s"

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logFormatter = logging.Formatter(LOG_FORMAT)
if cfg['logging'].get('filename'):
    fileHandler = logging.FileHandler(LOG_FILE)
    fileHandler.setLevel(LOG_LEVEL_NUM)
    fileHandler.setFormatter(logFormatter)
    logger.addHandler(fileHandler)

if cfg['logging'].get('console'):
    consoleHandler = logging.StreamHandler()
    consoleHandler.setLevel(getattr(logging, cfg['logging']['console'].upper(), None))
    consoleHandler.setFormatter(logFormatter)
    logger.addHandler(consoleHandler)

#####################################################
######## PARSE CONFIG FILE #########################
#####################################################
DEVICE_NAME = cfg['general']['device_name']
STATUS_UPDATE_TIME = cfg['general'].get('status_update', 5)
if cfg.get("speedtest") is not None:
    logger.debug("Speedtest will be done.")
    SPEEDTEST_INTERVAL = cfg['speedtest'].get('update', 300)
    SPEEDTEST_CONFIG = cfg['speedtest'].get('monitor')
    logger.debug("Speed Test will check: {}".format(SPEEDTEST_CONFIG))
    
    try:
        import speedtest
        RUNSPEEDTEST = True 
    except ImportError as error:
        RUNSPEEDTEST = False
        print("Can't Import speedtestcli. \n Install with \"pip3 install speedtestcli\"\n {}".format(error))
        pass

PROCESS_NAMES = cfg.get('process_check')
DRIVES = cfg.get('disk_status')
### CHECK DRIVES)
# Remove drives from drive list that dont exist.
DRIVES = [drive for drive in DRIVES if os.system("vol {} 2>nul>nul".format(drive)) == 0]
logger.debug("Removed drives that could not be found. Drives to be checked: {}".format(DRIVES))



######################################
######## MQTT ########################
######################################

MQTT_USER = cfg['mqtt']['user']             # MQTT USERNAME
MQTT_PASS = cfg['mqtt']['password']         # MQTT PASSWORD
MQTT_CLIENT_ID = "MQTT_" + DEVICE_NAME      # MQTT CLIENT ID
MQTT_HOST_IP = cfg['mqtt']['host']          # MQTT HOST
MQTT_PORT = cfg['mqtt'].get('port', 1883)   # MQTT PORT (DEFAULT 1883)
MQTT_DISCOVERY_PREFIX = cfg['mqtt']['discovery_prefix']
MQTT_QOS = cfg['mqtt'].get('qos', 0)
# PREP MQTT PREFIXES
MQTT_STATE_PREFIX = MQTT_DISCOVERY_PREFIX + "/sensor/" + DEVICE_NAME    # Prefix Topic
MQTT_STATE_TOPIC = MQTT_STATE_PREFIX + "/state"                         # Prefix State Topic
MQTT_CONFIG_TOPIC = MQTT_STATE_PREFIX + "_{}/config"                    # Prefix Config Topic

#################################################################
######## PREPARE CONFIG_PAYLOAD FOR SETUP #######################
#################################################################

CONFIG_PAYLOAD = {
    "computer_name": {
        "name": DEVICE_NAME + "_name",
        "state_topic": MQTT_STATE_TOPIC,
        "value_template": "{{ value_json.computer_name }}"
    },
    "lock": {
        "name": DEVICE_NAME + "_lock",
        "state_topic": MQTT_STATE_TOPIC,
        "value_template": "{{ value_json.lockstatus }}"
    },
    "idle": {
        "name": DEVICE_NAME + "_idle",
        "state_topic": MQTT_STATE_TOPIC,
        "icon": "mdi:timer",
        "value_template": "{{ value_json.timeidle }}",
        "unit_of_measurement": "seconds",
    },
    "cpu_percent": {
        "name": DEVICE_NAME + "_cpu",
        "state_topic": MQTT_STATE_TOPIC,
        "icon": "mdi:chip",
        "value_template": "{{ value_json.cpu_percent }}",
        "unit_of_measurement": "%"
    },
    "network": {
        "name": DEVICE_NAME + "_network",
        "state_topic": MQTT_STATE_TOPIC,
        "icon": "mdi:network",
        "value_template": "{{ value_json.speedtest.client.ip }}",
        "json_attributes_topic": MQTT_STATE_TOPIC,
        "json_attributes_template": "{{ value_json.network | tojson }}"
    },
    "memory_use": {
        "name": DEVICE_NAME + "_memory",
        "state_topic": MQTT_STATE_TOPIC,
        "icon": "mdi:memory",
        "value_template": "{{ value_json.memory_use.percent }}",
        "json_attributes_topic": MQTT_STATE_TOPIC,
        "json_attributes_template": "{{ value_json.memory_use | tojson }}",
        "unit_of_measurement": "%"
    },
    "boot_time": {
        "name": DEVICE_NAME + "_boot",
        "state_topic": MQTT_STATE_TOPIC,
        "icon": "mdi:av-timer",
        "value_template": "{{ value_json.boot_time.boot_iso }}",
        "json_attributes_topic": MQTT_STATE_TOPIC,
        "json_attributes_template": "{{ value_json.boot_time | tojson }}"
    },
    "win_version": {
        "name": DEVICE_NAME + "_winver",
        "state_topic": MQTT_STATE_TOPIC,
        "icon": "mdi:laptop-windows",
        "value_template": "{{ value_json.win_version.version }}",
        "json_attributes_topic": MQTT_STATE_TOPIC,
        "json_attributes_template": "{{ value_json.win_version | tojson }}"
    }
}

if PROCESS_NAMES:
    logger.debug("App running status will be checked.")
    CONFIG_PAYLOAD["apps_running"] = {
        "name": DEVICE_NAME + "_apps",
        "icon": "mdi:application",
        "state_topic": MQTT_STATE_TOPIC,
        "value_template": "{{ value_json.apps_running.app_count }}",
        "json_attributes_topic": MQTT_STATE_TOPIC,
        "json_attributes_template": "{{ value_json.apps_running | tojson }}"
    }   
if DRIVES:
    logger.debug("Disk usage will be checked.")
    for drive in DRIVES:
        drive_key = "disk_{}".format(drive[0])
        CONFIG_PAYLOAD[drive_key] = {
            "name": DEVICE_NAME + "_" + drive_key,
            "state_topic": MQTT_STATE_TOPIC,
            "icon": "mdi:harddisk",
            "value_template": "{{ value_json.disk_usage." + "{}".format(drive[0]) + ".percent }}",
            "json_attributes_topic": MQTT_STATE_TOPIC,
            "unit_of_measurement": "%",
            "json_attributes_template": "{{ value_json.disk_usage." + "{}".format(drive[0]) + " | tojson }}"
        }


if RUNSPEEDTEST:
    logger.debug("Speedtest will be performed.")
    CONFIG_PAYLOAD["speedtest"] = {
        "name": DEVICE_NAME + "_speedtest",
        "state_topic": MQTT_STATE_TOPIC,
        "icon": "mdi:pulse",
        "value_template": "{{ value_json.speedtest.ping }}",
        "json_attributes_topic": MQTT_STATE_TOPIC,
        "json_attributes_template": "{{ value_json.speedtest | tojson }}"
    }


logger.debug("CONFIG_PAYLOAD: {}".format(CONFIG_PAYLOAD))

##################################################################
######## PREPARE DATA COLLECTION FUNCTIONS #######################
##################################################################


def get_computerName():
    return platform.node()


def get_speedtest():
    # Run Speedtest
    #https://github.com/sivel/speedtest-cli/wiki
    st = speedtest.Speedtest()
    st.get_best_server
    if 'download' in SPEEDTEST_CONFIG:
        st.download(threads=1)
    if 'upload' in SPEEDTEST_CONFIG:
        st.upload(threads=1)
    return st.results.dict()


def get_idle_duration():
    """ Get Time Idle 
        http://stackoverflow.com/questions/911856/detecting-idle-time-in-python
        Time Idle
    """
    class LASTINPUTINFO(Structure):
        _fields_ = [
            ('cbSize', c_uint),
            ('dwTime', c_uint),
        ]
    lastInputInfo = LASTINPUTINFO()
    lastInputInfo.cbSize = sizeof(lastInputInfo)
    windll.user32.GetLastInputInfo(byref(lastInputInfo))
    millis = windll.kernel32.GetTickCount() - lastInputInfo.dwTime
    return int(millis / 1000.0)


def get_lock_status():
    """ Get Lock/Unlock Status
        https://stackoverflow.com/questions/34514644/in-python-3-how-can-i-tell-if-windows-is-locked
        
        Doesnt work all the time.
        Dont think there is a way to do this.
        Needs more work.
    """
    DESKTOP_SWITCHDESKTOP = 0x0100
    user32 = windll.User32
    
    OpenDesktop = user32.OpenDesktopW
    SwitchDesktop = user32.SwitchDesktop

    hDesktop = OpenDesktop(u"Default", 0, False, DESKTOP_SWITCHDESKTOP)
    LockStatus = SwitchDesktop(hDesktop)
    if LockStatus:
        result = "unlocked"
        logger.debug("Lock Status: Unlocked - {}".format(LockStatus))
    else:
        logger.debug("Lock Status: Locked - {}".format(LockStatus))
        result = "locked"
    return result


def get_cpu_use():
    """ Get CPU Use in Percentage (Float)
        returns float
    """
    return psutil.cpu_percent()


def get_disk_usage(drives):
    """ Gets Disk Usage for drives and returns as dict 
        Returns Dict with following keys:
            'total' - Total Size as int of Bytes
            'used' - Total Used as int of Bytes
            'free' - Total Free as int of bytes
            'percent' - Percentage used as float

    """
    drive_stats = dict()
    for drive in drives:
        drive_stats[drive[0]] = psutil.disk_usage(drive)._asdict()
    return drive_stats


def get_memory_use():
    """ Gets Memory Use.
        returns Dict with following keys:
            'total' - Total Memory as in of bytes
            'available' - Available Memory as in of bytes
            'percent' - Used percentage as float
            'used' - Memory used as int of bytes
            'free' - Memory Free as int of bytes
    """
    return dict(psutil.virtual_memory()._asdict())


def get_network_status():
    """ Gets Memory Use.
        returns Dict with following keys:
            bytes_sent: number of bytes sent
            bytes_recv: number of bytes received
            packets_sent: number of packets sent
            packets_recv: number of packets received
            errin: total number of errors while receiving
            errout: total number of errors while sending
            dropin: total number of incoming packets which were dropped
            dropout: total number of outgoing packets which were dropped (always 0 on macOS and BSD)

    """
    return dict(psutil.net_io_counters()._asdict())


def get_boot_time():
    ''' Get Time of Last Boot
        Returns time since last boot as string.
    '''
    boot_time = psutil.boot_time()
    dt_iso = datetime.datetime.utcfromtimestamp(boot_time).isoformat()
    dt_format = datetime.datetime.now() - datetime.datetime.fromtimestamp(boot_time)
    result = {
        "boot_iso": dt_iso,
        "boot_format": str(dt_format).split('.')[0]
    }
    return result


def get_win_version():
    """ Get Windows Version Info
        Returns a dict with following values
            release - Windows Release 
            version - WIndows Version
            servicepack - Windows Service Pack Installed
            pytpe - Process type
    """
    result = {}
    result["release"], result["version"], result["servicepack"], result["ptype"] = platform.win32_ver()
    return result


def get_app_running_status(processes):
    """ Get Status of Whether Process is Running
        https://stackoverflow.com/questions/24136733/find-if-process-is-running-in-windows-psutil
        Returns:
            Dict of running apps, their names status, and total number running.
        TODO:
            Error check needs more work. 
    """
    running_status = dict.fromkeys(processes, "not_running")
    for proc in psutil.process_iter(): 
        try: 
            process = psutil.Process(proc.pid) # Get the process info using PID
        except:
            logger.error("PSUTIL Error")
            continue
        try:
            pname = process.name() # Here is the process name
        except psutil.NoSuchProcess:
            logger.error("PSUTIL No Such Process")
            continue
        if pname in processes:
            running_status[pname] = "running"

    running_status['app_count'] = sum(value == "running" for value in running_status.values())
    return running_status


##################################################################
######## HELPER FUNCTIONS ########################################
##################################################################

def publishConfig(payload_dict):
    for payload in payload_dict:
        config_payload_json = json.dumps(CONFIG_PAYLOAD[payload])
        topic = MQTT_CONFIG_TOPIC.format(payload)
        logger.info("MQTT Publishing Config Payload")
        logger.debug("MQTT State Topic: {}".format(topic))
        logger.debug("MQTT Config Payload: {}".format(config_payload_json))
        client.publish(topic, config_payload_json, qos=0, retain=True) # Set QOS 2 on this as you want to make sure its received


def on_publish(client, userdata, mid):
    logger.debug("MQTT Message Published")


def on_disconnect(client, userdata, rc):
    logger.info("MQTT Disconnecting Client")
    client.connected_flag = False 


def on_connect(client, userdata, flags, rc):
    logger.debug("MQTT Connection Status Returned: %s" % rc)
    if rc == 0:
        client.connected_flag = True
        logger.info("MQTT Connected to Broker")
    elif rc == 1:
        client.bad_connection_flag = True
        logger.error("MQTT Connection Refused: Bad Protocol")
    elif rc == 2:
        client.bad_connection_flag = True
        logger.error("MQTT Connection Refused: Client ID Error")
    elif rc == 3:
        client.bad_connection_flag = True
        logger.error("MQTT Connection Refused: Service Unavailable")
    elif rc == 4:
        client.bad_connection_flag = True
        logger.error("MQTT Connection Refused: Bad username or password")
    elif rc == 5:
        client.bad_connection_flag = True
        logger.error("MQTT Connection Refused: Not Authorized")
    else:
        client.bad_connection_flag = True
        logger.error("MQTT Bad Connection. Returned Code={}".format(rc))


def connect_MQTT():
    # Create MQTT Connection
    client = mqtt.Client(MQTT_CLIENT_ID) #create new instance
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_publish = on_publish
    if (MQTT_USER) and (MQTT_PASS):
        client.username_pw_set(username=MQTT_USER, password=MQTT_PASS)
    client.loop_start()
    logger.info("MQTT Connecting to Broker: {}".format(MQTT_HOST_IP))
    client.connect(MQTT_HOST_IP, port=MQTT_PORT)
    while not client.connected_flag and not client.bad_connection_flag:
        logger.info("MQTT Waiting for Connection Acknowledgement")
        time.sleep(1)
    if client.bad_connection_flag:
        client.loop_stop()
        sys.exit()
    client.loop_stop()
    return client


mqtt.Client.connected_flag = False
mqtt.Client.bad_connection_flag = False

client = connect_MQTT()

logger.info("MQTT Starting Payload Sending")
client.loop_forever()

publishConfig(CONFIG_PAYLOAD)

################################################################################
######## PREPARE STATUS UPDATE PAYLOAD #########################################
################################################################################

payload = dict()
payload.update(
    {
        "computer_name": get_computerName()
    }
)

if RUNSPEEDTEST:
    # Get Initial Speedtest
    speedtest_scan = SPEEDTEST_INTERVAL
    payload.update({
        "speedtest": get_speedtest()
    })

try: 
    while True:
        if client.connected_flag is False:
            logger.info("Client not connected. Exiting Script")
            sys.exit(0)

        payload.update({
            "lockstatus": get_lock_status(),
            "timeidle": get_idle_duration(),
            "cpu_percent": get_cpu_use(),
            "memory_use": get_memory_use(),
            "network": get_network_status(),
            "boot_time": get_boot_time(),
            "win_version": get_win_version(),
            "apps_running": get_app_running_status(PROCESS_NAMES)
        })
        if DRIVES:
            # Only update if there are drives to check!
            payload.update({"disk_usage": get_disk_usage(DRIVES)})
        if PROCESS_NAMES:
            # Only update if their are apps to check.
            payload.update({"apps_running": get_app_running_status(PROCESS_NAMES)})

        if RUNSPEEDTEST:
            if speedtest_scan ==0:
                # There has to be a better way to do this.
                payload.update({"speedtest": get_speedtest()})
                speedtest_scan = SPEEDTEST_INTERVAL
            else:
                speedtest_scan = speedtest_scan - STATUS_UPDATE_TIME

        logger.debug("State Payload: {}".format(payload))
        logger.debug("State Topic: {}".format(MQTT_STATE_TOPIC))
        payload_json = json.dumps(payload)
        client.publish(MQTT_STATE_TOPIC, payload_json, qos=MQTT_QOS, retain=True)
        time.sleep(STATUS_UPDATE_TIME)
except KeyboardInterrupt:
    print("Keyboard Interrupt")
    logger.info("Keyboard Interrupt!")
    client.loop_stop()
