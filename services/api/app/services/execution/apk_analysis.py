"""APK analysis via `aapt dump badging` (PRD §7.6.3 "auto-detected package name, launch
activity, version"). Shells out rather than parsing the binary AndroidManifest.xml format
directly — `aapt`/`aapt2` ship with the Android SDK build-tools and already do this correctly,
including resolving the launchable activity across manifest `<intent-filter>` variations.
"""

import re
import subprocess
from dataclasses import dataclass

_PACKAGE_RE = re.compile(
    r"package: name='(?P<name>[^']+)' versionCode='(?P<code>[^']*)' "
    r"versionName='(?P<version>[^']*)'"
)
_LAUNCHABLE_RE = re.compile(r"launchable-activity: name='(?P<activity>[^']+)'")
_LABEL_RE = re.compile(r"application-label:'(?P<label>[^']*)'")


class ApkAnalysisError(Exception):
    pass


@dataclass
class ApkInfo:
    package_name: str
    launch_activity: str
    version_name: str
    version_code: str
    label: str


def analyze_apk(apk_path: str, *, aapt_path: str = "aapt") -> ApkInfo:
    try:
        # aapt_path is an admin-configured setting; apk_path is a file this process itself
        # wrote to a temp dir just before the call, never raw request input.
        result = subprocess.run(  # noqa: S603
            [aapt_path, "dump", "badging", apk_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError as exc:
        raise ApkAnalysisError(
            f"{aapt_path!r} was not found — install Android SDK build-tools"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise ApkAnalysisError("Timed out analyzing the APK") from exc

    if result.returncode != 0:
        raise ApkAnalysisError(f"aapt could not analyze this file: {result.stderr.strip()}")

    package_match = _PACKAGE_RE.search(result.stdout)
    if not package_match:
        raise ApkAnalysisError("Could not find package info in this APK")
    launchable_match = _LAUNCHABLE_RE.search(result.stdout)
    if not launchable_match:
        raise ApkAnalysisError("This APK has no launchable activity")
    label_match = _LABEL_RE.search(result.stdout)

    activity = launchable_match.group("activity")
    package_name = package_match.group("name")
    # aapt gives the fully-qualified activity name; Appium's appActivity accepts either form,
    # but storing the short (`.ApiDemos`) form when it's under the package is more readable.
    if activity.startswith(package_name + "."):
        activity = activity[len(package_name) :]

    return ApkInfo(
        package_name=package_name,
        launch_activity=activity,
        version_name=package_match.group("version"),
        version_code=package_match.group("code"),
        label=label_match.group("label") if label_match else "",
    )
