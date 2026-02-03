"""
Tracker communication module for getting peer lists.
"""

import random
import struct
import urllib.parse
import urllib.request
from typing import List, Tuple
from bencode import bdecode


class TrackerClient:
    """Handles communication with BitTorrent trackers."""
    
    def __init__(self, torrent):
        self.torrent = torrent
        self.peer_id = self._generate_peer_id()
        self.port = 6881
    
    @staticmethod
    def _generate_peer_id() -> bytes:
        """Generate a random 20-byte peer ID."""
        # Format: -PC0001-<random 12 bytes>
        prefix = b'-PC0001-'
        random_bytes = bytes([random.randint(0, 255) for _ in range(12)])
        return prefix + random_bytes
    
    def get_peers(self, uploaded=0, downloaded=0, left=None) -> List[Tuple[str, int]]:
        """
        Contact tracker and get list of peers.
        Returns list of (ip, port) tuples.
        """
        if left is None:
            left = self.torrent.total_size
        
        # Try announce URL first, then announce-list
        urls = [self.torrent.announce] + self.torrent.announce_list
        
        for url in urls:
            try:
                peers = self._request_peers(url, uploaded, downloaded, left)
                if peers:
                    return peers
            except Exception as e:
                print(f"Failed to get peers from {url}: {e}")
                continue
        
        return []
    
    def _request_peers(self, announce_url: str, uploaded: int, 
                       downloaded: int, left: int) -> List[Tuple[str, int]]:
        """Make HTTP request to tracker."""
        # Build query parameters
        params = {
            'info_hash': self.torrent.info_hash,
            'peer_id': self.peer_id,
            'port': self.port,
            'uploaded': uploaded,
            'downloaded': downloaded,
            'left': left,
            'compact': 1,
            'event': 'started'
        }
        
        # Manually encode info_hash and peer_id (they're binary)
        encoded_params = []
        for key, value in params.items():
            if isinstance(value, bytes):
                encoded_value = urllib.parse.quote(value, safe='')
            else:
                encoded_value = str(value)
            encoded_params.append(f"{key}={encoded_value}")
        
        query_string = '&'.join(encoded_params)
        full_url = f"{announce_url}?{query_string}"
        
        # Make request
        response = urllib.request.urlopen(full_url, timeout=10)
        response_data = response.read()
        
        # Parse response
        tracker_response = bdecode(response_data)
        
        if b'failure reason' in tracker_response:
            raise Exception(tracker_response[b'failure reason'].decode('utf-8'))
        
        # Parse peers
        peers_data = tracker_response.get(b'peers')
        
        if isinstance(peers_data, bytes):
            # Compact format: 6 bytes per peer (4 bytes IP, 2 bytes port)
            return self._parse_compact_peers(peers_data)
        elif isinstance(peers_data, list):
            # Dictionary format
            return self._parse_dict_peers(peers_data)
        else:
            return []
    
    @staticmethod
    def _parse_compact_peers(data: bytes) -> List[Tuple[str, int]]:
        """Parse compact peer format."""
        peers = []
        for i in range(0, len(data), 6):
            if i + 6 > len(data):
                break
            
            ip_bytes = data[i:i+4]
            port_bytes = data[i+4:i+6]
            
            ip = '.'.join(str(b) for b in ip_bytes)
            port = struct.unpack('!H', port_bytes)[0]
            
            peers.append((ip, port))
        
        return peers
    
    @staticmethod
    def _parse_dict_peers(peers_list: list) -> List[Tuple[str, int]]:
        """Parse dictionary peer format."""
        peers = []
        for peer in peers_list:
            ip = peer[b'ip'].decode('utf-8')
            port = peer[b'port']
            peers.append((ip, port))
        
        return peers