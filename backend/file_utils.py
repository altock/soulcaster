"""Utility for handling large files."""
from typing import List

def chunk_file_content(content: str, max_chunk_size: int = 10000) -> List[str]:
    """
    Split a large string into chunks.
    
    Args:
        content (str): The content to split.
        max_chunk_size (int): The maximum size of each chunk.
    
    Returns:
        List[str]: A list of chunks.
    """
    if not content:
        return []
    
    chunks = []
    for i in range(0, len(content), max_chunk_size):
        chunks.append(content[i:i + max_chunk_size])
        
    return chunks

def breakdown_large_file(file_path: str, max_chunk_size: int = 10000) -> List[str]:
    """
    Read a file and breakdown its content into chunks.
    
    Args:
        file_path (str): The path to the file.
        max_chunk_size (int): The maximum size of each chunk.
    
    Returns:
        List[str]: A list of content chunks.
    """
    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    return chunk_file_content(content, max_chunk_size)