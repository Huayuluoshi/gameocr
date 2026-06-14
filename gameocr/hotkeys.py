from __future__ import annotations

from typing import Dict

from PyQt5.QtCore import QObject, pyqtSignal

from .config import normalize_hotkey


class HotkeyManager(QObject):
    hotkey_pressed = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self._listener = None
        self._bindings: Dict[str, str] = {}

    def start(self, trigger_hotkey: str, region_hotkey: str = "") -> bool:
        return self.update_bindings(trigger_hotkey, region_hotkey)

    def stop(self) -> None:
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None

    def update_bindings(self, trigger_hotkey: str, region_hotkey: str = "") -> bool:
        trigger_hotkey = normalize_hotkey(trigger_hotkey)
        if not trigger_hotkey:
            self.error.emit("热键不能为空")
            return False

        self.stop()
        try:
            from pynput import keyboard
        except Exception as exc:  # noqa: BLE001
            self.error.emit(f"无法导入 pynput: {exc}")
            return False

        self._bindings = {"trigger": trigger_hotkey}
        pynput_map = {
            to_pynput_hotkey(trigger_hotkey): lambda: self.hotkey_pressed.emit("trigger"),
        }
        try:
            self._listener = keyboard.GlobalHotKeys(pynput_map)
            self._listener.start()
            return True
        except Exception as exc:  # noqa: BLE001
            self._listener = None
            self.error.emit(f"注册全局热键失败，可能存在冲突: {exc}")
            return False


def to_pynput_hotkey(value: str) -> str:
    parts = [part.strip().lower() for part in normalize_hotkey(value).split("+") if part.strip()]
    converted = []
    modifiers = {"ctrl", "alt", "shift", "cmd"}
    special = {
        "enter",
        "space",
        "tab",
        "escape",
        "backspace",
        "delete",
        "insert",
        "home",
        "end",
        "page_up",
        "page_down",
        "up",
        "down",
        "left",
        "right",
    }
    for part in parts:
        if part in modifiers or part in special or (part.startswith("f") and part[1:].isdigit()):
            converted.append(f"<{part}>")
        elif len(part) == 1:
            converted.append(part)
        else:
            converted.append(f"<{part}>")
    return "+".join(converted)