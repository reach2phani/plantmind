import os
from dotenv import load_dotenv
from pinecone import Pinecone
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

load_dotenv()

model = SentenceTransformer("all-MiniLM-L6-v2")

pc    = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index(os.getenv("PINECONE_INDEX"))

splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    separators=["\n\n", "\n", ". ", " "]
)

def embed_document(doc_id, file_path, metadata):
    print(f"Embedding: {file_path}")
    ext = file_path.rsplit(".", 1)[-1].lower()

    if ext == "pdf":
        try:
            loader = PyPDFLoader(file_path)
            pages  = loader.load()
            full_text = "\n\n".join([p.page_content for p in pages])
            print(f"  Extracted {len(full_text)} characters from PDF")
            if len(full_text.strip()) < 100:
                print("  WARNING: Very little text extracted - PDF may be image-based")
            texts = splitter.split_text(full_text)
        except Exception as e:
            print(f"  PDF load error: {e}")
            return 0
    elif ext in ["txt", "csv"]:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            texts = splitter.split_text(content)
        except Exception as e:
            print(f"  File read error: {e}")
            return 0
    else:
        print(f"  Skipping unsupported type: {ext}")
        return 0

    if not texts:
        print("  No text extracted")
        return 0

    print(f"  Split into {len(texts)} chunks")

    first_delete_done = False
    vectors = []
    for i, text in enumerate(texts):
        if not text.strip():
            continue
        embedding = model.encode(text).tolist()
        vector_id = f"{doc_id}_chunk_{i}"
        vectors.append({
            "id":     vector_id,
            "values": embedding,
            "metadata": {
                "doc_id":     str(doc_id),
                "text":       text[:2000],
                "chunk":      i,
                "name":       metadata.get("name", ""),
                "doc_type":   metadata.get("doc_type", ""),
                "plant_site": metadata.get("plant_site", ""),
                "line":       metadata.get("line", ""),
                "revision":   metadata.get("revision", "1.0"),
                "file_type":  metadata.get("file_type", ""),
            }
        })
        if len(vectors) >= 50:
            index.upsert(vectors=vectors)
            vectors = []

    if vectors:
        index.upsert(vectors=vectors)

    print(f"  Done - {len(texts)} chunks embedded for {metadata.get('name')}")
    return len(texts)
