# EDvoice_Fix v2.01
import os
import time
import glob
import json
import subprocess
import sys
import ctypes
import threading
import re
import datetime
import tkinter as tk
from tkinter import messagebox, scrolledtext

# --- НАСТРОЙКИ ---
EXE_NAME = "EDvoices.exe"
INI_NAME = "EDvoices.ini"
LOG_LIMIT = 5  # Сколько файлов журналов хранить в клон-папке
CONFIG_NAME = "EDFix_config.json"  # Для сохранения состояния галочек

# Белый список фракций (SystemAllegiance), которые EDvoices понимает корректно.
# Всё, что не входит сюда (Thargoid, None, новые фракции от разработчиков), заменится на ""
ALLEGIANCE_WHITELIST = {
    "Alliance",
    "Empire",
    "Federation",
    "Independent",
    "PilotsFederation",
    "Guardian"
}

# --- ЗАЩИТА ОТ ПОВТОРНОГО ЗАПУСКА (MUTEX) ---
MUTEX_NAME = "Global\\ED_Fixer_v2_SingleInstance_Mutex"
kernel32 = ctypes.windll.kernel32
mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
last_error = kernel32.GetLastError()

if last_error == 183:
    # Мьютекс уже открыт другой копией программы, завершаем этот процесс
    sys.exit(0)


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def get_paths():
    user_profile = os.environ.get("USERPROFILE", "")
    orig_dir = os.path.join(
        user_profile, "Saved Games", "Frontier Developments", "Elite Dangerous"
    )
    base_dir = os.path.dirname(
        os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__)
    )
    clone_dir = os.path.join(base_dir, "ED_Mirrored_Logs")
    return orig_dir, base_dir, clone_dir


def clean_old_clones(clone_dir, gui_log_func):
    """Удаляет старые файлы журналов, оставляя только свежие"""
    log_files = sorted(
        glob.glob(os.path.join(clone_dir, "Journal.*.log")), key=os.path.getmtime
    )
    if len(log_files) > LOG_LIMIT:
        files_to_delete = log_files[:-LOG_LIMIT]
        for f in files_to_delete:
            try:
                os.remove(f)
                gui_log_func(f"[Очистка] Удален старый клон: {os.path.basename(f)}")
            except:
                pass


def fix_fsd_jump_string(line):
    if '"event":"FSDJump"' not in line:
        return line
    try:
        data = json.loads(line)
        
        # Проверяем фракцию по белому списку
        allg = data.get("SystemAllegiance", "")
        if allg not in ALLEGIANCE_WHITELIST:
            allg = ""  # Если не в белом списке — сбрасываем в безопасную пустую строку
            
        # Извлекаем топливо с защитой типов
        fuel_used = data.get("FuelUsed", 0.0)
        fuel_level = data.get("FuelLevel", 0.0)
        
        try:
            fuel_used = float(fuel_used)
        except (ValueError, TypeError):
            fuel_used = 0.0
            
        try:
            fuel_level = float(fuel_level)
        except (ValueError, TypeError):
            fuel_level = 0.0

        timestamp = data.get("timestamp", "")
        if not timestamp:
            timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Собираем красивую укороченную строку строго С ПРОБЕЛАМИ, как просит EDvoices
        parts = [
            f'"timestamp":"{timestamp}"',
            f'"event":"FSDJump"',
            f'"SystemAllegiance":"{allg}"',
            f'"FuelUsed":{fuel_used:.6f}',
            f'"FuelLevel":{fuel_level:.6f}'
        ]
        
        return "{{ {0} }}\n".format(", ".join(parts))
    except Exception:
        # --- РЕЖИМ РЕВИЗОРА: ПРЕДОТВРАЩАЕМ ВЫЛЕТ, ЕСЛИ JSON БИТЫЙ ---
        # Вытаскиваем оригинальный timestamp регулярным выражением, чтобы не поломать хронологию
        time_match = re.search(r'"timestamp":"([^"]+)"', line)
        if time_match:
            backup_timestamp = time_match.group(1)
        else:
            backup_timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Формируем пустую, но 100% безопасную для EDvoices структуру
        fallback_parts = [
            f'"timestamp":"{backup_timestamp}"',
            f'"event":"FSDJump"',
            f'"SystemAllegiance":""',
            f'"FuelUsed":0.000000',
            f'"FuelLevel":0.000000'
        ]
        return "{{ {0} }}\n".format(", ".join(fallback_parts))


def setup_environment(orig_dir, base_dir, clone_dir, should_fix_ini, gui_log_func):
    if not os.path.exists(clone_dir):
        os.makedirs(clone_dir)

    targets = [
        "Status.json",
        "Market.json",
        "Shipyard.json",
        "Outfitting.json",
        "ModulesInfo.json",
    ]
    
    # Определяем буквы дисков для умного создания ссылок
    orig_drive = os.path.splitdrive(orig_dir)[0].lower()
    clone_drive = os.path.splitdrive(clone_dir)[0].lower()
    
    for t in targets:
        src = os.path.join(orig_dir, t)
        dst = os.path.join(clone_dir, t)
        if os.path.exists(src) and not os.path.exists(dst):
            if orig_drive == clone_drive:
                # Один и тот же диск -> Жесткая ссылка (Hardlink)
                subprocess.call(["cmd", "/c", "mklink", "/H", dst, src], shell=True)
            else:
                # Разные диски -> Символическая ссылка (Symlink)
                subprocess.call(["cmd", "/c", "mklink", dst, src], shell=True)

    # Проверка галочки правки INI
    if should_fix_ini:
        ini_path = os.path.join(base_dir, INI_NAME)
        if os.path.exists(ini_path):
            try:
                with open(ini_path, "r", encoding="cp1251", errors="ignore") as f:
                    lines = f.readlines()
                with open(ini_path, "w", encoding="cp1251", errors="replace") as f:
                    for line in lines:
                        if line.lower().startswith("setpath="):
                            f.write(f"SetPath={clone_dir}\n")
                        else:
                            f.write(line)
                gui_path_name = os.path.basename(ini_path)
                gui_log_func(
                    f"[Настройка] Путь в {gui_path_name} успешно проверен/исправлен."
                )
            except Exception as e:
                gui_log_func(f"[Ошибка] Не удалось перезаписать INI: {e}")
    else:
        gui_log_func(
            "[ИНФО] Проверка и правка пути в EDvoices.ini пропущена (отключено пользователем)."
        )


class SnifferGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("EDvoice_Fix_v2.01")
        self.root.geometry("550x440")
        self.root.configure(bg="#f0f0f0")

        self.orig_dir, self.base_dir, self.clone_dir = get_paths()

        # Переменные для галочек (с дефолтными значениями True)
        self.auto_start_var = tk.BooleanVar(value=True)
        self.fix_ini_var = tk.BooleanVar(value=True)

        self.load_config()  # Загружаем сохраненные настройки, если они есть

        self.create_widgets()

        if not is_admin():
            messagebox.showerror(
                "Ошибка прав",
                "Критическая ошибка: Запустите программу от имени АДМИНИСТРАТОРА!",
            )
            self.root.destroy()
            return

        self.stop_event = threading.Event()
        self.worker_thread = threading.Thread(target=self.bg_worker, daemon=True)
        self.worker_thread.start()

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_widgets(self):
        # --- ВЕРХНЯЯ ПАНЕЛЬ НАСТРОЕК ---
        settings_frame = tk.LabelFrame(
            self.root,
            text=" Настройки программы ",
            bg="#f0f0f0",
            font=("Arial", 9, "bold"),
        )
        settings_frame.pack(fill="x", padx=10, pady=5)

        # Первая галочка (Автозапуск EXE)
        self.chk_autostart = tk.Checkbutton(
            settings_frame,
            text=f"Автоматически запускать {EXE_NAME} при старте",
            variable=self.auto_start_var,
            command=self.save_config,
            bg="#f0f0f0",
            activebackground="#f0f0f0",
        )
        self.chk_autostart.pack(anchor="w", padx=10, pady=2)

        # Вторая галочка (Правка INI)
        self.chk_fixini = tk.Checkbutton(
            settings_frame,
            text=f"Проверять и исправлять пути в {INI_NAME} при старте",
            variable=self.fix_ini_var,
            command=self.save_config,
            bg="#f0f0f0",
            activebackground="#f0f0f0",
        )
        self.chk_fixini.pack(anchor="w", padx=10, pady=2)

        # --- ИНДИКАТОРЫ ТЕКУЩЕГО СОСТОЯНИЯ ---
        status_frame = tk.LabelFrame(
            self.root,
            text=" Статус и Индикация ",
            bg="#f0f0f0",
            font=("Arial", 9, "bold"),
        )
        status_frame.pack(fill="x", padx=10, pady=5)

        tk.Label(
            status_frame, text="Режим работы:", bg="#f0f0f0", font=("Arial", 9)
        ).grid(row=0, column=0, sticky="w", padx=10, pady=2)
        self.lbl_status = tk.Label(
            status_frame,
            text="Инициализация...",
            fg="blue",
            bg="#f0f0f0",
            font=("Arial", 9, "bold"),
        )
        self.lbl_status.grid(row=0, column=1, sticky="w", padx=5, pady=2)

        tk.Label(
            status_frame, text="Активный лог:", bg="#f0f0f0", font=("Arial", 9)
        ).grid(row=1, column=0, sticky="w", padx=10, pady=2)
        self.lbl_current_log = tk.Label(
            status_frame,
            text="Ожидание файла...",
            fg="#333333",
            bg="#f0f0f0",
            font=("Arial", 9, "italic"),
        )
        self.lbl_current_log.grid(row=1, column=1, sticky="w", padx=5, pady=2)

        # --- ОКНО КУДА ВЫВОДЯТСЯ ОШИБКИ И ЛОГИ (КОНСОЛЬ) ---
        log_frame = tk.LabelFrame(
            self.root,
            text=" Журнал событий | Blacview & Gemini AI ",
            bg="#f0f0f0",
            font=("Arial", 9, "bold"),
        )
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.log_area = scrolledtext.ScrolledText(
            log_frame,
            state="disabled",
            wrap="word",
            height=10,
            bg="#ffffff",
            fg="#000000",
            font=("Consolas", 9),
        )
        self.log_area.pack(fill="both", expand=True, padx=5, pady=5)

    def log_to_gui(self, message):
        def append():
            self.log_area.configure(state="normal")
            self.log_area.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {message}\n")
            self.log_area.see(tk.END)
            self.log_area.configure(state="disabled")

        self.root.after(0, append)

    def update_status_gui(self, status_text, color, log_file_name=None):
        def update():
            self.lbl_status.configure(text=status_text, fg=color)
            if log_file_name:
                self.lbl_current_log.configure(text=log_file_name)

        self.root.after(0, update)

    def load_config(self):
        """Загрузка состояний обоих чекбоксов из JSON"""
        config_path = os.path.join(self.base_dir, CONFIG_NAME)
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    data = json.load(f)
                    self.auto_start_var.set(data.get("auto_start", True))
                    self.fix_ini_var.set(data.get("fix_ini", True))
            except:
                pass

    def save_config(self):
        """Сохранение состояний обоих чекбоксов в JSON"""
        config_path = os.path.join(self.base_dir, CONFIG_NAME)
        try:
            with open(config_path, "w") as f:
                json.dump(
                    {
                        "auto_start": self.auto_start_var.get(),
                        "fix_ini": self.fix_ini_var.get(),
                    },
                    f,
                )
        except Exception as e:
            self.log_to_gui(
                f"[Ошибка конфигурации] Не удалось сохранить настройки: {e}"
            )

    def on_closing(self):
        self.stop_event.set()
        self.root.destroy()

    def bg_worker(self):
        """Параллельный поток, выполняющий всю работу алгоритма"""
        try:
            self.log_to_gui("Программа запущена. Blacview & Gemini AI")

            # Передаем состояние галочки в инициализацию окружения
            setup_environment(
                self.orig_dir,
                self.base_dir,
                self.clone_dir,
                self.fix_ini_var.get(),
                self.log_to_gui,
            )

            # Логика запуска EDvoices на основании галочки
            if self.auto_start_var.get():
                exe_path = os.path.join(self.base_dir, EXE_NAME)
                if os.path.exists(exe_path):
                    try:
                        tasks = subprocess.check_output(
                            f'tasklist /FI "IMAGENAME eq {EXE_NAME}"', shell=True
                        ).decode("cp866")
                        if EXE_NAME.lower() not in tasks.lower():
                            subprocess.Popen([exe_path], cwd=self.base_dir)
                            self.log_to_gui(f"[OK] {EXE_NAME} успешно запущен.")
                        else:
                            self.log_to_gui(f"[ИНФО] {EXE_NAME} уже запущен в системе.")
                    except Exception as e:
                        subprocess.Popen([exe_path], cwd=self.base_dir)
                        self.log_to_gui(
                            f"[ОК] {EXE_NAME} запущен (проверка процессов завершилась с ошибкой: {e})."
                        )
                else:
                    self.log_to_gui(
                        f"[ОШИБКА] Файл {EXE_NAME} не найден в папке скрипта."
                    )
            else:
                self.log_to_gui("[ИНФО] Автозапуск EDvoices отключен пользователем.")

            self.update_status_gui("Ожидание логов игры...", "#orange")

            last_glob_time = 0

            while not self.stop_event.is_set():
                all_logs = glob.glob(os.path.join(self.orig_dir, "Journal.*.log"))
                if not all_logs:
                    time.sleep(3)
                    continue

                current_log = max(all_logs, key=os.path.getmtime)
                clone_path = os.path.join(self.clone_dir, os.path.basename(current_log))

                clean_old_clones(self.clone_dir, self.log_to_gui)

                log_short_name = os.path.basename(current_log)
                self.update_status_gui("Активен (Слежение)", "green", log_short_name)
                self.log_to_gui(f"Начало отслеживания нового файла: {log_short_name}")

                try:
                    with (
                        open(current_log, "r", encoding="utf-8", errors="ignore") as src,
                        open(clone_path, "a", encoding="utf-8") as dst,
                    ):
                        is_clone_empty = os.path.getsize(clone_path) == 0

                        for line in src:
                            if is_clone_empty:
                                dst.write(fix_fsd_jump_string(line))

                        if is_clone_empty:
                            dst.flush()
                            os.fsync(dst.fileno())

                        while not self.stop_event.is_set():
                            line = src.readline()
                            if not line:
                                current_time = time.time()
                                if current_time - last_glob_time > 5.0:
                                    last_glob_time = current_time
                                    latest_log = max(
                                        glob.glob(
                                            os.path.join(self.orig_dir, "Journal.*.log")
                                        ),
                                        key=os.path.getmtime,
                                    )
                                    if latest_log != current_log:
                                        self.log_to_gui(
                                            "Обнаружен свежий файл лога. Переключаемся..."
                                        )
                                        time.sleep(0.5)  # Защита: даем ОС 500мс закрыть дескрипторы
                                        break
                                time.sleep(0.2)
                                continue

                            dst.write(fix_fsd_jump_string(line))
                            dst.flush()
                            os.fsync(dst.fileno())

                except Exception as e:
                    self.update_status_gui("Ошибка доступа!", "red")
                    self.log_to_gui(
                        f"[КРИТИЧЕСКАЯ ОШИБКА]: {e}. Повторная попытка через 2 сек..."
                    )
                    time.sleep(2)

        except Exception as global_err:
            self.update_status_gui("Крах потока!", "red")
            self.log_to_gui(f"[ОШИБКА ПОТОКА]: {global_err}")
            self.root.after(
                0,
                lambda: messagebox.showerror(
                    "Глобальная ошибка", f"Произошел системный сбой:\n{global_err}"
                ),
            )


if __name__ == "__main__":
    root = tk.Tk()
    app = SnifferGUI(root)
    root.mainloop()