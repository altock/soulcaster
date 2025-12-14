import numpy as np

import clustering


def test_agglomerative_quality_grouping():
    """
    Regression guard: two clear themes should cluster together at 0.72+.
    Embeddings are synthetic but arranged to mimic two topical groups.
    """
    issues = [
        {"title": "Export fails", "body": "export crashes on safari"},
        {"title": "Export timeout", "body": "export hangs on chrome"},
        {"title": "Login broken", "body": "oauth login fails"},
        {"title": "Auth error", "body": "token invalid on refresh"},
    ]

    # Two groups: export (~vector near x-axis) vs auth (~vector near y-axis)
    mock_embeddings = np.asarray(
        [
            [0.99, 0.0, 0.0],
            [0.97, 0.02, 0.0],
            [0.0, 0.99, 0.01],
            [0.05, 0.98, 0.0],
        ],
        dtype=np.float32,
    )

    def fake_embed(texts):
        """
        Provide a predefined embedding array for the given input texts (used in tests).
        
        Parameters:
            texts (Sequence[str]): Input texts whose length must match the number of rows in `mock_embeddings`.
        
        Returns:
            numpy.ndarray: The predefined `mock_embeddings` array.
        
        Raises:
            AssertionError: If `len(texts)` does not equal `len(mock_embeddings)`.
        """
        assert len(texts) == len(mock_embeddings)
        return mock_embeddings

    result = clustering.cluster_issues(
        issues,
        method="agglomerative",
        sim_threshold=0.72,
        min_cluster_size=2,
        embed_fn=fake_embed,
    )

    # Expect two clusters of size 2, no singletons
    assert sorted([sorted(group) for group in result["clusters"]]) == [[0, 1], [2, 3]]
    assert result["singletons"] == []
    assert len(result["labels"]) == len(issues)