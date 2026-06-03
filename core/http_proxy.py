import socket, threading, select


class HttpProxy:
    """
    A tiny HTTP/HTTPS (CONNECT) proxy that tunnels every request through an
    open paramiko SSH transport via 'direct-tcpip' channels. Windows system
    proxy works far more reliably with an HTTP proxy than with raw SOCKS,
    so running this alongside SOCKS makes the tunnel cover almost all apps.
    """

    def __init__(self, transport, host="127.0.0.1", port=1081, counter=None):
        self.transport = transport
        self.host = host
        self.port = port
        self.counter = counter
        self._srv = None
        self._stop = threading.Event()

    def start(self):
        self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind((self.host, self.port))
        self._srv.listen(200)
        self._srv.settimeout(1.0)
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self._stop.set()
        try:
            if self._srv:
                self._srv.close()
        except Exception:
            pass

    def _loop(self):
        while not self._stop.is_set():
            try:
                cli, _ = self._srv.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self._handle, args=(cli,),
                             daemon=True).start()

    def _handle(self, cli):
        try:
            cli.settimeout(20)
            data = b""
            while b"\r\n\r\n" not in data:
                chunk = cli.recv(4096)
                if not chunk:
                    cli.close(); return
                data += chunk
                if len(data) > 65536:
                    cli.close(); return

            head = data.split(b"\r\n")[0].decode("latin1", "ignore")
            parts = head.split(" ")
            if len(parts) < 2:
                cli.close(); return
            method, target = parts[0], parts[1]

            if method.upper() == "CONNECT":
                # target = host:port  (HTTPS tunnel)
                host, _, port = target.partition(":")
                port = int(port or 443)
                chan = self._open(host, port)
                if chan is None:
                    cli.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                    cli.close(); return
                cli.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                self._pipe(cli, chan)
            else:
                # plain HTTP — parse absolute URL host
                host, port, rest = self._parse_http(target, data)
                if not host:
                    cli.close(); return
                chan = self._open(host, port)
                if chan is None:
                    cli.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                    cli.close(); return
                chan.sendall(rest)
                if self.counter:
                    self.counter.add_up(len(rest))
                self._pipe(cli, chan)
        except Exception:
            try: cli.close()
            except Exception: pass

    def _parse_http(self, target, data):
        host, port = "", 80
        if target.startswith("http://"):
            t = target[7:]
            hostport, _, path = t.partition("/")
            host, _, p = hostport.partition(":")
            port = int(p or 80)
            # rewrite request line to origin form
            lines = data.split(b"\r\n")
            lines[0] = (data.split(b" ")[0] + b" /" + path.encode() +
                        b" HTTP/1.1")
            data = b"\r\n".join(lines)
        return host, port, data

    def _open(self, host, port):
        try:
            return self.transport.open_channel(
                "direct-tcpip", (host, port), ("127.0.0.1", 0))
        except Exception:
            return None

    def _pipe(self, cli, chan):
        try:
            while True:
                r, _, _ = select.select([cli, chan], [], [], 30)
                if not r:
                    break
                if cli in r:
                    d = cli.recv(65536)
                    if not d: break
                    chan.sendall(d)
                    if self.counter: self.counter.add_up(len(d))
                if chan in r:
                    d = chan.recv(65536)
                    if not d: break
                    cli.sendall(d)
                    if self.counter: self.counter.add_down(len(d))
        except Exception:
            pass
        finally:
            try: chan.close()
            except Exception: pass
            try: cli.close()
            except Exception: pass
