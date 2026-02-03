# BitTorrent Client

A **minimal, fully-functional BitTorrent (BEP-0003) client** built from scratch in Python using asynchronous I/O. This project focuses on **protocol-level understanding**, **async networking**, and **data integrity**, with zero external dependencies.

**Tech Stack:** Python 3.7+ • asyncio • TCP Sockets • SHA-1 • Binary Protocol Parsing

---

## Highlights

* Implements the BitTorrent wire protocol directly from spec (no libraries)
* Concurrent downloads from multiple peers using `asyncio`
* SHA-1 verification of every piece with automatic retry on corruption
* Real-time CLI progress, speed, and ETA
* Pure Python standard library only

---

## Architecture Overview

```
bencode.py          → Encodes/decodes bencoded torrent files
torrent.py          → Parses .torrent metadata and piece hashes
tracker.py          → Communicates with HTTP trackers to fetch peers
peer.py             → TCP peer connections & BitTorrent wire protocol
piece_manager.py    → Piece scheduling, verification, and assembly
downloader.py       → Async orchestration of multi-peer downloads
main.py             → CLI entry point and user interface
```

---

## Features

### Protocol & Networking

* Bencode encoder/decoder
* Info-hash generation
* Tracker requests (compact peer format)
* Peer handshake and bitfield exchange
* Message handling: choke, unchoke, interested, have, request, piece

### Download Engine

* Multi-peer piece scheduling
* 16KB block-based requests
* Piece reassembly and hash verification
* Async concurrent downloads

### CLI

* Colored progress output
* Live speed and ETA
* Verbose logging mode

---

## Usage

```bash
git clone https://github.com/yourusername/bittorrent-client.git
cd bittorrent-client
python main.py file.torrent
```

Optional flags:

```bash
-o output.file   # specify output
-p 8             # max peers
-v               # verbose logging
```

---

## Protocol Notes

**Handshake:**

```
<pstrlen><pstr><reserved><info_hash><peer_id>
```

**Messages:**

```
<length><id><payload>
0=choke  1=unchoke  2=interested  4=have
5=bitfield  6=request  7=piece
```

**Piece Verification:**

```python
hashlib.sha1(piece_data).digest() == expected_hash
```

---

## Limitations

* No DHT / magnet links
* No upload or seeding
* No encryption
* No resume support

(Intentionally omitted to keep focus on core protocol mechanics.)

---

## Legal

Educational use only. Download only content you have legal rights to.

---

## License

MIT License

---

Built to demonstrate low-level networking, async programming, and distributed systems fundamentals.
