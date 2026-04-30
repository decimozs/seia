import os

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

load_dotenv()

client = QdrantClient(
    url=os.environ["QDRANT_URL"],
    api_key=os.environ["QDRANT_API_KEY"],
)

COLLECTION_NAME = "seia-collection"
EMBED_MODEL = "all-MiniLM-L6-v2"

embedder = SentenceTransformer(EMBED_MODEL)

if not client.collection_exists(COLLECTION_NAME):
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=384, distance=Distance.COSINE),
    )

policies = [
    {"id": 1, "text": "Max Meal Expense: 500 PHP."},
    {"id": 2, "text": "Software subscriptions MUST have a 'justification' provided."},
    {
        "id": 3,
        "text": "Travel expenses > 2000 PHP MUST be set to 'pending_review'.",
    },
]

points = [
    PointStruct(
        id=p["id"],
        vector=embedder.encode(p["text"]).tolist(),
        payload={"text": p["text"]},
    )
    for p in policies
]

client.upsert(collection_name=COLLECTION_NAME, points=points)
print(f"Indexed {len(points)} policy chunks.")
