"""Unit tests for `LocalEmulatorProvider`'s device-selection logic, with `adb`/`emulator`
mocked out — the critical property under test is that it NEVER touches an attached emulator
it wasn't configured for, even when one is present. The real subprocess/adb path is exercised
separately by `tests/execution/` against a real emulator."""

from unittest.mock import patch

import pytest

from app.services.execution.android_provider import DeviceProviderError, LocalEmulatorProvider


def _fake_run(responses: dict[tuple[str, ...], str]):
    def run(cmd, **kwargs):
        key = tuple(cmd[1:])  # drop the adb/emulator binary path itself
        for pattern, output in responses.items():
            if key == pattern:
                result = type("Result", (), {"stdout": output, "stderr": ""})()
                return result
        raise AssertionError(f"Unexpected adb invocation: {cmd}")

    return run


def test_finds_the_warm_instance_matching_the_configured_avd() -> None:
    responses = {
        ("devices",): "List of devices attached\nemulator-5554\tdevice\nemulator-5556\tdevice\n\n",
        ("-s", "emulator-5554", "emu", "avd", "name"): "SomeoneElsesAVD\nOK\n",
        ("-s", "emulator-5556", "emu", "avd", "name"): "QAForgeTest\nOK\n",
    }
    provider = LocalEmulatorProvider(
        avd_name="QAForgeTest", appium_server_url="http://127.0.0.1:4723", adb_path="adb"
    )
    with patch("subprocess.run", side_effect=_fake_run(responses)):
        device = provider.acquire_device()
    assert device.udid == "emulator-5556"


def test_never_picks_an_emulator_running_a_different_avd() -> None:
    responses = {
        ("devices",): "List of devices attached\nemulator-5554\tdevice\n\n",
        ("-s", "emulator-5554", "emu", "avd", "name"): "SomeoneElsesAVD\nOK\n",
        # The fallback "boot a new instance" path picks the next free port (5556, since 5554
        # is in use) and polls this exact command while waiting for it to come up.
        ("-s", "emulator-5556", "shell", "getprop", "sys.boot_completed"): "",
    }
    provider = LocalEmulatorProvider(
        avd_name="QAForgeTest",
        appium_server_url="http://127.0.0.1:4723",
        adb_path="adb",
        boot_timeout_seconds=0.1,
    )
    with (
        patch("subprocess.run", side_effect=_fake_run(responses)),
        patch("subprocess.Popen"),
        pytest.raises(DeviceProviderError),
    ):
        # No warm instance matches, and the "boot" path times out immediately (0.1s, never
        # reports booted) rather than ever touching emulator-5554.
        provider.acquire_device()


def test_ignores_offline_devices() -> None:
    responses = {
        ("devices",): "List of devices attached\nemulator-5554\toffline\n\n",
        # No "device"-status emulator is attached, so the fallback boots at the default port.
        ("-s", "emulator-5554", "shell", "getprop", "sys.boot_completed"): "",
    }
    provider = LocalEmulatorProvider(
        avd_name="QAForgeTest",
        appium_server_url="http://127.0.0.1:4723",
        adb_path="adb",
        boot_timeout_seconds=0.1,
    )
    with (
        patch("subprocess.run", side_effect=_fake_run(responses)),
        patch("subprocess.Popen"),
        pytest.raises(DeviceProviderError),
    ):
        provider.acquire_device()


def test_release_device_is_a_no_op() -> None:
    from app.services.execution.android_provider import AndroidDevice

    provider = LocalEmulatorProvider(avd_name="QAForgeTest", appium_server_url="http://x")
    # Should not raise, and should not require any adb call.
    provider.release_device(AndroidDevice(udid="emulator-5556", appium_server_url="http://x"))


def test_remote_appium_provider_is_an_explicit_stub() -> None:
    from app.services.execution.android_provider import RemoteAppiumProvider

    provider = RemoteAppiumProvider(remote_appium_url="https://example.com")
    with pytest.raises(NotImplementedError):
        provider.acquire_device()
