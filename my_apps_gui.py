import winreg
import os
import re
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
import subprocess

# Настройка внешнего вида
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

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

# ==========================================
# ИНТЕРФЕЙС
# ==========================================
class AppScanner(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Анализатор приложений by Gradus")
        self.geometry("850x700")
        self.apps_data = []
        self.app_rows = []
        
        # Переменные для плавного скролла
        self.current_scroll_pos = 0.0
        self.target_scroll_pos = 0.0

        self.label = ctk.CTkLabel(self, text="Список установленных программ", font=("Arial", 20, "bold"))
        self.label.pack(pady=10)

        self.btn_scan = ctk.CTkButton(self, text="🔄 Сканировать заново", command=self.load_apps)
        self.btn_scan.pack(pady=5)

        self.search_var = tk.StringVar()
        self.search_entry = ctk.CTkEntry(self, placeholder_text="🔍 Поиск по названию...", 
                                         textvariable=self.search_var, width=400)
        self.search_entry.pack(pady=10)
        self.search_entry.bind("<KeyRelease>", self.filter_apps)

        self.main_frame = ctk.CTkFrame(self, fg_color="#212121", corner_radius=0)
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        # --- ХОЛСТ С ОПТИМИЗАЦИЕЙ ---
        # Используем стандартный canvas, но отключаем highlightthickness для скорости
        self.canvas = tk.Canvas(self.main_frame, bg="#212121", highlightthickness=0, bd=0)
        self.canvas.pack(side="left", fill="both", expand=True)

        # Скроллбар
        self.scrollbar = ctk.CTkScrollbar(self.main_frame, command=self._on_scrollbar_move)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # Внутренний фрейм
        self.scrollable_frame = tk.Frame(self.canvas, bg="#212121")
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.scrollable_frame.grid_columnconfigure(0, weight=1)
        
        self.canvas.bind('<Configure>', self._on_canvas_configure)
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        self.load_apps()
        self.animate_scroll()

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        delta = -1 * (event.delta / 120) * 0.05
        self.target_scroll_pos += delta
        self.target_scroll_pos = max(0.0, min(1.0, self.target_scroll_pos))

    def _on_scrollbar_move(self, *args):
        self.canvas.yview(*args)
        self.current_scroll_pos = self.canvas.yview()[0]
        self.target_scroll_pos = self.current_scroll_pos

    def animate_scroll(self):
        diff = self.target_scroll_pos - self.current_scroll_pos
        if abs(diff) > 0.001:
            self.current_scroll_pos += diff * 0.2
            self.canvas.yview_moveto(self.current_scroll_pos)
        self.after(15, self.animate_scroll)

    def load_apps(self):
        self.search_var.set("")
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.app_rows.clear()

        self.apps_data = get_installed_apps()

        for index, app in enumerate(self.apps_data):
            # --- ОПТИМИЗАЦИЯ ОТРИСОВКИ ---
            # Стандартный tk.Frame вместо CTkFrame — он рисуется быстрее и не рвется
            row = tk.Frame(self.scrollable_frame, bg="#2b2b2b", pady=5)
            row.grid(row=index, column=0, sticky="ew", pady=2, padx=5)
            
            # Внутренний контейнер для кнопок (используем grid для строгого выравнивания)
            row.grid_columnconfigure(0, weight=1) # Текст занимает всё место

            # Кнопки (пакуем справа через grid)
            btn_frame = tk.Frame(row, bg="#2b2b2b")
            btn_frame.grid(row=0, column=1, sticky="e", padx=5)

            btn_open = ctk.CTkButton(btn_frame, text="📂 Открыть", width=80, height=25,
                                     command=lambda p=app['path']: self.open_folder(p))
            btn_open.pack(side="left", padx=2)
            
            btn_run = ctk.CTkButton(btn_frame, text="▶️ Запустить", width=80, height=25, fg_color="#1f538d",
                                    command=lambda a=app: self.run_app(a))
            btn_run.pack(side="left", padx=2)
            
            btn_del = ctk.CTkButton(btn_frame, text="🗑️ Удалить", width=70, height=25, fg_color="#8b0000", hover_color="#b22222",
                                    command=lambda a=app: self.uninstall_app(a))
            btn_del.pack(side="left", padx=2)

            # Текст
            name_label = tk.Label(row, text=app['name'], bg="#2b2b2b", fg="white", 
                                  font=("Arial", 11, "bold"), anchor="w")
            name_label.grid(row=0, column=0, sticky="w", padx=5)

            path_label = tk.Label(row, text=app['path'], bg="#2b2b2b", fg="#888888", 
                                  font=("Arial", 9), anchor="w")
            path_label.grid(row=1, column=0, columnspan=2, sticky="w", padx=5)

            self.app_rows.append((row, app['name'].lower()))

    def filter_apps(self, event=None):
        search_query = self.search_var.get().lower()
        for row, name in self.app_rows:
            if search_query in name:
                row.grid()
            else:
                row.grid_remove()

    def run_app(self, app):
        path = app['path']
        if os.path.exists(path) and os.path.isdir(path):
            exe_files = [f for f in os.listdir(path) if f.lower().endswith('.exe')]
            valid_exe = [f for f in exe_files if not any(x in f.lower() for x in ['unins', 'setup', 'update', 'install'])]
            
            if valid_exe:
                try:
                    os.startfile(os.path.join(path, valid_exe[0]))
                except Exception as e:
                    messagebox.showerror("Ошибка", f"Не удалось запустить:\n{e}")
            else:
                messagebox.showinfo("Инфо", "В этой папке не найден .exe для запуска.")
        else:
            messagebox.showerror("Ошибка", "Папка не найдена.")

    def uninstall_app(self, app):
        cmd = app['uninstall_cmd']
        if not cmd:
            messagebox.showerror("Ошибка", "Команда удаления не найдена.")
            return
            
        if messagebox.askyesno("Удаление", f"Вы точно хотите удалить {app['name']}?"):
            try:
                subprocess.Popen(cmd, shell=True)
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось запустить удаление:\n{e}")

    def open_folder(self, path):
        if os.path.exists(path) and os.path.isdir(path):
            os.startfile(path)
        else:
            messagebox.showerror("Ошибка", f"Папка не найдена:\n{path}")

if __name__ == "__main__":
    app = AppScanner()
    app.mainloop()