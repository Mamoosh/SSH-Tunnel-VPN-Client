import threading, time, socket
import paramiko
from .socks_server import SocksServer, _Counter
from .http_proxy import HttpProxy


class SSHTunnel:
    """SSH transport + local SOCKS5 (1080) + local HTTP proxy (1081)."""

    def __init__(self, host, port, username, password="", key_path="",
                 local_host="127.0.0.1", local_port=1080, http_port=1081):
        self.host = host
        self.port = int(port)
        self.username = username
        self.password = password
        self.key_path = key_path
        self.local_host = local_host
        self.local_port = local_port
        self.http_port = http_port

        self.client = None
        self.transport = None
        self.socks = None
        self.http = None
        self.counter = _Counter()
        self.connected = False
        self.error = ""
        self.server_ip = ""        # resolved IPv4 of the SSH server
        self._stop = threading.Event()

    def connect(self, timeout=15):
        # resolve the server IP up-front (needed by Full VPN / WinDivert)
        try:
            self.server_ip = socket.gethostbyname(self.host)
        except Exception:
            self.server_ip = self.host

        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        kwargs = dict(hostname=self.host, port=self.port,
                      username=self.username, timeout=timeout,
                      allow_agent=False, look_for_keys=False,
                      banner_timeout=timeout, auth_timeout=timeout)
        if self.key_path:
            kwargs["key_filename"] = self.key_path
            if self.password:
                kwargs["passphrase"] = self.password
        else:
            kwargs["password"] = self.password
        self.client.connect(**kwargs)

        self.transport = self.client.get_transport()
        self.transport.set_keepalive(15)
        self.transport.use_compression(False)

        self.socks = SocksServer(self.transport, self.local_host,
                                 self.local_port, self.counter)
        self.socks.start()
        self.http = HttpProxy(self.transport, self.local_host,
                              self.http_port, self.counter)
        self.http.start()

        self.connected = True
        threading.Thread(target=self._watch, daemon=True).start()
        return True

    def _watch(self):
        while not self._stop.is_set():
            time.sleep(2)
            if self.transport is None or not self.transport.is_active():
                self.connected = False
                self.error = "SSH transport closed"
                break

    def is_alive(self):
        return (self.connected and self.transport is not None
                and self.transport.is_active())

    def close(self):
        self._stop.set()
        if self.socks: self.socks.stop()
        if self.http: self.http.stop()
        try:
            if self.client: self.client.close()
        except Exception:
            pass
        self.connected = False
