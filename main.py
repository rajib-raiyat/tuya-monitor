import asyncio
import threading
from threading import Event

from flask import Flask, render_template, redirect, url_for
from flask_socketio import SocketIO

from device import get_updates, get_real_time_update

app = Flask(__name__, static_url_path='/static')
socketio = SocketIO(app)


# Event object to signal the background task to stop
stop_event = Event()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/power-monitor')
def power_monitor():
    # Check if the background task has been started, if not, start it
    if not background_task_started():
        start_background_task()
    return render_template('power_monitor.html')


@app.route('/go-to-power-monitor', methods=['POST'])
def go_to_power_monitor():
    # Redirect to the power monitor page
    return redirect(url_for('power_monitor'))


@socketio.on('connect')
def handle_connect():
    print('Client connected')
    device_data = get_real_time_update()
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
