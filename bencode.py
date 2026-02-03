"""
Bencode encoding/decoding implementation for BitTorrent protocol.
Supports integers, strings, lists, and dictionaries.
"""

from collections import OrderedDict


class BencodeDecoder:
    """Decodes bencoded data into Python objects."""
    
    def __init__(self, data: bytes):
        if not isinstance(data, bytes):
            raise TypeError("Data must be bytes")
        self.data = data
        self.index = 0
    
    def decode(self):
        """Main decode method - returns decoded Python object."""
        if self.index >= len(self.data):
            raise ValueError("Unexpected end of data")
        
        c = chr(self.data[self.index])
        
        if c == 'i':
            return self._decode_int()
        elif c == 'l':
            return self._decode_list()
        elif c == 'd':
            return self._decode_dict()
        elif c.isdigit():
            return self._decode_string()
        else:
            raise ValueError(f"Invalid bencode data at position {self.index}")
    
    def _decode_int(self) -> int:
        """Decode integer: i<number>e"""
        self.index += 1  # Skip 'i'
        end = self.data.find(b'e', self.index)
        if end == -1:
            raise ValueError("Unterminated integer")
        
        num_str = self.data[self.index:end]
        self.index = end + 1
        
        return int(num_str)
    
    def _decode_string(self) -> bytes:
        """Decode string: <length>:<data>"""
        colon = self.data.find(b':', self.index)
        if colon == -1:
            raise ValueError("Invalid string encoding")
        
        length = int(self.data[self.index:colon])
        self.index = colon + 1
        
        if self.index + length > len(self.data):
            raise ValueError("String length exceeds data")
        
        string = self.data[self.index:self.index + length]
        self.index += length
        
        return string
    
    def _decode_list(self) -> list:
        """Decode list: l<items>e"""
        self.index += 1  # Skip 'l'
        items = []
        
        while self.index < len(self.data) and chr(self.data[self.index]) != 'e':
            items.append(self.decode())
        
        if self.index >= len(self.data):
            raise ValueError("Unterminated list")
        
        self.index += 1  # Skip 'e'
        return items
    
    def _decode_dict(self) -> OrderedDict:
        """Decode dictionary: d<key><value>...e"""
        self.index += 1  # Skip 'd'
        items = OrderedDict()
        
        while self.index < len(self.data) and chr(self.data[self.index]) != 'e':
            key = self.decode()
            if not isinstance(key, bytes):
                raise ValueError("Dictionary keys must be strings")
            
            value = self.decode()
            items[key] = value
        
        if self.index >= len(self.data):
            raise ValueError("Unterminated dictionary")
        
        self.index += 1  # Skip 'e'
        return items


class BencodeEncoder:
    """Encodes Python objects into bencoded format."""
    
    @staticmethod
    def encode(obj) -> bytes:
        """Main encode method - returns bencoded bytes."""
        if isinstance(obj, int):
            return BencodeEncoder._encode_int(obj)
        elif isinstance(obj, bytes):
            return BencodeEncoder._encode_bytes(obj)
        elif isinstance(obj, str):
            return BencodeEncoder._encode_bytes(obj.encode('utf-8'))
        elif isinstance(obj, list):
            return BencodeEncoder._encode_list(obj)
        elif isinstance(obj, dict) or isinstance(obj, OrderedDict):
            return BencodeEncoder._encode_dict(obj)
        else:
            raise TypeError(f"Cannot encode type {type(obj)}")
    
    @staticmethod
    def _encode_int(num: int) -> bytes:
        """Encode integer: i<number>e"""
        return f"i{num}e".encode('utf-8')
    
    @staticmethod
    def _encode_bytes(data: bytes) -> bytes:
        """Encode string: <length>:<data>"""
        return f"{len(data)}:".encode('utf-8') + data
    
    @staticmethod
    def _encode_list(lst: list) -> bytes:
        """Encode list: l<items>e"""
        result = b'l'
        for item in lst:
            result += BencodeEncoder.encode(item)
        result += b'e'
        return result
    
    @staticmethod
    def _encode_dict(dct: dict) -> bytes:
        """Encode dictionary: d<key><value>...e"""
        result = b'd'
        # Sort keys as per bencode spec
        for key in sorted(dct.keys()):
            if isinstance(key, str):
                key = key.encode('utf-8')
            result += BencodeEncoder.encode(key)
            result += BencodeEncoder.encode(dct[key])
        result += b'e'
        return result


def bdecode(data: bytes):
    """Convenience function to decode bencoded data."""
    return BencodeDecoder(data).decode()


def bencode(obj) -> bytes:
    """Convenience function to encode object to bencode."""
    return BencodeEncoder.encode(obj)