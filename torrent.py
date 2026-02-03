"""
Torrent file parser and metadata extractor.
"""

import hashlib
from pathlib import Path
from typing import List, Optional
from bencode import bdecode, bencode


class TorrentFile:
    """Represents a parsed .torrent file with all metadata."""
    
    def __init__(self, filepath: str):
        self.filepath = Path(filepath)
        with open(filepath, 'rb') as f:
            self.raw_data = f.read()
        
        self.meta_info = bdecode(self.raw_data)
        self._parse_metadata()
    
    def _parse_metadata(self):
        """Extract and store important metadata from torrent."""
        # Get announce URL(s)
        self.announce = self.meta_info.get(b'announce', b'').decode('utf-8')
        self.announce_list = []
        
        if b'announce-list' in self.meta_info:
            for tier in self.meta_info[b'announce-list']:
                for url in tier:
                    self.announce_list.append(url.decode('utf-8'))
        
        # Parse info dictionary
        info = self.meta_info[b'info']
        self.info_dict = info
        
        # Calculate info_hash (SHA1 of bencoded info dict)
        self.info_hash = hashlib.sha1(bencode(info)).digest()
        
        # Piece information
        self.piece_length = info[b'piece length']
        pieces_data = info[b'pieces']
        
        # Split pieces into 20-byte SHA1 hashes
        self.pieces = []
        for i in range(0, len(pieces_data), 20):
            self.pieces.append(pieces_data[i:i+20])
        
        self.total_pieces = len(self.pieces)
        
        # File information (single or multi-file mode)
        if b'length' in info:
            # Single file mode
            self.name = info[b'name'].decode('utf-8')
            self.total_size = info[b'length']
            self.files = [{
                'path': self.name,
                'length': self.total_size
            }]
        else:
            # Multi-file mode
            self.name = info[b'name'].decode('utf-8')
            self.files = []
            self.total_size = 0
            
            for file_info in info[b'files']:
                path_parts = [self.name]
                path_parts.extend([p.decode('utf-8') for p in file_info[b'path']])
                
                file_length = file_info[b'length']
                self.files.append({
                    'path': '/'.join(path_parts),
                    'length': file_length
                })
                self.total_size += file_length
    
    def get_piece_size(self, piece_index: int) -> int:
        """Get size of a specific piece (last piece may be smaller)."""
        if piece_index < 0 or piece_index >= self.total_pieces:
            raise ValueError(f"Invalid piece index: {piece_index}")
        
        if piece_index == self.total_pieces - 1:
            # Last piece
            return self.total_size - (piece_index * self.piece_length)
        else:
            return self.piece_length
    
    def verify_piece(self, piece_index: int, data: bytes) -> bool:
        """Verify piece data against its hash."""
        if piece_index < 0 or piece_index >= self.total_pieces:
            return False
        
        piece_hash = hashlib.sha1(data).digest()
        return piece_hash == self.pieces[piece_index]
    
    def __repr__(self):
        return (f"TorrentFile(name='{self.name}', "
                f"size={self.total_size}, "
                f"pieces={self.total_pieces}, "
                f"announce='{self.announce}')")