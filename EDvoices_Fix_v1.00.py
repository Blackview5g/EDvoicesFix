import os
import time
import glob
import json
import subprocess
import sys
import ctypes

# --- НАСТРОЙКИ ---
EXE_NAME = "EDvoices.exe"
INI_NAME = "EDvoices.ini"
LOG_LIMIT = 5  # Сколько файлов журналов хранить в клон-папке

def is_admin():
    try: return ctypes.windll.shell32.IsUserAnAdmin()
    except: return False

def get_paths():
    user_profile = os.environ.get('USERPROFILE')
    orig_dir = os.path.join(user_profile, 'Saved Games', 'Frontier Developments', 'Elite Dangerous')
    base_dir = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
    clone_dir = os.path.join(base_dir, 'ED_Mirrored_Logs')
    return orig_dir, base_dir, clone_dir

def clean_old_clones(clone_dir):
    """Удаляет старые файлы журналов, оставляя только свежие"""
    log_files = sorted(glob.glob(os.path.join(clone_dir, 'Journal.*.log')), key=os.path.getmtime)
    if len(log_files) > LOG_LIMIT:
        files_to_delete = log_files[:-LOG_LIMIT]
        for f in files_to_delete:
            try:
                os.remove(f)
                print(f"[Очистка] Удален старый клон: {os.path.basename(f)}")
            except: pass

def fix_fsd_jump_string(line):
    if '"event":"FSDJump"' not in line:
        return line
    try:
        data = json.loads(line)
        allg = data.get("SystemAllegiance", "")
        if allg in ["Thargoid", "NONE", "none", " ", None]:
            allg = ""
        parts = [
            f'"timestamp":"{data.get("timestamp")}"',
            f'"event":"FSDJump"',
            f'"SystemAllegiance":"{allg}"',
            f'"FuelUsed":{data.get("FuelUsed", 0.0):.6f}',
            f'"FuelLevel":{data.get("FuelLevel", 0.0):.6f}'
        ]
        return '{{ {0} }}\n'.format(', '.join(parts))
    except:
        return line

def setup_environment(orig_dir, base_dir, clone_dir):
    if not os.path.exists(clone_dir):
        os.makedirs(clone_dir)
    
    # Ссылки на системные файлы
    targets = ['Status.json', 'Market.json', 'Shipyard.json', 'Outfitting.json', 'ModulesInfo.json']
    for t in targets:
        src = os.path.join(orig_dir, t)
        dst = os.path.join(clone_dir, t)
        if os.path.exists(src) and not os.path.exists(dst):
            subprocess.call(['cmd', '/c', 'mklink', '/H', dst, src], shell=True)

    # Правка INI
    ini_path = os.path.join(base_dir, INI_NAME)
    if os.path.exists(ini_path):
        try:
            with open(ini_path, 'r', encoding='cp1251', errors='ignore') as f:
                lines = f.readlines()
            with open(ini_path, 'w', encoding='cp1251') as f:
                for line in lines:
                    if line.lower().startswith('setpath='):
                        f.write(f'SetPath={clone_dir}\n')
                    else:
                        f.write(line)
        except: pass

def run_logic():
    orig_dir, base_dir, clone_dir = get_paths()
    print("===Программа запущенна. Blacview & Gemini AI===")
    
    if not is_admin():
        print("!!! ЗАПУСТИТЕ ОТ ИМЕНИ АДМИНИСТРАТОРА !!!")
        time.sleep(10)
        return

    setup_environment(orig_dir, base_dir, clone_dir)

    # Запуск программы озвучки (если еще не запущена)
    exe_path = os.path.join(base_dir, EXE_NAME)
    if os.path.exists(exe_path):
        # Проверяем, не запущен ли уже процесс, чтобы не плодить копии
        subprocess.Popen([exe_path], cwd=base_dir)
        print(f"[OK] {EXE_NAME} запущен.")

    print("--- Ожидание появления логов игры... ---")
    
    while True:
        all_logs = glob.glob(os.path.join(orig_dir, 'Journal.*.log'))
        if not all_logs:
            time.sleep(5)
            continue
            
        current_log = max(all_logs, key=os.path.getmtime)
        clone_path = os.path.join(clone_dir, os.path.basename(current_log))
        
        # Чистим старые клоны перед созданием нового
        clean_old_clones(clone_dir)

        print(f"[АКТИВНО] Слежу за: {os.path.basename(current_log)}")
        
        try:
            with open(current_log, 'r', encoding='utf-8', errors='ignore') as src, \
                 open(clone_path, 'a', encoding='utf-8') as dst:
                
                # Если клон новый, копируем в него текущее содержимое
                if os.path.getsize(clone_path) == 0:
                    for line in src:
                        dst.write(fix_fsd_jump_string(line))
                
                src.seek(0, os.SEEK_END)
                
                while True:
                    line = src.readline()
                    if not line:
                        # Проверка смены файла
                        if max(glob.glob(os.path.join(orig_dir, 'Journal.*.log')), key=os.path.getmtime) != current_log:
                            break
                        time.sleep(0.1)
                        continue
                    
                    dst.write(fix_fsd_jump_string(line))
                    dst.flush()
                    os.fsync(dst.fileno())
        except Exception as e:
            print(f"Ошибка доступа к файлу: {e}. Повтор...")
            time.sleep(2)

if __name__ == "__main__":
    try:
        run_logic()
    except KeyboardInterrupt:
        print("\nЗавершение работы...")
