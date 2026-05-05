import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

load_dotenv()

COLLECTION_NAME = "seia-collection"
EMBED_MODEL = "nomic-embed-text"

repo_root = Path(__file__).resolve().parent.parent
policy_paths = [
    repo_root / "policies" / "policy.pdf",
    repo_root / "app" / "policies" / "policy.pdf",
]

PDF_PATH = next((path for path in policy_paths if path.exists()), None)

if PDF_PATH is None:
    expected = ", ".join(str(path) for path in policy_paths)
    raise FileNotFoundError(f"Policy PDF not found. Expected one of: {expected}")

client = QdrantClient(
    url=os.environ["QDRANT_URL"],
    api_key=os.environ.get("QDRANT_API_KEY"),
)

loader = PyPDFLoader(str(PDF_PATH))
pages = loader.load()

splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
chunks = splitter.split_documents(pages)

if not chunks:
    raise ValueError("No content extracted from policy PDF")

texts = [doc.page_content for doc in chunks]

embeddings = OllamaEmbeddings(model=EMBED_MODEL)
vectors = embeddings.embed_documents(texts)

vector_size = len(vectors[0])

if not client.collection_exists(COLLECTION_NAME):
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )

points = []
for i, (doc, vector) in enumerate(zip(chunks, vectors), start=1):
    payload = {
        "text": doc.page_content,
        "source": "Smart Expense & Invoice Auditor (SEIA) Policy.pdf",
        "chunk": i,
    }
    if "page" in doc.metadata:
        payload["page"] = doc.metadata["page"]

    points.append(
        PointStruct(
            id=str(uuid.uuid4()),
            vector=vector,
            payload=payload,
        )
    )

client.upsert(collection_name=COLLECTION_NAME, points=points, wait=True)
print(f"Upserted {len(points)} policy chunks from {PDF_PATH}.")
