import socket
import struct
import time
from typing import Optional, Tuple
from app.communication.interface import CommunicationInterface, iTantraPacket

class TCPTransport(CommunicationInterface):
    """
    TCP Socket transport implementation for iTantra.
    Supports both compact binary ('binary') and JSON ('json') formats with automatic receiver decoding.
    """
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 65432,
        is_server: bool = False,
        timeout: float = 30.0,
        transport_format: str = "binary"
    ):
        self.host = host
        self.port = port
        self.is_server = is_server
        self.timeout = timeout
        self.transport_format = transport_format
        self.sock: Optional[socket.socket] = None
        self.conn: Optional[socket.socket] = None
        self._init_socket()

    def _init_socket(self):
        if self.is_server:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind((self.host, self.port))
            self.sock.listen(1)
            self.sock.settimeout(self.timeout)
        else:
            # Client socket will connect on demand during send
            pass

    def _recv_exact(self, conn: socket.socket, num_bytes: int) -> bytes:
        data = bytearray()
        while len(data) < num_bytes:
            packet = conn.recv(num_bytes - len(data))
            if not packet:
                raise ConnectionError("Socket connection closed prematurely")
            data.extend(packet)
        return bytes(data)

    def send(self, packet: iTantraPacket, format_type: Optional[str] = None) -> Tuple[bool, float, int]:
        """
        Transmitter: Connects to the receiver, sends length-prefixed packet, receives ACK.
        """
        start_time = time.perf_counter()
        packet.t3_tx_start = time.time()
        
        fmt = format_type or self.transport_format
        raw_bytes = packet.to_bytes(fmt)
        total_len = len(raw_bytes)
        prefix = struct.pack("!I", total_len)
        frame = prefix + raw_bytes
        
        client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_sock.settimeout(self.timeout)
        try:
            client_sock.connect((self.host, self.port))
            client_sock.sendall(frame)
            
            # Wait for 1-byte ACK (0x06: ACK)
            ack = client_sock.recv(1)
            latency = time.perf_counter() - start_time
            if ack == b'\x06':
                return True, latency, len(frame)
            return False, latency, len(frame)
        except Exception as e:
            latency = time.perf_counter() - start_time
            print(f"[!] TCP Send Error to {self.host}:{self.port} - {e}")
            return False, latency, 0
        finally:
            client_sock.close()

    def receive(self, timeout: Optional[float] = None) -> Tuple[Optional[iTantraPacket], float, int]:
        """
        Receiver: Waits for incoming TCP connection, reads length prefix and packet, sends ACK.
        """
        if not self.is_server or not self.sock:
            raise RuntimeError("TCPTransport must be initialized as server to receive.")

        if timeout is not None:
            self.sock.settimeout(timeout)

        start_time = time.perf_counter()
        try:
            conn, addr = self.sock.accept()
            with conn:
                conn.settimeout(self.timeout)
                # Read 4-byte header
                prefix = self._recv_exact(conn, 4)
                msg_len = struct.unpack("!I", prefix)[0]
                
                # Read payload
                payload_bytes = self._recv_exact(conn, msg_len)
                
                # Send 1-byte ACK
                conn.sendall(b'\x06')
                
                t4_rx = time.time()
                latency = time.perf_counter() - start_time
                
                packet = iTantraPacket.from_bytes(payload_bytes)
                packet.t4_rx_finish = t4_rx
                total_bytes = len(prefix) + len(payload_bytes)
                return packet, latency, total_bytes
        except socket.timeout:
            return None, 0.0, 0
        except Exception as e:
            print(f"[!] TCP Receive Error on {self.host}:{self.port} - {e}")
            return None, 0.0, 0

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
