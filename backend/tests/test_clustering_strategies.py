import numpy as np

import clustering


def test_agglomerative_smoke():
    embeddings = np.asarray(
        [
            [1.0, 0.0, 0.0],
            [0.9, 0.1, 0.0],
            [0.0, 1.0, 0.0],
        ],
        dtype=np.float32,
    )
    labels = clustering.cluster_agglomerative(embeddings, sim_threshold=0.8)
    assert len(labels) == 3
    # first two should share a cluster at high similarity
    assert labels[0] == labels[1]
    assert labels[0] != labels[2]


def test_centroid_smoke():
    embeddings = np.asarray(
        [
            [1.0, 0.0],
            [0.9, 0.1],
            [0.1, 0.9],
        ],
        dtype=np.float32,
    )
    labels = clustering.cluster_centroid(embeddings, sim_threshold=0.75)
    assert len(labels) == 3
    assert labels[0] == labels[1]
    assert labels[2] != labels[0]


def test_centroid_normalizes_centroids():
    embeddings = np.asarray(
        [
            [1.0, 0.0],
            [0.8, 0.6],
            [0.6, 0.8],
        ],
        dtype=np.float32,
    )
    labels = clustering.cluster_centroid(embeddings, sim_threshold=0.8)
    assert len(labels) == 3
    assert labels[0] == labels[1] == labels[2]


def test_vector_like_smoke():
    embeddings = np.asarray(
        [
            [1.0, 0.0],
            [0.95, 0.05],
            [0.2, 0.8],
        ],
        dtype=np.float32,
    )
    labels = clustering.cluster_vector_like(embeddings, sim_threshold=0.8)
    assert len(labels) == 3
    assert labels[0] == labels[1]
    assert labels[2] != labels[0]


def test_cluster_issues_uses_embed_fn():
    mock_embeddings = np.asarray(
        [
            [1.0, 0.0, 0.0],
            [0.9, 0.1, 0.0],
            [0.0, 1.0, 0.0],
        ],
        dtype=np.float32,
    )

    def fake_embed(texts):
        """
        Provide a mock embedding function that returns a pre-defined embeddings array for exactly three input texts.
        
        Asserts that the input sequence contains three items and returns the module-level `mock_embeddings` value.
        
        Parameters:
            texts (Sequence[str]): Sequence of exactly three texts to embed.
        
        Returns:
            numpy.ndarray: The pre-defined `mock_embeddings` array.
        """
        assert len(texts) == 3
        return mock_embeddings

    issues = [
        {"title": "A", "body": "alpha"},
        {"title": "B", "body": "beta"},
        {"title": "C", "body": "gamma"},
    ]
    result = clustering.cluster_issues(
        issues,
        method="agglomerative",
        sim_threshold=0.8,
        min_cluster_size=2,
        embed_fn=fake_embed,
    )

    assert list(result["labels"]) == [0, 0, 1]
    assert result["clusters"] == [[0, 1]]
    assert result["singletons"] == [2]
    assert len(result["texts"]) == 3
