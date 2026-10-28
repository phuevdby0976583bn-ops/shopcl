import socket
import threading
import base64
import os
import shutil


class LocalProxyTunnel:
    """Lightweight local HTTP CONNECT tunnel for authenticated proxy support.
    
    Chrome connects to localhost (no auth needed), and this tunnel
    injects proxy credentials before forwarding to the upstream proxy.
    """

    def __init__(self, upstream_host, upstream_port, username, password):
        self.upstream_host = upstream_host
        self.upstream_port = int(upstream_port)
        self.username = username
        self.password = password
        self.server = None
        self.local_port = None
        self._thread = None

    def _get_auth_header(self):
        creds = f"{self.username}:{self.password}".encode()
        encoded = base64.b64encode(creds).decode()
        return f"Proxy-Authorization: Basic {encoded}\r\n"

    def _handle_client(self, client_sock):
        try:
            # Read the CONNECT request from browser
            data = b""
            while b"\r\n\r\n" not in data:
                chunk = client_sock.recv(4096)
                if not chunk:
                    break
                data += chunk

            if not data:
                return

            # Connect to upstream proxy
            upstream_sock = socket.create_connection(
                (self.upstream_host, self.upstream_port), timeout=15
            )

            # Inject auth header into the original request
            first_line_end = data.find(b"\r\n")
            first_line = data[:first_line_end]
            rest = data[first_line_end + 2:]
            auth_header = self._get_auth_header().encode()
            modified_request = first_line + b"\r\n" + auth_header + rest
            upstream_sock.sendall(modified_request)

            # Read upstream response
            response = b""
            while b"\r\n\r\n" not in response:
                chunk = upstream_sock.recv(4096)
                if not chunk:
                    break
                response += chunk

            # Forward response back to browser
            client_sock.sendall(response)

            # Bi-directional data forwarding
            def forward(src, dst):
                try:
                    while True:
                        data = src.recv(8192)
                        if not data:
                            break
                        dst.sendall(data)
                except:
                    pass
                finally:
                    try: src.close()
                    except: pass
                    try: dst.close()
                    except: pass

            t1 = threading.Thread(target=forward, args=(client_sock, upstream_sock), daemon=True)
            t2 = threading.Thread(target=forward, args=(upstream_sock, client_sock), daemon=True)
            t1.start()
            t2.start()
        except Exception:
            try: client_sock.close()
            except: pass

    def _run_server(self):
        while True:
            try:
                client_sock, _ = self.server.accept()
                t = threading.Thread(target=self._handle_client, args=(client_sock,), daemon=True)
                t.start()
            except OSError:
                break

    def start(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(('127.0.0.1', 0))
        self.local_port = self.server.getsockname()[1]
        self.server.listen(50)
        self._thread = threading.Thread(target=self._run_server, daemon=True)
        self._thread.start()
        return self.local_port

    def stop(self):
        if self.server:
            try:
                self.server.close()
            except:
                pass


def create_proxy_tunnel(proxy_url):
    """Start a local tunnel for an authenticated proxy (user:pass@host:port).
    Returns (tunnel, local_port) or (None, None) on failure.
    """
    if '@' not in proxy_url:
        return None, None

    auth, host_port = proxy_url.split('@', 1)
    if ':' not in auth or ':' not in host_port:
        return None, None

    usr, pwd = auth.split(':', 1)
    host, port = host_port.split(':', 1)

    tunnel = LocalProxyTunnel(host, int(port), usr, pwd)
    local_port = tunnel.start()
    return tunnel, local_port


EXTENSION_DIR = "Proxy_Extensions"

def init_extension_dir():
    """Reset the proxy extension directory to a clean state."""
    if os.path.exists(EXTENSION_DIR):
        try:
            shutil.rmtree(EXTENSION_DIR)
        except Exception:
            pass
    try:
        os.makedirs(EXTENSION_DIR, exist_ok=True)
    except:
        pass
