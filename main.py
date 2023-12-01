import asyncio
import base64
import threading
from datetime import datetime
from io import BytesIO
from threading import Event

import matplotlib.pyplot as plt
import pandas as pd
from flask import Flask, render_template, redirect, url_for, request, jsonify
from flask_socketio import SocketIO

from device import get_updates, get_real_time_update, get_device_info, set_device_control, calculate_total_cost

app = Flask(__name__, static_url_path='/static')
socketio = SocketIO(app)

# Event object to signal the background task to stop
stop_event = Event()

df = pd.read_csv('temp/device_log.csv', parse_dates=['TimeStamp'])
df = df.sort_values(by='TimeStamp', ascending=True)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/home-page')
def homepage():
    return render_template('homepage.html')


@app.route('/device-info')
def device_info():
    info = get_device_info()

    return render_template(
        'device_info.html',
        device_info=info,
        human_readable_time=human_readable_time
    )


@app.route('/device-control', methods=['POST'])
def device_control():
    json_body = request.get_json()

    response = set_device_control(json_body['status'])
    return jsonify(response)


@app.route('/power-monitor')
def power_monitor():
    if not background_task_started():
        start_background_task()
    return render_template('power_monitor.html')


@app.route('/go-to-power-monitor', methods=['POST'])
def go_to_power_monitor():
    # Redirect to the power monitor page
    return redirect(url_for('power_monitor'))


def human_readable_time(timestamp):
    return datetime.fromtimestamp(timestamp).strftime('%d %b, %Y - %I:%M %p %A')


@socketio.on('connect')
def handle_connect():
    print('Client connected')
    device_data = get_real_time_update()
    if device_data:
        socketio.emit('logs', {'logs': device_data}, namespace='/')

    # Start the background task when a client connects
    start_background_task()


@app.route('/total-price', methods=['GET', 'POST'])
def total_price():
    if request.method == 'POST':
        start_datetime_str = request.form['start_datetime']
        end_datetime_str = request.form['end_datetime']

        # Convert input strings to datetime objects
        start_datetime = datetime.strptime(start_datetime_str, '%Y-%m-%dT%H:%M')
        end_datetime = datetime.strptime(end_datetime_str, '%Y-%m-%dT%H:%M')

        total_cost = calculate_total_cost(start_datetime, end_datetime)

        return render_template('total_price.html', start_datetime=start_datetime, end_datetime=end_datetime,
                               total_cost=total_cost)

    # Default date and time ranges
    default_start_date = df['TimeStamp'].min()
    default_end_date = df['TimeStamp'].max()

    return render_template('total_price_form.html', default_start_date=default_start_date,
                           default_end_date=default_end_date)


@app.route('/wattage-calculator', methods=['GET', 'POST'])
def wattage_calculator():
    timestamps = df['TimeStamp'].dt.strftime('%Y-%m-%dT%H:%M').unique()

    if request.method == 'POST':
        selected_timestamp = request.form.get('selected_timestamp')

        if selected_timestamp:
            selected_time = datetime.strptime(selected_timestamp, '%Y-%m-%dT%H:%M')
            selected_row = df.loc[df['TimeStamp'] == selected_time]

            if not selected_row.empty:
                wattage = selected_row['Power (W)'].values[0]
                return render_template('wattage_calculator.html', timestamp=selected_timestamp, wattage=wattage,
                                       timestamps=timestamps)

        return render_template('wattage_calculator.html', timestamp=None, wattage=None, timestamps=timestamps)

    return render_template('wattage_calculator.html', timestamp=None, wattage=None, timestamps=timestamps)


@app.route('/daily-energy-analysis')
def daily_energy_analysis():
    daily_energy_usage = df.groupby(df['TimeStamp'].dt.date)['kWh per 1 Minute'].sum()
    daily_operating_costs = df.groupby(df['TimeStamp'].dt.date)['Cost per 1 Minute (BDT)'].sum()

    # Plotting daily energy usage trend
    plt.figure(figsize=(10, 5))
    plt.subplot(2, 1, 1)
    daily_energy_usage.plot(kind='line', marker='o', color='green')
    plt.title('Daily Energy Usage Trend')
    plt.xlabel('Date')
    plt.ylabel('Energy Usage (kWh)')
    plt.xticks(rotation=45)
    plt.tight_layout()

    # Plotting daily operating costs trend
    plt.subplot(2, 1, 2)
    daily_operating_costs.plot(kind='line', marker='o', color='blue')
    plt.title('Daily Operating Costs Trend')
    plt.xlabel('Date')
    plt.ylabel('Operating Costs (BDT)')
    plt.xticks(rotation=45)
    plt.tight_layout()

    # Save plot to a BytesIO object
    img_data = BytesIO()
    plt.savefig(img_data, format='png')
    img_data.seek(0)

    # Encode the image to base64
    img_base64 = base64.b64encode(img_data.getvalue()).decode()

    plt.close()  # Close the plot to release resources

    return render_template('energy_analysis.html', img_base64=img_base64)


@socketio.on('disconnect')
def handle_disconnect():
    global stop_event
    print('Client disconnected')

    # Set the event to stop the background task
    stop_event.set()


def background_task_started():
    return not stop_event.is_set()


async def send_logs():
    while not stop_event.is_set():
        device_data = await get_updates()
        if device_data:
            socketio.emit('logs', {'logs': device_data}, namespace='/')
        await asyncio.sleep(10)


def start_background_task():
    # Reset the event before starting the background task
    global stop_event
    stop_event = Event()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Create a new Thread for the asyncio loop
    loop_thread = threading.Thread(target=loop.run_until_complete, args=(send_logs(),))
    loop_thread.daemon = True
    loop_thread.start()


if __name__ == '__main__':
    socketio.run(app, debug=True, use_reloader=False, allow_unsafe_werkzeug=True)
