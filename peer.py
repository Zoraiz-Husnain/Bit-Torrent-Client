"""
Peer wire protocol implementation for BitTorrent.
Handles handshake, messages, and piece downloading.
"""

import asyncio
import struct
from typing import Optional


# Message IDs
MSG_CHOKE = 0
MSG_UNCHOKE = 1
MSG_INTERESTED = 2
MSG_NOT_INTERESTED = 3
MSG_HAVE = 4
MSG_BITFIELD = 5
MSG_REQUEST = 6
MSG_PIECE = 7
MSG_CANCEL = 8

BLOCK_SIZE = 16384  # 16 KB standard block size


class PeerMessage:
    """Represents a BitTorrent peer protocol message."""
    
    def __init__(self, msg_id: int, payload: bytes = b''):
        self.msg_id = msg_id
        self.payload = payload
    
    def to_bytes(self) -> bytes:
        """Convert message to wire format."""
        length = 1 + len(self.payload)
        return struct.pack('!IB', length, self.msg_id) + self.payload
    
    @staticmethod
    def keepalive() -> bytes:
        """Create keepalive message (length 0)."""
        return struct.pack('!I', 0)


class PeerConnection:
    """Manages connection to a single peer."""
    
    def __init__(self, ip: str, port: int, info_hash: bytes, peer_id: bytes):
        self.ip = ip
        self.port = port
        self.info_hash = info_hash
        self.peer_id = peer_id
        
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        
        self.am_choking = True
        self.am_interested = False
        self.peer_choking = True
        self.peer_interested = False
        
        self.bitfield = None
        self.connected = False
    
    async def connect(self, timeout: int = 10) -> bool:
        """Establish TCP connection to peer."""
        try:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.ip, self.port),
                timeout=timeout
            )
            self.connected = True
            return True
        except Exception as e:
            print(f"Failed to connect to {self.ip}:{self.port} - {e}")
            return False
    
    async def handshake(self) -> bool:
        """Perform BitTorrent handshake."""
        # Handshake format:
        # <pstrlen><pstr><reserved><info_hash><peer_id>
        pstr = b'BitTorrent protocol'
        pstrlen = len(pstr)
        reserved = b'\x00' * 8
        
        handshake_msg = (
            struct.pack('!B', pstrlen) +
            pstr +
            reserved +
            self.info_hash +
            self.peer_id
        )
        
        try:
            # Send handshake
            self.writer.write(handshake_msg)
            await self.writer.drain()
            
            # Receive handshake response
            response = await asyncio.wait_for(
                self.reader.read(68),
                timeout=10
            )
            
            if len(response) != 68:
                return False
            
            # Verify protocol and info_hash
            recv_pstrlen = response[0]
            recv_pstr = response[1:1+recv_pstrlen]
            recv_info_hash = response[28:48]
            
            if recv_pstr != pstr or recv_info_hash != self.info_hash:
                return False
            
            return True
            
        except Exception as e:
            print(f"Handshake failed with {self.ip}:{self.port} - {e}")
            return False
    
    async def send_interested(self):
        """Send interested message to peer."""
        msg = PeerMessage(MSG_INTERESTED)
        self.writer.write(msg.to_bytes())
        await self.writer.drain()
        self.am_interested = True
    
    async def send_not_interested(self):
        """Send not interested message."""
        msg = PeerMessage(MSG_NOT_INTERESTED)
        self.writer.write(msg.to_bytes())
        await self.writer.drain()
        self.am_interested = False
    
    async def request_block(self, piece_index: int, begin: int, length: int):
        """Request a block from peer."""
        payload = struct.pack('!III', piece_index, begin, length)
        msg = PeerMessage(MSG_REQUEST, payload)
        
        self.writer.write(msg.to_bytes())
        await self.writer.drain()
    
    async def read_message(self) -> Optional[tuple]:
        """
        Read next message from peer.
        Returns (msg_id, payload) or None.
        """
        try:
            # Read message length
            length_bytes = await asyncio.wait_for(
                self.reader.read(4),
                timeout=30
            )
            
            if len(length_bytes) != 4:
                return None
            
            length = struct.unpack('!I', length_bytes)[0]
            
            if length == 0:
                # Keepalive
                return (None, b'')
            
            # Read message ID
            msg_id_byte = await self.reader.read(1)
            msg_id = msg_id_byte[0]
            
            # Read payload
            payload_length = length - 1
            payload = b''
            
            if payload_length > 0:
                payload = await self.reader.read(payload_length)
            
            return (msg_id, payload)
            
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            print(f"Error reading message: {e}")
            return None
    
    async def handle_messages(self):
        """Handle incoming messages from peer."""
        while self.connected:
            msg = await self.read_message()
            
            if msg is None:
                break
            
            msg_id, payload = msg
            
            if msg_id is None:
                # Keepalive
                continue
            elif msg_id == MSG_CHOKE:
                self.peer_choking = True
            elif msg_id == MSG_UNCHOKE:
                self.peer_choking = False
            elif msg_id == MSG_INTERESTED:
                self.peer_interested = True
            elif msg_id == MSG_NOT_INTERESTED:
                self.peer_interested = False
            elif msg_id == MSG_HAVE:
                piece_index = struct.unpack('!I', payload)[0]
                if self.bitfield:
                    self.bitfield[piece_index] = 1
            elif msg_id == MSG_BITFIELD:
                self.bitfield = [int(b) for byte in payload for b in f"{byte:08b}"]
            elif msg_id == MSG_PIECE:
                # Let piece manager handle this
                pass
    
    def has_piece(self, piece_index: int) -> bool:
        """Check if peer has a specific piece."""
        if not self.bitfield or piece_index >= len(self.bitfield):
            return False
        return self.bitfield[piece_index] == 1
    
    async def close(self):
        """Close connection to peer."""
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
        self.connected = False
    
    def __repr__(self):
        return f"Peer({self.ip}:{self.port}, connected={self.connected})"