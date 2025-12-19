import os
import pytest
from backend.file_utils import chunk_file_content, breakdown_large_file

def test_chunk_file_content():
    content = "a" * 10500
    chunks = chunk_file_content(content, max_chunk_size=5000)
    assert len(chunks) == 3
    assert len(chunks[0]) == 5000
    assert len(chunks[1]) == 5000
    assert len(chunks[2]) == 500

def test_breakdown_large_file(tmp_path):
    d = tmp_path / "subdir"
    d.mkdir()
    p = d / "hello.txt"
    content = "a" * 10500
    p.write_text(content, encoding='utf-8')
    
    chunks = breakdown_large_file(str(p), max_chunk_size=5000)
    assert len(chunks) == 3
    assert len(chunks[0]) == 5000
    assert len(chunks[1]) == 5000
    assert len(chunks[2]) == 500