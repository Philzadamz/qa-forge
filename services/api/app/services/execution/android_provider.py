"""Device acquisition for the Android runner (PRD §7.6.3): `AndroidDeviceProvider` is the
pluggable backend interface, `LocalEmulatorProvider` the v1 implementation, `RemoteAppiumProvider`
a documented stub for a cloud device farm.

`LocalEmulatorProvider` only ever touches the one AVD it's configured with
(`Settings.android_avd_name`) — it identifies a candidate emulator by asking each attached
device "which AVD are you" (`adb -s <serial> emu avd name`), never by just grabbing the first
`adb devices` entry. A dev machine may have other emulators running for unrelated reasons; this
provider must never interact with one it wasn't told about.
"""

import subprocess
import time
from dataclasses import dataclass
from typing import Protocol


class DeviceProviderError(Exception):
    pass


@dataclass
class AndroidDevice:
    udid: str
    appium_server_url: str


class AndroidDeviceProvider(Protocol):
    def acquire_device(self) -> AndroidDevice: ...
    def release_device(self, device: AndroidDevice) -> None: ...


def _run_adb(adb_path: str, *args: str, timeout: float = 15.0) -> str:
    # adb_path is an admin-configured setting, args are built from our own fixed strings and
    # the serial adb itself just reported — never user/request-supplied input.
    result = subprocess.run(  # noqa: S603
        [adb_path, *args], capture_output=True, text=True, timeout=timeout
    )
    return result.stdout.strip()


def _attached_emulator_serials(adb_path: str) -> list[str]:
    output = _run_adb(adb_path, "devices")
    serials = []
    for line in output.splitlines()[1:]:  # skip the "List of devices attached" header
        parts = line.split()
        if len(parts) == 2 and parts[1] == "device" and parts[0].startswith("emulator-"):
            serials.append(parts[0])
    return serials


def _avd_name_for_serial(adb_path: str, serial: str) -> str | None:
    try:
        output = _run_adb(adb_path, "-s", serial, "emu", "avd", "name")
    except subprocess.TimeoutExpired:
        return None
    # The emulator console echoes "OK" after the name; take the first non-empty, non-"OK" line.
    for line in output.splitlines():
        stripped = line.strip()
        if stripped and stripped != "OK":
            return stripped
    return None


class LocalEmulatorProvider:
    def __init__(
        self,
        *,
        avd_name: str,
        appium_server_url: str,
        adb_path: str = "adb",
        emulator_path: str = "emulator",
        boot_timeout_seconds: float = 180.0,
    ) -> None:
        self._avd_name = avd_name
        self._appium_server_url = appium_server_url
        self._adb_path = adb_path
        self._emulator_path = emulator_path
        self._boot_timeout_seconds = boot_timeout_seconds

    def _find_warm_instance(self) -> str | None:
        for serial in _attached_emulator_serials(self._adb_path):
            if _avd_name_for_serial(self._adb_path, serial) == self._avd_name:
                return serial
        return None

    def _boot_new_instance(self) -> str:
        used_ports = {
            int(serial.split("-")[1]) for serial in _attached_emulator_serials(self._adb_path)
        }
        port = 5554
        while port in used_ports:
            port += 2
        # Same trust boundary as _run_adb above: every argument is either a fixed literal or
        # the admin-configured AVD name/emulator path, never request-supplied.
        subprocess.Popen(  # noqa: S603
            [
                self._emulator_path,
                "-avd",
                self._avd_name,
                "-port",
                str(port),
                "-no-window",
                "-no-audio",
                "-no-boot-anim",
                "-gpu",
                "swiftshader_indirect",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        serial = f"emulator-{port}"
        deadline = time.monotonic() + self._boot_timeout_seconds
        while time.monotonic() < deadline:
            booted = _run_adb(
                self._adb_path, "-s", serial, "shell", "getprop", "sys.boot_completed"
            )
            if booted.strip() == "1":
                return serial
            time.sleep(2)
        raise DeviceProviderError(
            f"AVD {self._avd_name!r} did not boot within {self._boot_timeout_seconds}s"
        )

    def acquire_device(self) -> AndroidDevice:
        serial = self._find_warm_instance() or self._boot_new_instance()
        return AndroidDevice(udid=serial, appium_server_url=self._appium_server_url)

    def release_device(self, device: AndroidDevice) -> None:
        # Deliberately a no-op: leaves the emulator running warm for the next run (PRD §7.6
        # "start (or reuse warm) emulator container"). Per-run isolation comes from
        # uninstalling the APK and clearing its data, not from tearing down the whole VM.
        pass


class RemoteAppiumProvider:
    """Stub (PRD §7.6.3): a cloud device farm (BrowserStack/Sauce Labs/LambdaTest) reached via
    a remote Appium URL. Not implemented — no farm account/credentials to build and verify
    against in this environment; `AndroidDeviceProvider` is the seam a real implementation
    would fill in without touching the runner above it."""

    def __init__(self, *, remote_appium_url: str) -> None:
        self._remote_appium_url = remote_appium_url

    def acquire_device(self) -> AndroidDevice:
        raise NotImplementedError("Remote device farm support is not implemented yet")

    def release_device(self, device: AndroidDevice) -> None:
        raise NotImplementedError("Remote device farm support is not implemented yet")
