import socket
import select
import sys
import threading

def forward_stream(source, destination):
    try:
        while True:
            data = source.recv(8192)
            if not data:
                break
            destination.sendall(data)
    except Exception:
        pass
    finally:
        try:
            source.close()
        except Exception:
            pass
        try:
            destination.close()
        except Exception:
            pass

def handle_client(client_socket):
    try:
        request = client_socket.recv(4096)
        if not request:
            client_socket.close()
            return

        lines = request.split(b"\r\n")
        first_line = lines[0].decode("utf-8", errors="ignore")
        parts = first_line.split()
        if len(parts) < 2:
            client_socket.close()
            return

        method, target = parts[0], parts[1]

        if method.upper() == "CONNECT":
            # HTTPS tunneling
            if ":" in target:
                host, port_str = target.split(":", 1)
                port = int(port_str)
            else:
                host = target
                port = 443

            remote_socket = socket.create_connection((host, port), timeout=15)
            client_socket.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")

            t1 = threading.Thread(target=forward_stream, args=(client_socket, remote_socket), daemon=True)
            t2 = threading.Thread(target=forward_stream, args=(remote_socket, client_socket), daemon=True)
            t1.start()
            t2.start()
            t1.join()
            t2.join()
        else:
            # Plain HTTP proxy
            # target is e.g. http://dl-cdn.alpinelinux.org/alpine/v3.20/main/...
            if target.startswith("http://"):
                url_without_http = target[7:]
                host_part = url_without_http.split("/")[0]
                if ":" in host_part:
                    host, port_str = host_part.split(":", 1)
                    port = int(port_str)
                else:
                    host = host_part
                    port = 80
            else:
                host = "127.0.0.1"
                port = 80

            remote_socket = socket.create_connection((host, port), timeout=15)
            remote_socket.sendall(request)

            t1 = threading.Thread(target=forward_stream, args=(client_socket, remote_socket), daemon=True)
            t2 = threading.Thread(target=forward_stream, args=(remote_socket, client_socket), daemon=True)
            t1.start()
            t2.start()
            t1.join()
            t2.join()
    except Exception as e:
        pass
    finally:
        try:
            client_socket.close()
        except Exception:
            pass

def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", port))
    server.listen(64)
    print(f"Proxy listening on 127.0.0.1:{port}", flush=True)

    while True:
        client_sock, addr = server.accept()
        t = threading.Thread(target=handle_client, args=(client_sock,), daemon=True)
        t.start()

if __name__ == "__main__":
    main()
