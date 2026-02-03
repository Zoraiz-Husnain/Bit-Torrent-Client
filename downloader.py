"""
Main download orchestrator using async/await.
Coordinates peers, pieces, and download process.
"""

import asyncio
import time
from typing import List
from torrent import TorrentFile
from tracker import TrackerClient
from peer import PeerConnection
from piece_manager import PieceManager


class DownloadStats:
    """Track download statistics in real-time"""
    
    def __init__(self, total_size):
        self.total_size = total_size
        self.downloaded_bytes = 0
        self.start_time = time.time()
        self.last_update = self.start_time
        self.last_bytes = 0
    
    def update(self, new_bytes):
        """Update downloaded bytes"""
        self.downloaded_bytes = new_bytes
    
    def get_speed(self):
        """Get current download speed in bytes/sec"""
        elapsed = time.time() - self.last_update
        if elapsed < 0.1:  # Avoid division by zero
            return 0
        
        bytes_diff = self.downloaded_bytes - self.last_bytes
        speed = bytes_diff / elapsed
        
        self.last_bytes = self.downloaded_bytes
        self.last_update = time.time()
        
        return speed
    
    def format_speed(self, speed):
        """Format speed to human readable"""
        if speed < 1024:
            return f"{speed:.1f} B/s"
        elif speed < 1024 * 1024:
            return f"{speed/1024:.1f} KB/s"
        else:
            return f"{speed/(1024*1024):.2f} MB/s"
    
    def get_eta(self, speed):
        """Calculate estimated time remaining"""
        if speed == 0:
            return "calculating..."
        
        remaining_bytes = self.total_size - self.downloaded_bytes
        eta_seconds = remaining_bytes / speed
        
        if eta_seconds < 60:
            return f"{int(eta_seconds)}s"
        elif eta_seconds < 3600:
            return f"{int(eta_seconds/60)}m {int(eta_seconds%60)}s"
        else:
            hours = int(eta_seconds / 3600)
            minutes = int((eta_seconds % 3600) / 60)
            return f"{hours}h {minutes}m"
    
    def get_progress_percent(self):
        """Get download progress percentage"""
        return (self.downloaded_bytes / self.total_size) * 100


class TorrentDownloader:
    """Main downloader class that orchestrates the download."""
    
    def __init__(self, torrent_file: str, output_file: str, max_peers: int = 5):
        self.torrent = TorrentFile(torrent_file)
        self.output_file = output_file
        self.max_peers = max_peers
        
        self.tracker = TrackerClient(self.torrent)
        self.piece_manager = PieceManager(self.torrent)
        self.peers: List[PeerConnection] = []
        
        print(f"\n{'='*60}")
        print(f"BitTorrent Client - Starting Download")
        print(f"{'='*60}")
        print(f"Torrent: {self.torrent.name}")
        print(f"Size: {self._format_size(self.torrent.total_size)}")
        print(f"Pieces: {self.torrent.total_pieces}")
        print(f"Piece size: {self._format_size(self.torrent.piece_length)}")
        print(f"{'='*60}\n")
    
    @staticmethod
    def _format_size(bytes_size: int) -> str:
        """Format byte size to human readable."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.2f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.2f} TB"
    
    async def connect_to_peers(self):
        """Get peers from tracker and establish connections."""
        print("Contacting tracker...")
        peer_list = self.tracker.get_peers()
        
        if not peer_list:
            raise Exception("No peers available from tracker")
        
        print(f"Found {len(peer_list)} peers from tracker")
        print(f"Attempting to connect to {min(self.max_peers, len(peer_list))} peers...\n")
        
        # Try to connect to multiple peers
        tasks = []
        for ip, port in peer_list[:self.max_peers * 2]:  # Try more than needed
            peer = PeerConnection(
                ip, port,
                self.torrent.info_hash,
                self.tracker.peer_id
            )
            tasks.append(self._connect_and_handshake(peer))
        
        # Wait for connections
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Keep successfully connected peers
        self.peers = [peer for peer in results if isinstance(peer, PeerConnection)]
        
        if not self.peers:
            raise Exception("Failed to connect to any peers")
        
        print(f"✓ Connected to {len(self.peers)} peers\n")
    
    async def _connect_and_handshake(self, peer: PeerConnection) -> PeerConnection:
        """Connect to peer and perform handshake."""
        if await peer.connect():
            if await peer.handshake():
                await peer.send_interested()
                return peer
        
        await peer.close()
        return None
    
    async def download_from_peer(self, peer: PeerConnection):
        """Download pieces from a single peer."""
        try:
            while not self.piece_manager.is_complete():
                # Get next piece to download
                piece_idx = await self.piece_manager.get_next_piece(peer)
                
                if piece_idx is None:
                    # No more pieces available for this peer
                    await asyncio.sleep(1)
                    continue
                
                # Download the piece
                await self.piece_manager.download_piece_from_peer(peer, piece_idx)
                
        except Exception as e:
            print(f"Error with peer {peer.ip}:{peer.port} - {e}")
        finally:
            await peer.close()
    
    async def download(self):
        """Main download method."""
        start_time = time.time()
        
        # Connect to peers
        await self.connect_to_peers()
        
        # Start downloading from all peers concurrently
        print("Starting download...\n")
        
        download_tasks = [
            self.download_from_peer(peer)
            for peer in self.peers
        ]
        
        # Also monitor progress
        progress_task = self.monitor_progress()
        
        # Wait for all downloads to complete
        await asyncio.gather(progress_task, *download_tasks)
        
        # Write to file
        if self.piece_manager.is_complete():
            await self.piece_manager.write_to_file(self.output_file)
            
            # Show final statistics
            elapsed = time.time() - start_time
            avg_speed = self.torrent.total_size / elapsed if elapsed > 0 else 0
            
            print(f"\n{'='*60}")
            print("📊 Download Statistics:")
            print(f"  Total Size: {self._format_size(self.torrent.total_size)}")
            print(f"  Time Taken: {int(elapsed//60)}m {int(elapsed%60)}s")
            print(f"  Average Speed: {self._format_size(avg_speed)}/s")
            print(f"  Peers Used: {len(self.peers)}")
            print(f"  Pieces: {self.torrent.total_pieces}")
            print(f"{'='*60}")
            print("✅ Download Complete!")
            print(f"{'='*60}\n")
        else:
            print("\nDownload incomplete - some pieces missing")
    
    async def monitor_progress(self):
        """Monitor and display download progress with speed and ETA"""
        stats = DownloadStats(self.torrent.total_size)
        
        while not self.piece_manager.is_complete():
            await asyncio.sleep(2)
            
            # Calculate downloaded bytes
            downloaded_bytes = len(self.piece_manager.downloaded_pieces) * self.torrent.piece_length
            stats.update(downloaded_bytes)
            
            # Get stats
            speed = stats.get_speed()
            progress = stats.get_progress_percent()
            eta = stats.get_eta(speed)
            
            # Display
            downloaded = len(self.piece_manager.downloaded_pieces)
            total = self.torrent.total_pieces
            
            print(f"📊 Progress: {progress:.1f}% ({downloaded}/{total} pieces) | "
                  f"Speed: {stats.format_speed(speed)} | ETA: {eta}")
    
    def start(self):
        """Start the download process."""
        asyncio.run(self.download())


async def main():
    """Example usage."""
    # Example: download a torrent file
    downloader = TorrentDownloader(
        torrent_file='test.torrent',
        output_file='downloaded_file.bin',
        max_peers=5
    )
    
    await downloader.download()


if __name__ == '__main__':
    asyncio.run(main())