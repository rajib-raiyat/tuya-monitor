import asyncio
import threading
from datetime import datetime
from threading import Event

import pandas as pd
import plotly.express as px
from flask import Flask, render_template, redirect, url_for, request, jsonify
from flask_socketio import SocketIO

from device import get_updates, get_real_time_update, get_device_info, set_device_control

app = Flask(__name__, static_url_path='/static')
socketio = SocketIO(app)

# Event object to signal the background task to stop
stop_event = Event()

df = pd.read_csv('temp/device_log.csv', parse_dates=['TimeStamp'])
df = df.sort_values(by='TimeStamp', ascending=True)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/dashboard')
def dashboard():
    info = get_device_info()

    return render_template('dashboard.html', device_info=info,
                           human_readable_time=human_readable_time)


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


@app.route('/total-price')
def total_price():
    # Calculate total cost for each day
    df['Date'] = df['TimeStamp'].dt.date
    daily_total_cost = df.groupby('Date')['Cost per 1 Minute (BDT)'].sum().reset_index()

    # Create line chart
    fig = px.line(daily_total_cost, x='Date', y='Cost per 1 Minute (BDT)', title='Total Price per Day')
    fig.update_xaxes(title_text='Date')
    fig.update_yaxes(title_text='Total Cost (BDT)')

    # Save the HTML code for the chart
    chart_html = fig.to_html(full_html=False)

    return render_template('total_price.html', chart_html=chart_html)


@app.route('/wattage-calculator')
def wattage_calculator():
    # Calculate total wattage for each day
    df['Date'] = df['TimeStamp'].dt.date
    daily_total_wattage = df.groupby('Date')['Power (W)'].sum().reset_index()

    # Create line chart
    fig = px.line(daily_total_wattage, x='Date', y='Power (W)', title='Daily Wattage')
    fig.update_xaxes(title_text='Date')
    fig.update_yaxes(title_text='Total Wattage (W)')

    # Save the HTML code for the chart
    chart_html = fig.to_html(full_html=False)

    return render_template('wattage_calculator.html', chart_html=chart_html)


@app.route('/daily-energy-analysis')
def daily_energy_analysis():
    daily_energy_usage = df.groupby(df['TimeStamp'].dt.date)['kWh per 1 Minute'].sum().reset_index()
    daily_operating_costs = df.groupby(df['TimeStamp'].dt.date)['Cost per 1 Minute (BDT)'].sum().reset_index()

    # Create line chart for daily energy usage
    fig1 = px.line(daily_energy_usage, x='TimeStamp', y='kWh per 1 Minute', title='Daily Energy Usage Trend',
                   labels={'kWh per 1 Minute': 'Energy Usage (kWh)'})
    fig1.update_xaxes(title_text='Date')
    fig1.update_yaxes(title_text='Energy Usage (kWh)')

    # Save the HTML code for the charts
    chart_html1 = fig1.to_html(full_html=False)

    return render_template('energy_analysis.html', chart_html1=chart_html1)


def human_readable_time(timestamp):
    return datetime.fromtimestamp(timestamp).strftime('%d %b, %Y - %I:%M %p %A')


@socketio.on('connect')
def handle_connect():
    print('Client connected')
    device_data = get_real_time_update(keep_log=False)
    if device_data:
        socketio.emit('logs', {'logs': device_data}, namespace='/')

    # Start the background task when a client connects
    start_background_task()


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
        await asyncio.sleep(60)


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
