import socket, time


def tcp_ping(host, port, timeout=5):
    """Return latency in ms, or -1 on failure."""
    try:
        start = time.time()
        s = socket.create_connection((host, int(port)), timeout=timeout)
        s.close()
        return int((time.time() - start) * 1000)
    except Exception:
        return -1
