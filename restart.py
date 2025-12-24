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
                print("\n[!] Получена команда из консоли. Перезапуск...")
                RESTART_FLAG = True
        except EOFError:
            break

# Запускаем поток чтения консоли
threading.Thread(target=terminal_input, daemon=True).start()

while True:
    RESTART_FLAG = False
    try:
        print(f"[{time.strftime('%H:%M:%S')}] Запуск бота...")
        
        # Запускаем процесс бота
        # Используем sys.executable для запуска через тот же интерпретатор Python
        process = subprocess.Popen([sys.executable, BOT_SCRIPT])
        
        while True:
            # Проверка 1: Бот завершился сам (os._exit из чата)
            if process.poll() is not None:
                print(f"[{time.strftime('%H:%M:%S')}] Бот завершил работу самостоятельно. Перезапуск...")
                break
                
            # Проверка 2: Команда 'restart' введена в консоль
            if RESTART_FLAG:
                process.terminate() # Мягко завершаем
                process.wait()      # Ждем выхода
                break
            
            time.sleep(1) # Не нагружаем процессор
            
    except Exception as e:
        print(f"Ошибка монитора: {e}. Рестарт через 5 секунд...")
        time.sleep(5)