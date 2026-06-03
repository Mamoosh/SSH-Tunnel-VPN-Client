"""
Lightweight Windows 10/11 toast notifications with zero pip dependencies.

Uses PowerShell + the WinRT ToastNotificationManager. Falls back silently if
anything is unavailable. Call notify("Title", "message").
"""
import subprocess, os

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
APP_ID = "SSHH.VPN"

_PS_TEMPLATE = r"""
$ErrorActionPreference = 'SilentlyContinue'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.UI.Notifications.ToastNotification, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$xml = @"
<toast>
  <visual>
    <binding template="ToastGeneric">
      <text>{title}</text>
      <text>{message}</text>
    </binding>
  </visual>
</toast>
"@
$doc = New-Object Windows.Data.Xml.Dom.XmlDocument
$doc.LoadXml($xml)
$toast = New-Object Windows.UI.Notifications.ToastNotification $doc
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("{app}").Show($toast)
"""

def _xml_escape(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))

def notify(title, message, enabled=True):
    if not enabled or os.name != "nt":
        return
    try:
        script = _PS_TEMPLATE.format(
            title=_xml_escape(title), message=_xml_escape(message), app=APP_ID)
        subprocess.Popen(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", script],
            creationflags=_NO_WINDOW,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
