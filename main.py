#!/usr/bin/env python3
"""
BitTorrent Client - Main CLI Entry Point
A fully functional BitTorrent client implementation.
"""

import argparse
import asyncio
import sys
from pathlib import Path
from downloader import TorrentDownloader


def print_banner():
    """Print application banner."""
    banner = """
    ╔════════════════════════════════════════════════════════╗
    ║                                                        ║
    ║           BitTorrent Client v1.0                       ║
    ║           Educational P2P File Sharing                 ║
    ║                                                        ║
    ╚════════════════════════════════════════════════════════╝
    """
    print(banner)


def validate_torrent_file(filepath: str) -> bool:
    """Validate that torrent file exists and is readable."""
    path = Path(filepath)
    
    if not path.exists():
        print(f"Error: Torrent file '{filepath}' not found")
        return False
    
    if not path.is_file():
        print(f"Error: '{filepath}' is not a file")
        return False
    
    if path.suffix != '.torrent':
        print(f"Warning: File doesn't have .torrent extension")
    
    return True


async def download_torrent(torrent_file: str, output_file: str, 
                          max_peers: int, verbose: bool):
    """Download a torrent file."""
    try:
        # Validate input
        if not validate_torrent_file(torrent_file):
            return False
        
        # Create downloader
        downloader = TorrentDownloader(
            torrent_file=torrent_file,
            output_file=output_file,
            max_peers=max_peers
        )
        
        # Start download
        await downloader.download()
        return True
        
    except KeyboardInterrupt:
        print("\n\nDownload interrupted by user")
        return False
    except Exception as e:
        print(f"\nError during download: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='BitTorrent Client - Download files using BitTorrent protocol',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s file.torrent                          # Download to default output
  %(prog)s file.torrent -o movie.mp4             # Specify output filename
  %(prog)s file.torrent -p 10                    # Use up to 10 peers
  %(prog)s file.torrent -o output.bin -p 8 -v    # Verbose mode with 8 peers

Note: This is an educational implementation. Use responsibly and only
download content you have rights to access.
        """
    )
    
    parser.add_argument(
        'torrent',
        help='Path to .torrent file'
    )
    
    parser.add_argument(
        '-o', '--output',
        default='downloaded_file.bin',
        help='Output filename (default: downloaded_file.bin)'
    )
    
    parser.add_argument(
        '-p', '--peers',
        type=int,
        default=5,
        help='Maximum number of peers to connect to (default: 5)'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='BitTorrent Client v1.0'
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    # Print banner
    print_banner()
    
    # Validate peers
    if args.peers < 1 or args.peers > 50:
        print("Error: Number of peers must be between 1 and 50")
        sys.exit(1)
    
    # Run download
    success = asyncio.run(download_torrent(
        torrent_file=args.torrent,
        output_file=args.output,
        max_peers=args.peers,
        verbose=args.verbose
    ))
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()