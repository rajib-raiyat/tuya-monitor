import os
from datetime import datetime, timedelta

from dotenv import load_dotenv
from tuya_connector import TuyaOpenAPI

load_dotenv(".env")

DEVICE_ID = os.environ.get('DEVICE_ID')
API_VERSION = os.environ.get('API_VERSION')

openapi = TuyaOpenAPI(
    endpoint=os.environ.get('API_ENDPOINT'),
    access_id=os.environ.get('ACCESS_ID'),
    access_secret=os.environ.get('ACCESS_KEY')
)

openapi.connect()


# # Retrieve device status
# response1 = openapi.get(f"/v1.0/devices/{DEVICE_ID}/status", params={"schema": True})
# # print("Device Status:", response1)
#
# # Retrieve device details
# response2 = openapi.get(f"/v1.0/devices/{DEVICE_ID}", params={"schema": True})
# # print("Device Details:", response2)


async def get_updates():
    latest_cur_current, latest_cur_power = get_real_time_update()
    return latest_cur_current, latest_cur_power


def get_real_time_update():
    current_time = datetime.now()
    one_hour_ago = current_time - timedelta(minutes=10)
    end_time = round(one_hour_ago.timestamp() * 1000)

    response = openapi.get(
        path=f"/{API_VERSION}/devices/{DEVICE_ID}/logs",
        params={
            "start_time": end_time,
            "end_time": round(current_time.timestamp() * 1000),
            "type": '7',
            "size": "10"
        }
    )

    device_logs = response['result']['logs']

    # Filter logs for 'cur_current' and 'cur_power' events
    cur_current_logs = [log for log in device_logs if log['code'] == 'cur_current']
    cur_power_logs = [log for log in device_logs if log['code'] == 'cur_power']

    # Find the latest 'cur_current' and 'cur_power' values
    latest_cur_current = max(cur_current_logs, key=lambda x: x['event_time'])
    latest_cur_power = max(cur_power_logs, key=lambda x: x['event_time'])
    print('getting results...')
    return latest_cur_current, latest_cur_power
