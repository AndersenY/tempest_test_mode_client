"""
ПЭМИН — Запуск тестового режима СВТ
====================================
Назначение: создание детерминированного периодического сигнала
на интерфейсах монитора, клавиатуры и принтера для проведения
специальных исследований защищённости от ПЭМИН.

Поддерживаемые ОС: Windows, Linux
Зависимости: python 3.8+, tkinter (входит в стандартную поставку)
Опционально: pillow (pip install pillow) — для режима монитора
             pywin32 (pip install pywin32) — для принтера на Windows
"""

import sys
import os
import platform
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import subprocess
import signal

OS = platform.system()  # 'Windows' или 'Linux'

# ─────────────────────────────────────────────
#  УТИЛИТЫ
# ─────────────────────────────────────────────

def log(widget, msg):
    widget.configure(state="normal")
    widget.insert(tk.END, msg + "\n")
    widget.see(tk.END)
    widget.configure(state="disabled")


# ─────────────────────────────────────────────
#  МОДУЛЬ 1: МОНИТОР
#  Тестовый сигнал — меандр на экране:
#  чередование чёрных и белых вертикальных
#  полос шириной 1 пиксель (максимальная
#  частота переключений = 1/τ).
# ─────────────────────────────────────────────

class MonitorTest:
    """
    Открывает полноэкранное окно с тестовым паттерном.
    Паттерн: чередование чёрных/белых вертикальных полос
    шириной 1 пиксель — это меандр на видеоинтерфейсе,
    создающий максимальную частоту переключений пикселей
    и соответственно максимальное ПЭМИН.

    Дополнительно реализован режим «мигания» (инверсия
    паттерна каждые N мс) для создания низкочастотной
    огибающей, удобной для обнаружения методом разности панорам.
    """

    def __init__(self, parent_log, blink_ms=500):
        self.parent_log = parent_log
        self.blink_ms = blink_ms
        self.window = None
        self.canvas = None
        self.running = False
        self.phase = 0  # 0 = прямой паттерн, 1 = инвертированный
        self.stripe_px = 32  # ширина полосы в пикселях

    def _make_ppm(self, w, h, phase, stripe):
        """
        Горизонтальные полосы шириной stripe пикселей.
        Строки, попадающие в чётный блок — белые, нечётный — чёрные
        (при инверсии phase меняется на 1, блоки меняются местами).

        Строим два готовых ряда байт (белый и чёрный) и
        тиражируем их нужное количество раз — без питоновского
        цикла по пикселям, только операции bytes.
        """
        white_row = bytes([255, 255, 255]) * w
        black_row = bytes([0,   0,   0  ]) * w

        rows = bytearray()
        for y in range(h):
            block = (y // stripe + phase) % 2
            rows += white_row if block == 0 else black_row

        header = f"P6\n{w} {h}\n255\n".encode()
        photo = tk.PhotoImage(width=w, height=h)
        photo.put(header + bytes(rows), to=(0, 0))
        return photo

    def _draw_pattern(self):
        if not self.running or self.canvas is None:
            return
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 2 or h < 2:
            self.canvas.after(100, self._draw_pattern)
            return

        photo = self._make_ppm(w, h, self.phase, self.stripe_px)
        self.canvas.delete("all")
        self.canvas._photo = photo
        self.canvas.create_image(0, 0, anchor="nw", image=photo)

        self.phase = 1 - self.phase
        self.canvas.after(self.blink_ms, self._draw_pattern)

    def start(self):
        if self.running:
            return
        self.running = True
        self.window = tk.Toplevel()
        self.window.title("ПЭМИН — Тест монитора")
        self.window.attributes("-fullscreen", True)
        self.window.configure(bg="black")
        self.window.bind("<Escape>", lambda e: self.stop())

        self.canvas = tk.Canvas(self.window, bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        label = tk.Label(
            self.window,
            text="Тестовый режим монитора  •  ESC — остановить",
            fg="#888888", bg="#000000", font=("Courier", 11)
        )
        label.place(relx=0.5, rely=0.97, anchor="center")

        self.window.update()
        self._draw_pattern()
        log(self.parent_log, "[Монитор] Тест запущен. Паттерн: меандр 1px, инверсия каждые "
            f"{self.blink_ms} мс.")

    def stop(self):
        self.running = False
        if self.window:
            self.window.destroy()
            self.window = None
        log(self.parent_log, "[Монитор] Тест остановлен.")

    def set_blink(self, ms):
        self.blink_ms = ms

    def set_stripe(self, px):
        self.stripe_px = px


# ─────────────────────────────────────────────
#  МОДУЛЬ 2: КЛАВИАТУРА
#  Тестовый сигнал — непрерывная автоматическая
#  посылка нажатий одной клавиши с фиксированным
#  интервалом. Создаёт периодический импульсный
#  сигнал на шине USB/PS2.
# ─────────────────────────────────────────────

class KeyboardTest:
    """
    Метод: программная генерация нажатий клавиши Scroll Lock
    (не мешает работе ОС) с заданным периодом повтора.

    Windows: ctypes.windll.user32.keybd_event
    Linux:   xdotool / evemu-event (требует установки)

    Период повтора определяет F_T = 1/T сигнала на шине.
    Рекомендуемый период: 20–100 мс (10–50 Гц).
    """

    VK_SCROLL = 0x91  # Scroll Lock (Windows)

    def __init__(self, parent_log, interval_ms=50):
        self.parent_log = parent_log
        self.interval_ms = interval_ms
        self.running = False
        self._thread = None
        self._check_deps()

    def _check_deps(self):
        if OS == "Linux":
            result = subprocess.run(["which", "xdotool"],
                                    capture_output=True, text=True)
            if result.returncode != 0:
                log(self.parent_log,
                    "[Клавиатура] ВНИМАНИЕ: xdotool не найден. "
                    "Установите: sudo apt install xdotool")

    def _send_key_windows(self):
        import ctypes
        KEYEVENTF_KEYUP = 0x0002
        while self.running:
            ctypes.windll.user32.keybd_event(self.VK_SCROLL, 0, 0, 0)
            time.sleep(0.005)
            ctypes.windll.user32.keybd_event(self.VK_SCROLL, 0, KEYEVENTF_KEYUP, 0)
            time.sleep(self.interval_ms / 1000.0)

    def _send_key_linux(self):
        while self.running:
            subprocess.run(
                ["xdotool", "key", "Scroll_Lock"],
                capture_output=True
            )
            time.sleep(self.interval_ms / 1000.0)

    def start(self):
        if self.running:
            return
        self.running = True
        target = self._send_key_windows if OS == "Windows" else self._send_key_linux
        self._thread = threading.Thread(target=target, daemon=True)
        self._thread.start()
        freq = round(1000 / self.interval_ms, 1)
        log(self.parent_log,
            f"[Клавиатура] Тест запущен. Клавиша: Scroll Lock, "
            f"интервал: {self.interval_ms} мс, F_T ≈ {freq} Гц.")

    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join(timeout=1)
        log(self.parent_log, "[Клавиатура] Тест остановлен.")

    def set_interval(self, ms):
        self.interval_ms = ms


# ─────────────────────────────────────────────
#  МОДУЛЬ 3: ПРИНТЕР
#  Тестовый сигнал — непрерывная посылка
#  повторяющейся строки на принтер.
#  Создаёт периодический сигнал на интерфейсе
#  LPT или USB.
# ─────────────────────────────────────────────

class PrinterTest:
    """
    Метод: повторяющаяся посылка фиксированной строки байт
    на принтерный порт / очередь печати.

    Windows: запись в LPT1 через CreateFile или
             посылка PostScript/RAW через win32print.
    Linux:   запись в /dev/usb/lp0 или /dev/lp0,
             либо через lp/lpr.

    Тестовая строка: чередование 0xFF и 0x00 —
    это меандр на уровне байт, создающий
    максимальную частоту переключений на шине.
    """

    TEST_PATTERN = bytes([0xFF, 0x00] * 64)  # 128 байт меандра
    TEST_STR_TEXT = ("X " * 40 + "\n") * 5    # текстовый вариант

    def __init__(self, parent_log, port=None, interval_ms=200):
        self.parent_log = parent_log
        self.port = port  # None = автовыбор
        self.interval_ms = interval_ms
        self.running = False
        self._thread = None

    def _auto_port(self):
        if OS == "Windows":
            return "LPT1"
        else:
            for p in ["/dev/usb/lp0", "/dev/lp0", "/dev/usb/lp1"]:
                if os.path.exists(p):
                    return p
            return None

    def _run_windows(self, port):
        try:
            import win32print
            hprinter = win32print.OpenPrinter(port)
            win32print.StartDocPrinter(hprinter, 1, ("ПЭМИН-тест", None, "RAW"))
            win32print.StartPagePrinter(hprinter)
            count = 0
            while self.running:
                win32print.WritePrinter(hprinter, self.TEST_PATTERN)
                count += 1
                time.sleep(self.interval_ms / 1000.0)
            win32print.EndPagePrinter(hprinter)
            win32print.EndDocPrinter(hprinter)
            win32print.ClosePrinter(hprinter)
            log(self.parent_log, f"[Принтер] Отправлено посылок: {count}.")
        except ImportError:
            log(self.parent_log,
                "[Принтер] win32print не установлен. "
                "Установите: pip install pywin32")
        except Exception as e:
            log(self.parent_log, f"[Принтер] Ошибка: {e}")

    def _run_linux(self, port):
        try:
            count = 0
            with open(port, "wb") as f:
                while self.running:
                    f.write(self.TEST_PATTERN)
                    f.flush()
                    count += 1
                    time.sleep(self.interval_ms / 1000.0)
            log(self.parent_log, f"[Принтер] Отправлено посылок: {count}.")
        except PermissionError:
            log(self.parent_log,
                f"[Принтер] Нет доступа к {port}. "
                "Попробуйте: sudo adduser $USER lp")
        except Exception as e:
            log(self.parent_log, f"[Принтер] Ошибка: {e}")

    def start(self):
        if self.running:
            return
        port = self.port or self._auto_port()
        if port is None:
            log(self.parent_log,
                "[Принтер] Принтерный порт не найден. "
                "Укажите порт вручную.")
            return
        self.running = True
        target = self._run_windows if OS == "Windows" else self._run_linux
        self._thread = threading.Thread(
            target=target, args=(port,), daemon=True)
        self._thread.start()
        log(self.parent_log,
            f"[Принтер] Тест запущен. Порт: {port}, "
            f"интервал: {self.interval_ms} мс, "
            f"паттерн: 0xFF/0x00 × 64.")

    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join(timeout=2)
        log(self.parent_log, "[Принтер] Тест остановлен.")

    def set_interval(self, ms):
        self.interval_ms = ms

    def set_port(self, port):
        self.port = port


# ─────────────────────────────────────────────
#  ГЛАВНОЕ ОКНО
# ─────────────────────────────────────────────

class App(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title(f"ПЭМИН — Тестовый режим СВТ  [{OS}]")
        self.geometry("720x580")
        self.resizable(False, False)
        self.configure(bg="#f5f5f5")

        self._build_ui()

        self.monitor_test = MonitorTest(self.log_widget)
        self.keyboard_test = KeyboardTest(self.log_widget)
        self.printer_test = PrinterTest(self.log_widget)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI ──────────────────────────────────

    def _build_ui(self):
        title = tk.Label(
            self, text="ПЭМИН — Запуск тестового режима",
            font=("Arial", 13, "bold"), bg="#f5f5f5", fg="#222"
        )
        title.pack(pady=(12, 4))

        subtitle = tk.Label(
            self,
            text="Создание детерминированного периодического сигнала на интерфейсах СВТ",
            font=("Arial", 9), bg="#f5f5f5", fg="#666"
        )
        subtitle.pack(pady=(0, 10))

        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, padx=14, pady=4, expand=False)

        # ── Монитор ──
        f_mon = ttk.Frame(nb)
        nb.add(f_mon, text="  Монитор  ")
        self._tab_monitor(f_mon)

        # ── Клавиатура ──
        f_kbd = ttk.Frame(nb)
        nb.add(f_kbd, text="  Клавиатура  ")
        self._tab_keyboard(f_kbd)

        # ── Принтер ──
        f_prt = ttk.Frame(nb)
        nb.add(f_prt, text="  Принтер  ")
        self._tab_printer(f_prt)

        # ── Лог ──
        log_frame = tk.LabelFrame(self, text=" Журнал ", bg="#f5f5f5",
                                  font=("Arial", 9))
        log_frame.pack(fill=tk.BOTH, padx=14, pady=(6, 10), expand=True)

        self.log_widget = scrolledtext.ScrolledText(
            log_frame, height=10, state="disabled",
            font=("Courier", 9), bg="#1e1e1e", fg="#cccccc",
            insertbackground="white"
        )
        self.log_widget.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        log(self.log_widget,
            f"[Система] ОС: {OS} | Python {sys.version.split()[0]} | "
            "Инструмент готов к работе.")

    def _tab_monitor(self, parent):
        tk.Label(parent, text="Тестовый паттерн:", anchor="w").grid(
            row=0, column=0, sticky="w", padx=12, pady=(10, 2))
        tk.Label(
            parent,
            text="Меандр: чередование белых/чёрных вертикальных полос шириной 1 пиксель.\n"
                 "Создаёт максимальную частоту переключений пикселей на видеоинтерфейсе.",
            fg="#555", justify="left", wraplength=580
        ).grid(row=1, column=0, columnspan=3, sticky="w", padx=12)

        tk.Label(parent, text="Ширина полосы (px):").grid(
            row=2, column=0, sticky="w", padx=12, pady=(10, 2))
        self.mon_stripe = tk.IntVar(value=32)
        tk.Scale(parent, from_=4, to=256, orient=tk.HORIZONTAL,
                 variable=self.mon_stripe, length=300).grid(
            row=2, column=1, sticky="w", padx=6)
        tk.Label(parent, textvariable=self.mon_stripe).grid(
            row=2, column=2, sticky="w")

        tk.Label(parent, text="Интервал инверсии (мс):").grid(
            row=3, column=0, sticky="w", padx=12, pady=(6, 2))
        self.mon_blink = tk.IntVar(value=500)
        tk.Scale(parent, from_=100, to=2000, orient=tk.HORIZONTAL,
                 variable=self.mon_blink, length=300).grid(
            row=3, column=1, sticky="w", padx=6)
        tk.Label(parent, textvariable=self.mon_blink).grid(
            row=3, column=2, sticky="w")

        btn_frame = tk.Frame(parent)
        btn_frame.grid(row=4, column=0, columnspan=3, pady=14, padx=12, sticky="w")

        self.mon_start_btn = tk.Button(
            btn_frame, text="▶  Запустить тест монитора",
            command=self._mon_start, width=24,
            bg="#2e7d32", fg="white", relief="flat", pady=6)
        self.mon_start_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.mon_stop_btn = tk.Button(
            btn_frame, text="■  Остановить",
            command=self._mon_stop, width=14,
            bg="#c62828", fg="white", relief="flat", pady=6,
            state="disabled")
        self.mon_stop_btn.pack(side=tk.LEFT)

        tk.Label(parent, text="Горячая клавиша для остановки: ESC (в окне теста)",
                 fg="#888", font=("Arial", 8)).grid(
            row=5, column=0, columnspan=3, sticky="w", padx=12)

    def _tab_keyboard(self, parent):
        tk.Label(parent, text="Тестовый сигнал:", anchor="w").grid(
            row=0, column=0, sticky="w", padx=12, pady=(10, 2))
        tk.Label(
            parent,
            text="Периодические нажатия клавиши Scroll Lock с фиксированным интервалом.\n"
                 "Создаёт детерминированный импульсный сигнал на шине USB/PS2.",
            fg="#555", justify="left", wraplength=580
        ).grid(row=1, column=0, columnspan=3, sticky="w", padx=12)

        tk.Label(parent, text="Интервал (мс) / F_T:").grid(
            row=2, column=0, sticky="w", padx=12, pady=(10, 2))
        self.kbd_interval = tk.IntVar(value=50)
        tk.Scale(parent, from_=10, to=500, orient=tk.HORIZONTAL,
                 variable=self.kbd_interval, length=300).grid(
            row=2, column=1, sticky="w", padx=6)

        self.kbd_freq_label = tk.Label(parent, text="20.0 Гц", fg="#333")
        self.kbd_freq_label.grid(row=2, column=2, sticky="w")
        self.kbd_interval.trace_add("write", self._update_kbd_freq)

        if OS == "Linux":
            tk.Label(
                parent,
                text="Linux: требуется xdotool  (sudo apt install xdotool)",
                fg="#e65100", font=("Arial", 8)
            ).grid(row=3, column=0, columnspan=3, sticky="w", padx=12, pady=(4, 0))

        btn_frame = tk.Frame(parent)
        btn_frame.grid(row=4, column=0, columnspan=3, pady=14, padx=12, sticky="w")

        self.kbd_start_btn = tk.Button(
            btn_frame, text="▶  Запустить тест клавиатуры",
            command=self._kbd_start, width=24,
            bg="#2e7d32", fg="white", relief="flat", pady=6)
        self.kbd_start_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.kbd_stop_btn = tk.Button(
            btn_frame, text="■  Остановить",
            command=self._kbd_stop, width=14,
            bg="#c62828", fg="white", relief="flat", pady=6,
            state="disabled")
        self.kbd_stop_btn.pack(side=tk.LEFT)

    def _tab_printer(self, parent):
        tk.Label(parent, text="Тестовый сигнал:", anchor="w").grid(
            row=0, column=0, sticky="w", padx=12, pady=(10, 2))
        tk.Label(
            parent,
            text="Непрерывная посылка паттерна 0xFF/0x00×64 на принтерный порт.\n"
                 "Меандр на уровне байт: максимальная частота переключений на шине.",
            fg="#555", justify="left", wraplength=580
        ).grid(row=1, column=0, columnspan=3, sticky="w", padx=12)

        tk.Label(parent, text="Порт:").grid(
            row=2, column=0, sticky="w", padx=12, pady=(10, 2))
        default_port = "LPT1" if OS == "Windows" else "/dev/usb/lp0"
        self.prt_port = tk.StringVar(value=default_port)
        tk.Entry(parent, textvariable=self.prt_port, width=20).grid(
            row=2, column=1, sticky="w", padx=6)

        tk.Label(parent, text="Интервал (мс):").grid(
            row=3, column=0, sticky="w", padx=12, pady=(6, 2))
        self.prt_interval = tk.IntVar(value=200)
        tk.Scale(parent, from_=50, to=2000, orient=tk.HORIZONTAL,
                 variable=self.prt_interval, length=300).grid(
            row=3, column=1, sticky="w", padx=6)
        tk.Label(parent, textvariable=self.prt_interval).grid(
            row=3, column=2, sticky="w")

        if OS == "Windows":
            tk.Label(
                parent,
                text="Windows: требуется pywin32  (pip install pywin32)",
                fg="#e65100", font=("Arial", 8)
            ).grid(row=4, column=0, columnspan=3, sticky="w", padx=12, pady=(4, 0))
        else:
            tk.Label(
                parent,
                text="Linux: нужен доступ к порту  (sudo adduser $USER lp)",
                fg="#e65100", font=("Arial", 8)
            ).grid(row=4, column=0, columnspan=3, sticky="w", padx=12, pady=(4, 0))

        btn_frame = tk.Frame(parent)
        btn_frame.grid(row=5, column=0, columnspan=3, pady=14, padx=12, sticky="w")

        self.prt_start_btn = tk.Button(
            btn_frame, text="▶  Запустить тест принтера",
            command=self._prt_start, width=24,
            bg="#2e7d32", fg="white", relief="flat", pady=6)
        self.prt_start_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.prt_stop_btn = tk.Button(
            btn_frame, text="■  Остановить",
            command=self._prt_stop, width=14,
            bg="#c62828", fg="white", relief="flat", pady=6,
            state="disabled")
        self.prt_stop_btn.pack(side=tk.LEFT)

    # ── Обработчики ─────────────────────────

    def _update_kbd_freq(self, *_):
        try:
            ms = self.kbd_interval.get()
            self.kbd_freq_label.config(text=f"{round(1000/ms, 1)} Гц")
        except Exception:
            pass

    def _mon_start(self):
        self.monitor_test.set_stripe(self.mon_stripe.get())
        self.monitor_test.set_blink(self.mon_blink.get())
        self.monitor_test.start()
        self.mon_start_btn.config(state="disabled")
        self.mon_stop_btn.config(state="normal")

    def _mon_stop(self):
        self.monitor_test.stop()
        self.mon_start_btn.config(state="normal")
        self.mon_stop_btn.config(state="disabled")

    def _kbd_start(self):
        self.keyboard_test.set_interval(self.kbd_interval.get())
        self.keyboard_test.start()
        self.kbd_start_btn.config(state="disabled")
        self.kbd_stop_btn.config(state="normal")

    def _kbd_stop(self):
        self.keyboard_test.stop()
        self.kbd_start_btn.config(state="normal")
        self.kbd_stop_btn.config(state="disabled")

    def _prt_start(self):
        self.printer_test.set_port(self.prt_port.get())
        self.printer_test.set_interval(self.prt_interval.get())
        self.printer_test.start()
        self.prt_start_btn.config(state="disabled")
        self.prt_stop_btn.config(state="normal")

    def _prt_stop(self):
        self.printer_test.stop()
        self.prt_start_btn.config(state="normal")
        self.prt_stop_btn.config(state="disabled")

    def _on_close(self):
        self.monitor_test.stop()
        self.keyboard_test.stop()
        self.printer_test.stop()
        self.destroy()


# ─────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    app.mainloop()
