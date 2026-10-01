import shutil
from pathlib import Path

import pytest

from app.services.execution.apk_analysis import ApkAnalysisError, analyze_apk

REPO_ROOT = Path(__file__).resolve().parents[4]
SAMPLE_APK = REPO_ROOT / "infra" / "demo-android" / "ApiDemos-debug.apk"

needs_sample_apk = pytest.mark.skipif(
    not SAMPLE_APK.exists(), reason="infra/demo-android/ApiDemos-debug.apk not present"
)


def _aapt_path() -> str | None:
    # build-tools binaries are rarely on PATH even with the SDK installed — read this dev
    # machine's own .env as a fallback, the same path the real runner would use.
    found = shutil.which("aapt") or shutil.which("aapt2")
    if found:
        return found
    from dotenv import dotenv_values

    configured = dotenv_values(REPO_ROOT / ".env").get("ANDROID_AAPT_PATH")
    return configured if configured and Path(configured).is_file() else None


@needs_sample_apk
def test_analyze_apk_extracts_package_activity_and_version() -> None:
    aapt = _aapt_path()
    if not aapt:
        pytest.skip("aapt/aapt2 not installed")
    info = analyze_apk(str(SAMPLE_APK), aapt_path=aapt)
    assert info.package_name == "io.appium.android.apis"
    assert info.launch_activity == ".ApiDemos"
    assert info.version_name == "5.0.0"
    assert info.label == "API Demos"


def test_analyze_apk_raises_on_missing_aapt_binary(tmp_path: Path) -> None:
    fake_apk = tmp_path / "whatever.apk"
    with pytest.raises(ApkAnalysisError, match="not found"):
        analyze_apk(str(fake_apk), aapt_path="/nonexistent/aapt-binary-xyz")


@needs_sample_apk
def test_analyze_apk_raises_on_non_apk_file(tmp_path: Path) -> None:
    aapt = _aapt_path()
    if not aapt:
        pytest.skip("aapt/aapt2 not installed")
    bogus = tmp_path / "not-an-apk.apk"
    bogus.write_bytes(b"not a real apk")
    with pytest.raises(ApkAnalysisError):
        analyze_apk(str(bogus), aapt_path=aapt)
