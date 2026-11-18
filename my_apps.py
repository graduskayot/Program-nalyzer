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

# ==========================================
# ЛОГИКА ПОИСКА ПРОГРАММ (Без изменений)
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
                paths = re.findall(r'"path"\s+"([^"]+)"', content)
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
                                
                                apps.append({
                                    "name": name, 
                                    "path": install_path,
                                    "uninstall_cmd": uninstall_cmd
                                })
                            except FileNotFoundError:
                                pass
                    except OSError:
                        pass
        except FileNotFoundError:
            pass
    return sorted(apps, key=lambda x: x["name"].lower())

# --- БЛОК АВТООБНОВЛЕНИЯ ---
CURRENT_VERSION = "0.1.3"  # Версия твоей текущей программы
VERSION_URL = "https://raw.githubusercontent.com/graduskayot/Program-nalyzer/refs/heads/main/version.json"  # Ссылка на твой version.json

def check_update(page):
    try:
        # Пытаемся скачать файл с версией
        response = requests.get(VERSION_URL, timeout=5)
        data = response.json()
        latest = data["latest_version"]
        
        # Если версия в файле отличается от нашей
        if latest != CURRENT_VERSION:
            # Создаем блокирующее окно
            dlg = ft.AlertDialog(
                modal=True, # Блокирует всё остальное
                title=ft.Text("🚨 Доступно обновление"),
                content=ft.Text(f"Вышла новая версия {latest}. Программа не будет работать, пока вы не обновитесь."),
                actions=[
                    ft.TextButton("Скачать обновление и закрыть", on_click=lambda e: os.startfile(data["download_url"]) or sys.exit())
                ],
            )
            page.dialog = dlg
            dlg.open = True
            page.update()
            return False # Возвращаем False = БЛОКИРУЕМ ЗАПУСК
    except Exception:
        # Если интернета нет или файл не найден — просто продолжаем работу
        pass 
    return True # Возвращаем True = ВСЁ ОК, РАБОТАЕМ

# ==========================================
# ИНТЕРФЕЙС НА FLET
# ==========================================
def main(page: ft.Page):
    page.title = "Анализатор приложений by Gradus"
        # Проверяем обновление. Если версия старая — код дальше не пойдет
    if not check_update(page):
        return
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 20

    # --- Language settings (saved between launches) ---
    settings_path = os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), "AnalyserApps", "settings.json")
    os.makedirs(os.path.dirname(settings_path), exist_ok=True)
    try:
        with open(settings_path, "r", encoding="utf-8") as settings_file:
            settings = json.load(settings_file)
    except (OSError, ValueError):
        settings = {"language": "ru"}
    current_language = settings.get("language", "ru")

    # Edit these values to add your own translations.
    translations = {
        "ru": {
            "title": "Список установленных программ", "search": "🔍 Поиск по названию...",
            "scan": "🔄 Сканировать заново", "settings": "⚙️ Настройки", "language": "Язык",
            "settings_title": "Настройки", "save": "Сохранить", "cancel": "Отмена",
            "open": "📂 Открыть", "run": "▶️ Запустить", "delete": "🗑️ Удалить",
            "folder_missing": "Папка не найдена: {path}", "exe_missing": "Не найден .exe для запуска.",
            "launch_error": "Ошибка запуска: {error}", "uninstall_missing": "Команда удаления не найдена.",
            "uninstall_error": "Ошибка удаления: {error}",
        },
        "en": {
            "title": "Installed applications", "search": "🔍 Search by name...",
            "scan": "🔄 Scan again", "settings": "⚙️ Settings", "language": "Language",
            "settings_title": "Settings", "save": "Save", "cancel": "Cancel",
            "open": "📂 Open", "run": "▶️ Launch", "delete": "🗑️ Uninstall",
            "folder_missing": "Folder not found: {path}", "exe_missing": "No .exe file found.",
            "launch_error": "Launch error: {error}", "uninstall_missing": "Uninstall command not found.",
            "uninstall_error": "Uninstall error: {error}",
        },
    }

    def tr(key, **kwargs):
        return translations.get(current_language, translations["ru"]).get(key, key).format(**kwargs)


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
        update_list(search_field.value or "")

    # Список для хранения всех программ
    all_apps = []

    # Список приложений (создаётся один раз и обновляется при поиске)
    list_view = ft.ListView(
        expand=True,
        spacing=5,
        padding=10,
    )

    # Функция для обновления списка
    def update_list(filter_text=""):
        list_view.controls.clear()
        search_lower = (filter_text or "").lower()

        for app in all_apps:
            if search_lower in app['name'].lower():
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

        page.update()

    # Функции действий
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
        
        # В Flet для подтверждения можно использовать диалог, но для простоты запустим сразу
        try:
            subprocess.Popen(cmd, shell=True)
        except Exception as e:
            page.snack_bar = ft.SnackBar(ft.Text(tr("uninstall_error", error=e)))
            page.snack_bar.open = True
            page.update()

    # Функция сканирования
    def scan_apps(e=None):
        nonlocal all_apps
        all_apps = get_installed_apps()
        update_list(search_field.value)

    # Функция поиска
    def on_search_change(e):
        update_list(e.control.value)

    # Элементы интерфейса
    title = ft.Text(tr("title"), size=24, weight=ft.FontWeight.BOLD)
    
    search_field = ft.TextField(
        hint_text=tr("search"),
        width=400,
        on_change=on_search_change,
        border_radius=20,
    )
    
    scan_button = ft.ElevatedButton(
        tr("scan"),
        on_click=scan_apps,
        style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_700, color=ft.Colors.WHITE),
    )

    settings_button = ft.ElevatedButton(
        tr("settings"),
        on_click=lambda e: open_settings(),
        style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_700, color=ft.Colors.WHITE),
    )

    def refresh_texts():
        title.value = tr("title")
        search_field.hint_text = tr("search")
        scan_button.text = tr("scan")
        settings_button.text = tr("settings")
        page.update()

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
                ft.TextButton(tr("save"), on_click=lambda e: (save_language(language_dropdown.value), close_dialog())),
            ],
        )
        def close_dialog():
            dialog.open = False
            page.update()
        page.dialog = dialog
        dialog.open = True
        page.update()

    # Собираем страницу
    page.add(
        ft.Column(
            [
                title,
                ft.Row([scan_button, settings_button], alignment=ft.MainAxisAlignment.CENTER),
                ft.Row([search_field], alignment=ft.MainAxisAlignment.CENTER),
                ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
                list_view,
            ],
            expand=True,
        )
    )

    # Первоначальная загрузка
    scan_apps()

if __name__ == "__main__":
    ft.app(main)
