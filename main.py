import asyncio
import threading
from threading import Thread

from flask import Flask, render_template
from flask_socketio import SocketIO

from device import get_updates, get_real_time_update

app = Flask(__name__)
socketio = SocketIO(app)


@app.route('/')
def index():
    return render_template('index.html')


@socketio.on('connect')
def handle_connect():
    print('Client connected')
    device_data = get_real_time_update()
    if device_data:
        socketio.emit('logs', {'logs': device_data}, namespace='/')

    send_logs_thread = Thread(target=send_logs)
    send_logs_thread.daemon = True
    send_logs_thread.start()


async def send_logs():
    while True:
        device_data = await get_updates()
        if device_data:
            socketio.emit('logs', {'logs': device_data}, namespace='/')
        await asyncio.sleep(10)


def start_background_task():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Create a new Thread for the asyncio loop
    loop_thread = threading.Thread(target=loop.run_until_complete, args=(send_logs(),))
    loop_thread.daemon = True
    loop_thread.start()


if __name__ == '__main__':
    threading.Thread(target=start_background_task, daemon=True).start()
    socketio.run(app, debug=True, use_reloader=False, allow_unsafe_werkzeug=True)
