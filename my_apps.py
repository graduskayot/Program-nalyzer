import sys
try:
    sys.stdin = open('CONIN$', 'r')
except Exception:
    pass
import flet as ft
import winreg
import os
import re
import subprocess
import requests
import json
import threading

# ==========================================
# ЛОГИКА ПОИСКА ПРОГРАММ
# ==========================================
def get_steam_games():
    steam_paths = []
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            steam_paths.append(winreg.QueryValueEx(key, "SteamPath")[0])
    except FileNotFoundError:
        pass

    library_folders = []
    for s_path in steam_paths:
        vdf_path = os.path.join(s_path, "steamapps", "libraryfolders.vdf")
        if os.path.exists(vdf_path):
            with open(vdf_path, "r", encoding="utf-8") as f:
                content = f.read()
                paths = re.findall(r'"path"\s+"\s*([^"]+)"', content)
                for p in paths:
                    library_folders.append(p.replace("\\\\", "\\"))
                    
    for s_path in steam_paths:
        if s_path not in library_folders:
            library_folders.append(s_path)

    return library_folders

def find_steam_game(game_name, steam_libraries):
    clean_game_name = game_name.lower().replace(" ", "")
    for lib in steam_libraries:
        common_path = os.path.join(lib, "steamapps", "common")
        if os.path.exists(common_path):
            for folder in os.listdir(common_path):
                clean_folder = folder.lower().replace(" ", "")
                if clean_game_name in clean_folder or clean_folder in clean_game_name:
                    return os.path.join(common_path, folder)
    return "Путь не найден (Steam)"

def get_installed_apps():
    apps = []
    registry_paths = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall")
    ]
    steam_libraries = get_steam_games()

    for hkey, path in registry_paths:
        try:
            with winreg.OpenKey(hkey, path) as key:
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        with winreg.OpenKey(key, subkey_name) as subkey:
                            try:
                                name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                                if "Update for" in name or "Security Update" in name:
                                    continue
                                
                                uninstall_cmd = ""
                                try:
                                    uninstall_cmd = winreg.QueryValueEx(subkey, "UninstallString")[0]
                                except FileNotFoundError:
                                    pass

                                if "steam://uninstall" in uninstall_cmd:
                                    install_path = find_steam_game(name, steam_libraries)
                                else:
                                    clean_path = re.sub(r'"?[^"\\]*\.exe"?.*$', '', uninstall_cmd, flags=re.IGNORECASE).strip('" ')
                                    install_path = clean_path if os.path.exists(clean_path) else "Путь не найден"
                                
                                # ← ФИЛЬТРАЦИЯ: пропускаем программы без пути
                                if "Путь не найден" in install_path:
                                    continue
                                
                                apps.append({
                                    "name": name,
                                    "path": install_path,
                                    "uninstall_cmd": uninstall_cmd,
                                    "size": None
                                })
                            except FileNotFoundError:
                                pass
                    except OSError:
                        pass
        except FileNotFoundError:
            pass
    return sorted(apps, key=lambda x: x["name"].lower())

# ==========================================
# ФУНКЦИИ ДЛЯ РАЗМЕРА
# ==========================================
def get_folder_size(path):
    total_size = 0
    try:
        if os.path.exists(path) and os.path.isdir(path):
            for dirpath, dirnames, filenames in os.walk(path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    if not os.path.islink(fp):
                        total_size += os.path.getsize(fp)
    except Exception:
        pass
    return total_size

def format_size(bytes_size):
    if bytes_size == 0: return "0 Б"
    for unit in ['Б', 'КБ', 'МБ', 'ГБ', 'ТБ']:
        if bytes_size < 1024.0: return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} ПБ"

# --- БЛОК АВТООБНОВЛЕНИЯ ---
CURRENT_VERSION = "0.1.4"
VERSION_URL = "https://raw.githubusercontent.com/graduskayot/Program-nalyzer/refs/heads/main/version.json"

def check_update(page):
    try:
        response = requests.get(VERSION_URL, timeout=5)
        data = response.json()
        latest = data["latest_version"]
        if latest != CURRENT_VERSION:
            dlg = ft.AlertDialog(
                modal=True,
                title=ft.Text("🚨 Доступно обновление"),
                content=ft.Text(f"Вышла новая версия {latest}. Программа не будет работать, пока вы не обновитесь."),
                actions=[ft.TextButton("Скачать обновление и закрыть", on_click=lambda e: os.startfile(data["download_url"]) or sys.exit())],
            )
            page.dialog = dlg
            dlg.open = True
            page.update()
            return False
    except Exception:
        pass
    return True

# ==========================================
# ИНТЕРФЕЙС НА FLET
# ==========================================
def main(page: ft.Page):
    page.title = "Анализатор приложений by Gradus"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 20

    # 1. ЭКРАН ЗАГРУЗКИ
    loading_view = ft.View(
        "/",
        [
            ft.Column(
                [
                    ft.ProgressRing(width=50, height=50, stroke_width=4),
                    ft.Text("Сканирую установленные программы...", size=20, weight=ft.FontWeight.BOLD),
                    ft.Text("Это может занять несколько секунд", color=ft.Colors.GREY_500),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=20,
            )
        ],
        vertical_alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )
    page.views.append(loading_view)
    page.update()

    # 2. ПРОВЕРКА ОБНОВЛЕНИЙ
    if not check_update(page):
        return

    # --- Language settings ---
    settings_path = os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), "AnalyserApps", "settings.json")
    os.makedirs(os.path.dirname(settings_path), exist_ok=True)
    try:
        with open(settings_path, "r", encoding="utf-8") as settings_file:
            settings = json.load(settings_file)
    except (OSError, ValueError):
        settings = {"language": "ru"}
    current_language = settings.get("language", "ru")

    translations = {
        "ru": {
            "title": "Список установленных программ", "search": "🔍 Поиск по названию...",
            "scan": "🔄 Сканировать заново", "settings": "⚙️ Настройки", "language": "Язык",
            "settings_title": "Настройки", "save": "Сохранить", "cancel": "Отмена",
            "open": "📂 Открыть", "run": "▶️ Запустить", "delete": "🗑 Удалить",
            "folder_missing": "Папка не найдена: {path}", "exe_missing": "Не найден .exe для запуска.",
            "launch_error": "Ошибка запуска: {error}", "uninstall_missing": "Команда удаления не найдена.",
            "uninstall_error": "Ошибка удаления: {error}", "size_calc": "⏳ Считаю...",
        },
        "en": {
            "title": "Installed applications", "search": "🔍 Search by name...",
            "scan": "🔄 Scan again", "settings": "⚙️ Settings", "language": "Language",
            "settings_title": "Settings", "save": "Save", "cancel": "Cancel",
            "open": "📂 Open", "run": "▶️ Launch", "delete": "🗑 Uninstall",
            "folder_missing": "Folder not found: {path}", "exe_missing": "No .exe file found.",
            "launch_error": "Launch error: {error}", "uninstall_missing": "Uninstall command not found.",
            "uninstall_error": "Uninstall error: {error}", "size_calc": "⏳ Calculating...",
        },
    }

    def tr(key, **kwargs):
        return translations.get(current_language, translations["ru"]).get(key, key).format(**kwargs)

    def refresh_texts():
        title.value = tr("title")
        search_field.hint_text = tr("search")
        scan_button.text = tr("scan")
        settings_button.text = tr("settings")
        page.update()

    def save_language(language):
        nonlocal current_language
        current_language = language
        settings["language"] = language
        try:
            with open(settings_path, "w", encoding="utf-8") as settings_file:
                json.dump(settings, settings_file, ensure_ascii=False, indent=2)
        except OSError:
            pass
        
        refresh_texts()
        update_list(search_field.value or "", recalc_sizes=False)

    all_apps = []
    list_view = ft.ListView(expand=True, spacing=5, padding=10)

    def update_list(filter_text="", recalc_sizes=True):
        list_view.controls.clear()
        search_lower = (filter_text or "").lower()

        for app in all_apps:
            if search_lower in app['name'].lower():
                if recalc_sizes:
                    size_text = ft.Text(tr("size_calc"), color=ft.Colors.GREY_500, size=12)
                else:
                    size_text = ft.Text(app.get('size', ""), color=ft.Colors.GREY_500, size=12)
                
                row = ft.Row(
                    controls=[
                        ft.Column(
                            [
                                ft.Text(app['name'], weight=ft.FontWeight.BOLD, size=14),
                                ft.Text(app['path'], color=ft.Colors.GREY_500, size=10),
                            ],
                            expand=True,
                            spacing=2,
                        ),
                        ft.Row(
                            [
                                ft.ElevatedButton(
                                    tr("open"),
                                    on_click=lambda e, p=app['path']: open_folder(p),
                                    style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_700, color=ft.Colors.WHITE),
                                ),
                                ft.ElevatedButton(
                                    tr("run"),
                                    on_click=lambda e, a=app: run_app(a),
                                    style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_700, color=ft.Colors.WHITE),
                                ),
                                ft.ElevatedButton(
                                    tr("delete"),
                                    on_click=lambda e, a=app: uninstall_app(a),
                                    style=ft.ButtonStyle(bgcolor=ft.Colors.RED_700, color=ft.Colors.WHITE),
                                ),
                                size_text,
                            ],
                            spacing=5,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )

                list_view.controls.append(
                    ft.Container(
                        content=row,
                        padding=10,
                        bgcolor="#2b2b2b",
                        border_radius=8,
                    )
                )

                if recalc_sizes:
                    def calc_size(path, txt_ctrl, app_ref):
                        s = get_folder_size(path)
                        formatted = f"📦 {format_size(s)}"
                        app_ref['size'] = formatted
                        txt_ctrl.value = formatted
                        page.update()
                    threading.Thread(target=calc_size, args=(app['path'], size_text, app), daemon=True).start()

        page.update()

    def open_folder(path):
        if os.path.exists(path) and os.path.isdir(path):
            os.startfile(path)
        else:
            page.snack_bar = ft.SnackBar(ft.Text(tr("folder_missing", path=path)))
            page.snack_bar.open = True
            page.update()

    def run_app(app):
        path = app['path']
        if os.path.exists(path) and os.path.isdir(path):
            exe_files = [f for f in os.listdir(path) if f.lower().endswith('.exe')]
            valid_exe = [f for f in exe_files if not any(x in f.lower() for x in ['unins', 'setup', 'update', 'install'])]
            if valid_exe:
                try:
                    os.startfile(os.path.join(path, valid_exe[0]))
                except Exception as e:
                    page.snack_bar = ft.SnackBar(ft.Text(tr("launch_error", error=e)))
                    page.snack_bar.open = True
                    page.update()
            else:
                page.snack_bar = ft.SnackBar(ft.Text(tr("exe_missing")))
                page.snack_bar.open = True
                page.update()
        else:
            page.snack_bar = ft.SnackBar(ft.Text(tr("folder_missing", path="")))
            page.snack_bar.open = True
            page.update()

    def uninstall_app(app):
        cmd = app['uninstall_cmd']
        if not cmd:
            page.snack_bar = ft.SnackBar(ft.Text(tr("uninstall_missing")))
            page.snack_bar.open = True
            page.update()
            return
        try:
            subprocess.Popen(cmd, shell=True)
        except Exception as e:
            page.snack_bar = ft.SnackBar(ft.Text(tr("uninstall_error", error=e)))
            page.snack_bar.open = True
            page.update()

    def scan_apps(e=None):
        nonlocal all_apps
        all_apps = get_installed_apps()
        for app in all_apps:
            app['size'] = None
        update_list(search_field.value, recalc_sizes=True)

    def on_search_change(e):
        update_list(e.control.value, recalc_sizes=False)

    title = ft.Text(tr("title"), size=24, weight=ft.FontWeight.BOLD)
    search_field = ft.TextField(hint_text=tr("search"), width=400, on_change=on_search_change, border_radius=20)
    scan_button = ft.ElevatedButton(tr("scan"), on_click=scan_apps, style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_700, color=ft.Colors.WHITE))
    settings_button = ft.ElevatedButton(tr("settings"), on_click=lambda e: open_settings(), style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_700, color=ft.Colors.WHITE))

    def open_settings():
        language_dropdown = ft.Dropdown(
            label=tr("language"),
            value=current_language,
            options=[ft.dropdown.Option("ru", "Русский"), ft.dropdown.Option("en", "English")],
            width=250,
        )

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(tr("settings_title")),
            content=language_dropdown,
            actions=[
                ft.TextButton(tr("cancel"), on_click=lambda e: close_dialog()),
                ft.TextButton(
                    tr("save"),
                    on_click=lambda e: save_and_close(language_dropdown.value),
                ),
            ],
        )

        def close_dialog():
            page.close(dialog)

        def save_and_close(language):
            save_language(language)
            close_dialog()

        page.open(dialog)

    # 3. ПЕРЕКЛЮЧЕНИЕ ЭКРАНОВ
    all_apps = get_installed_apps()
    update_list()

    main_view = ft.View(
        "/main",
        [
            title,
            ft.Row([scan_button, settings_button], alignment=ft.MainAxisAlignment.CENTER),
            ft.Row([search_field], alignment=ft.MainAxisAlignment.CENTER),
            ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
            list_view,
        ],
    )

    page.views.clear()
    page.views.append(main_view)
    page.update()

if __name__ == "__main__":
    ft.app(main)
