import json
import os
from datetime import datetime, timedelta

import pandas as pd
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


async def get_updates():
    latest_cur_current, latest_cur_power, latest_cur_voltage = get_real_time_update()
    return latest_cur_current, latest_cur_power, latest_cur_voltage


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

    if not response['success'] or not response['result']['logs']:
        print('....')
        with open('temp/log-data.json', 'r') as f:
            device_logs = json.loads(f.read())
    else:
        device_logs = response['result']['logs']

        if not len(device_logs) or len(device_logs) < 2:
            print('....')
            with open('temp/log-data.json', 'r') as f:
                device_logs = json.loads(f.read())
        else:
            print('getting results...')

    # Filter logs for 'cur_current' and 'cur_power' events
    cur_voltage_logs = [log for log in device_logs if log['code'] == 'cur_voltage']
    cur_current_logs = [log for log in device_logs if log['code'] == 'cur_current']
    cur_power_logs = [log for log in device_logs if log['code'] == 'cur_power']

    # Find the latest 'cur_current' and 'cur_power' values
    latest_cur_current = max(cur_current_logs, key=lambda x: x['event_time'])
    latest_cur_power = max(cur_power_logs, key=lambda x: x['event_time'])
    latest_cur_voltage = max(cur_voltage_logs, key=lambda x: x['event_time'])
    latest_cur_voltage['value'] = str(round(int(latest_cur_voltage['value']) / 10))

    return latest_cur_current, latest_cur_power, latest_cur_voltage


def get_device_info():
    response = openapi.get(f"/v1.0/devices/{DEVICE_ID}", params={"schema": True})

    if not response['success'] or not response['result']:
        print('....')
        with open('temp/device-info.json', 'r') as f:
            response = json.loads(f.read())

        return response['result']

    print('getting results...')
    return response['result']


def set_device_control(value):
    response = openapi.post(
        f"/v1.0/devices/{DEVICE_ID}/commands",
        body={
            "commands": [
                {
                    "code": "switch_1",
                    "value": value
                }
            ]
        }
    )

    return response


def calculate_total_cost(start_datetime, end_datetime):
    df = pd.read_csv('temp/device_log.csv', parse_dates=['TimeStamp'])
    df = df.sort_values(by='TimeStamp', ascending=True)

    filtered_df = df[(df['TimeStamp'] >= start_datetime) & (df['TimeStamp'] <= end_datetime)]
    total_cost = filtered_df['Cost per 1 Minute (BDT)'].sum()

    return total_cost
