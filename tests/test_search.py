from app.services.search import cosine_similarity, embed_text


def test_semantically_related_text_scores_higher():
    query = embed_text("Acme invoice consulting")
    related = embed_text("Acme consulting invoice total")
    unrelated = embed_text("warehouse bananas rainfall")
    assert cosine_similarity(query, related) > cosine_similarity(query, unrelated)
