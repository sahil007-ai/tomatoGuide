"""Optional Bluetooth transport for accountability events.

This module provides an additive transport layer that can run alongside the
existing file-based collaboration system.
"""

from __future__ import annotations

import json
import queue
import socket
import threading
import time
import uuid
from typing import Dict, List


class BluetoothAccountabilityBridge:
    def __init__(self, logger) -> None:
        self.logger = logger
        self.sender_id = uuid.uuid4().hex

        self._server_socket = None
        self._socket = None
        self._accept_thread = None
        self._reader_thread = None
        self._lock = threading.Lock()
        self._events: "queue.Queue[Dict]" = queue.Queue()
        self._running = False
        self._waiting_for_peer = False

    @staticmethod
    def is_supported() -> bool:
        return all(
            hasattr(socket, attr)
            for attr in ("AF_BLUETOOTH", "BTPROTO_RFCOMM", "SOCK_STREAM")
        )

    def is_connected(self) -> bool:
        with self._lock:
            return self._socket is not None

    def is_waiting(self) -> bool:
        return self._waiting_for_peer

    def start_host(self, channel: int = 4) -> bool:
        if not self.is_supported():
            self.logger.warning("Bluetooth RFCOMM is not supported on this system")
            return False

        self.stop()
        try:
            server_socket = socket.socket(
                socket.AF_BLUETOOTH,
                socket.SOCK_STREAM,
                socket.BTPROTO_RFCOMM,
            )
            server_socket.bind(("", int(channel)))
            server_socket.listen(1)
            server_socket.settimeout(1.0)

            with self._lock:
                self._server_socket = server_socket
                self._running = True
                self._waiting_for_peer = True

            self._accept_thread = threading.Thread(
                target=self._accept_worker,
                daemon=True,
            )
            self._accept_thread.start()
            self.logger.info("Bluetooth host started on channel %s", channel)
            return True
        except Exception as exc:
            self.logger.warning("Failed to start Bluetooth host: %s", exc)
            self.stop()
            return False

    def connect(self, address: str, channel: int = 4, timeout: float = 8.0) -> bool:
        if not self.is_supported():
            self.logger.warning("Bluetooth RFCOMM is not supported on this system")
            return False

        self.stop()
        try:
            bt_socket = socket.socket(
                socket.AF_BLUETOOTH,
                socket.SOCK_STREAM,
                socket.BTPROTO_RFCOMM,
            )
            bt_socket.settimeout(timeout)
            bt_socket.connect((address, int(channel)))
            bt_socket.settimeout(1.0)

            with self._lock:
                self._socket = bt_socket
                self._running = True
                self._waiting_for_peer = False

            self._start_reader_thread()
            self.logger.info(
                "Bluetooth connected to %s on channel %s", address, channel
            )
            return True
        except Exception as exc:
            self.logger.warning("Bluetooth connect failed: %s", exc)
            self.stop()
            return False

    def send_event(self, event_type: str, payload: Dict) -> bool:
        with self._lock:
            sock = self._socket

        if sock is None:
            return False

        event = {
            "type": event_type,
            "timestamp": time.time(),
            "sender": self.sender_id,
            "payload": payload,
            "transport": "bluetooth",
        }

        try:
            message = (json.dumps(event) + "\n").encode("utf-8")
            sock.sendall(message)
            return True
        except Exception as exc:
            self.logger.warning("Bluetooth send failed: %s", exc)
            self.stop()
            return False

    def poll_events(self) -> List[Dict]:
        events: List[Dict] = []
        while True:
            try:
                events.append(self._events.get_nowait())
            except queue.Empty:
                break
        return events

    def stop(self) -> None:
        with self._lock:
            self._running = False
            self._waiting_for_peer = False
            sock = self._socket
            server_sock = self._server_socket
            self._socket = None
            self._server_socket = None

        for item in (sock, server_sock):
            if item is None:
                continue
            try:
                item.close()
            except Exception:
                pass

    def _accept_worker(self) -> None:
        while True:
            with self._lock:
                running = self._running
                server_socket = self._server_socket

            if not running or server_socket is None:
                return

            try:
                bt_socket, _ = server_socket.accept()
                bt_socket.settimeout(1.0)
                with self._lock:
                    if self._socket is not None:
                        try:
                            self._socket.close()
                        except Exception:
                            pass
                    self._socket = bt_socket
                    self._waiting_for_peer = False
                self._start_reader_thread()
                self.logger.info("Bluetooth peer connected")
                return
            except socket.timeout:
                continue
            except Exception as exc:
                self.logger.warning("Bluetooth accept failed: %s", exc)
                self.stop()
                return

    def _start_reader_thread(self) -> None:
        self._reader_thread = threading.Thread(target=self._reader_worker, daemon=True)
        self._reader_thread.start()

    def _reader_worker(self) -> None:
        buffer = ""
        while True:
            with self._lock:
                running = self._running
                sock = self._socket

            if not running or sock is None:
                return

            try:
                data = sock.recv(4096)
                if not data:
                    self.logger.info("Bluetooth peer disconnected")
                    self.stop()
                    return

                buffer += data.decode("utf-8", errors="ignore")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if event.get("sender") == self.sender_id:
                        continue
                    self._events.put(event)
            except socket.timeout:
                continue
            except Exception as exc:
                self.logger.warning("Bluetooth receive failed: %s", exc)
                self.stop()
                return
