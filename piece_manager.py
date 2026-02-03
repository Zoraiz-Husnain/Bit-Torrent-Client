"""
Manages piece downloading, verification, and file assembly.
"""

import asyncio
import struct
from pathlib import Path
from typing import Dict, List, Set
from peer import PeerConnection, MSG_PIECE, BLOCK_SIZE


class ColoredProgress:
    """Add colored terminal output for better UX"""
    
    # ANSI color codes
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    RESET = '\033[0m'
    
    @staticmethod
    def progress_bar(current, total, bar_length=40):
        """Create a visual progress bar"""
        percent = current / total
        filled = int(bar_length * percent)
        bar = '█' * filled + '░' * (bar_length - filled)
        
        return f"{ColoredProgress.BLUE}[{bar}]{ColoredProgress.RESET} {percent*100:.1f}%"
    
    @staticmethod
    def success(msg):
        return f"{ColoredProgress.GREEN}✓{ColoredProgress.RESET} {msg}"
    
    @staticmethod
    def error(msg):
        return f"{ColoredProgress.RED}✗{ColoredProgress.RESET} {msg}"
    
    @staticmethod
    def info(msg):
        return f"{ColoredProgress.BLUE}ℹ{ColoredProgress.RESET} {msg}"


class Piece:
    """Represents a single piece being downloaded."""
    
    def __init__(self, index: int, size: int, piece_hash: bytes):
        self.index = index
        self.size = size
        self.hash = piece_hash
        self.blocks: Dict[int, bytes] = {}
        self.downloaded = 0
        self.complete = False
    
    def add_block(self, begin: int, data: bytes):
        """Add a block to this piece."""
        if begin not in self.blocks:
            self.blocks[begin] = data
            self.downloaded += len(data)
    
    def is_complete(self) -> bool:
        """Check if all blocks have been downloaded."""
        return self.downloaded >= self.size
    
    def get_data(self) -> bytes:
        """Assemble all blocks into complete piece data."""
        if not self.is_complete():
            return b''
        
        # Sort blocks by offset and concatenate
        sorted_blocks = sorted(self.blocks.items())
        return b''.join(data for _, data in sorted_blocks)
    
    def get_next_request(self) -> tuple:
        """Get next block to request (offset, length)."""
        # Find first missing block
        offset = 0
        while offset < self.size:
            if offset not in self.blocks:
                length = min(BLOCK_SIZE, self.size - offset)
                return (offset, length)
            offset += BLOCK_SIZE
        
        return None


class PieceManager:
    """Manages downloading and assembly of all pieces."""
    
    def __init__(self, torrent):
        self.torrent = torrent
        self.pieces: Dict[int, Piece] = {}
        self.pending_pieces: Set[int] = set(range(torrent.total_pieces))
        self.downloaded_pieces: Set[int] = set()
        self.lock = asyncio.Lock()
        
        # Initialize all pieces
        for i in range(torrent.total_pieces):
            size = torrent.get_piece_size(i)
            piece_hash = torrent.pieces[i]
            self.pieces[i] = Piece(i, size, piece_hash)
    
    async def get_next_piece(self, peer: PeerConnection) -> int:
        """Get next piece index to download from this peer."""
        async with self.lock:
            for piece_idx in self.pending_pieces:
                if peer.has_piece(piece_idx):
                    self.pending_pieces.remove(piece_idx)
                    return piece_idx
            return None
    
    async def add_block(self, piece_index: int, begin: int, data: bytes):
        """Add downloaded block data to piece with colored output."""
        async with self.lock:
            if piece_index in self.pieces:
                piece = self.pieces[piece_index]
                piece.add_block(begin, data)
                
                # Check if piece is complete
                if piece.is_complete() and not piece.complete:
                    # Verify piece hash
                    piece_data = piece.get_data()
                    if self.torrent.verify_piece(piece_index, piece_data):
                        piece.complete = True
                        self.downloaded_pieces.add(piece_index)
                        
                        # Colored progress output
                        progress_bar = ColoredProgress.progress_bar(
                            len(self.downloaded_pieces), 
                            self.torrent.total_pieces
                        )
                        print(f"{ColoredProgress.success(f'Piece {piece_index}/{self.torrent.total_pieces}')} "
                              f"{progress_bar}")
                        return True
                    else:
                        # Hash mismatch - re-download with colored error
                        print(ColoredProgress.error(f"Piece {piece_index} hash mismatch, retrying"))
                        piece.blocks.clear()
                        piece.downloaded = 0
                        self.pending_pieces.add(piece_index)
                        return False
            return False
    
    async def download_piece_from_peer(self, peer: PeerConnection, piece_index: int):
        """Download a complete piece from a peer."""
        piece = self.pieces[piece_index]
        
        # Request all blocks for this piece
        while not piece.is_complete():
            if peer.peer_choking:
                # Wait to be unchoked
                await asyncio.sleep(0.5)
                continue
            
            next_request = piece.get_next_request()
            if not next_request:
                break
            
            begin, length = next_request
            
            try:
                # Send request
                await peer.request_block(piece_index, begin, length)
                
                # Wait for response
                msg = await asyncio.wait_for(peer.read_message(), timeout=10)
                
                if msg is None:
                    break
                
                msg_id, payload = msg
                
                if msg_id == MSG_PIECE:
                    # Parse piece message
                    recv_index = struct.unpack('!I', payload[0:4])[0]
                    recv_begin = struct.unpack('!I', payload[4:8])[0]
                    block_data = payload[8:]
                    
                    if recv_index == piece_index and recv_begin == begin:
                        await self.add_block(piece_index, begin, block_data)
                
            except asyncio.TimeoutError:
                print(f"Timeout requesting block from {peer.ip}:{peer.port}")
                break
            except Exception as e:
                print(f"Error downloading block: {e}")
                break
    
    def is_complete(self) -> bool:
        """Check if all pieces have been downloaded."""
        return len(self.downloaded_pieces) == self.torrent.total_pieces
    
    def get_progress(self) -> float:
        """Get download progress as percentage."""
        return (len(self.downloaded_pieces) / self.torrent.total_pieces) * 100
    
    async def write_to_file(self, output_path: str):
        """Write all downloaded pieces to file."""
        output_file = Path(output_path)
        
        print(f"\n{ColoredProgress.info('Writing to file')} {output_file}...")
        
        with open(output_file, 'wb') as f:
            for piece_idx in range(self.torrent.total_pieces):
                if piece_idx in self.downloaded_pieces:
                    piece = self.pieces[piece_idx]
                    piece_data = piece.get_data()
                    f.write(piece_data)
        
        print(ColoredProgress.success(f"File saved: {output_file}"))