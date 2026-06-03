import socket, struct, threading, select


class _Counter:
    """Thread-safe byte counter shared with the stats engine."""
    def __init__(self):
        self.down = 0   # bytes received from remote -> client
        self.up = 0     # bytes sent from client -> remote
        self._l = threading.Lock()

    def add_down(self, n):
        with self._l:
            self.down += n

    def add_up(self, n):
        with self._l:
            self.up += n


class SocksServer:
    """
    Minimal SOCKS5 (CONNECT only) server. Each incoming TCP connection is
    tunnelled through the given paramiko SSH Transport using
    transport.open_channel('direct-tcpip', ...). This mirrors `ssh -D`.
    """

    def __init__(self, transport, host="127.0.0.1", port=1080, counter=None):
        self.transport = transport
        self.host = host
        self.port = port
        self.counter = counter or _Counter()
        self._srv = None
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind((self.host, self.port))
        self._srv.listen(200)
        self._srv.settimeout(1.0)
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        try:
            if self._srv:
                self._srv.close()
        except Exception:
            pass

    def _accept_loop(self):
        while not self._stop.is_set():
            try:
                client, _ = self._srv.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self._handle, args=(client,),
                             daemon=True).start()

    def _handle(self, client):
        try:
            client.settimeout(15)
            # --- greeting ---
            ver, nmethods = client.recv(1), client.recv(1)
            if not ver or ver[0] != 0x05:
                client.close(); return
            client.recv(nmethods[0])
            client.sendall(b"\x05\x00")   # no auth

            # --- request ---
            hdr = client.recv(4)
            if len(hdr) < 4 or hdr[1] != 0x01:   # CONNECT only
                client.sendall(b"\x05\x07\x00\x01" + b"\x00" * 6)
                client.close(); return

            atyp = hdr[3]
            if atyp == 0x01:        # IPv4
                addr = socket.inet_ntoa(client.recv(4))
            elif atyp == 0x03:      # domain
                ln = client.recv(1)[0]
                addr = client.recv(ln).decode("utf-8", "ignore")
            elif atyp == 0x04:      # IPv6
                addr = socket.inet_ntop(socket.AF_INET6, client.recv(16))
            else:
                client.sendall(b"\x05\x08\x00\x01" + b"\x00" * 6)
                client.close(); return
            port = struct.unpack(">H", client.recv(2))[0]

            # --- open SSH channel ---
            try:
                chan = self.transport.open_channel(
                    "direct-tcpip", (addr, port), client.getsockname())
            except Exception:
                client.sendall(b"\x05\x05\x00\x01" + b"\x00" * 6)
                client.close(); return
            if chan is None:
                client.sendall(b"\x05\x05\x00\x01" + b"\x00" * 6)
                client.close(); return

            client.sendall(b"\x05\x00\x00\x01" + b"\x00" * 6)
            client.settimeout(None)
            self._pipe(client, chan)
        except Exception:
            try: client.close()
            except Exception: pass

    def _pipe(self, client, chan):
        try:
            while True:
                r, _, _ = select.select([client, chan], [], [], 30)
                if not r:
                    break
                if client in r:
                    data = client.recv(65536)
                    if not data:
                        break
                    chan.sendall(data)
                    self.counter.add_up(len(data))
                if chan in r:
                    data = chan.recv(65536)
                    if not data:
                        break
                    client.sendall(data)
                    self.counter.add_down(len(data))
        except Exception:
            pass
        finally:
            try: chan.close()
            except Exception: pass
            try: client.close()
            except Exception: pass
