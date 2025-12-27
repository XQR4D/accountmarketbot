import subprocess
import sys
import time
import threading
import os

BOT_SCRIPT = "main.py"
RESTART_FLAG = False

def terminal_input():
    global RESTART_FLAG
    while True:
        try:
            cmd = input().strip().lower()
            if cmd == "restart":
                print("\n[!] Команда restart из консоли. Перезапуск...")
                RESTART_FLAG = True
        except EOFError:
            break

threading.Thread(target=terminal_input, daemon=True).start()

while True:
    RESTART_FLAG = False
    print(f"[{time.strftime('%H:%M:%S')}] Запуск бота...")

    process = subprocess.Popen([sys.executable, BOT_SCRIPT])

    while True:
        if RESTART_FLAG:
            print("Перезапуск по команде из консоли...")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            break

        if process.poll() is not None:
            exit_code = process.returncode
            print(f"[{time.strftime('%H:%M:%S')}] Бот завершился с кодом {exit_code}. Перезапуск через 3 секунды...")
            time.sleep(3)
            break

        time.sleep(0.5)