from pypdf import PdfReader
import os
from typing import List
from utils.embeddings import embeddings, vector_store


def extract_text(pdf_path: str = "data-source/Bank-Policy.pdf") -> str:
    reader = PdfReader(pdf_path)

    text = ""

    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"

    return text


def chunk_text(text: str, max_chars: int = 1000, overlap: int = 200) -> List[str]:
    chunks: List[str] = []
    start = 0
    length = len(text)
    if length == 0:
        return chunks

    while start < length:
        end = start + max_chars
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - overlap
    return chunks


def store_pdf_embeddings(pdf_path: str = None, collection_name: str = "pdf_docs") -> int:
    """Extract text from `pdf_path`, split into chunks, embed and persist to the configured vector store.

    Returns the number of chunks indexed.
    """
    pdf_path = pdf_path or "data-source/Bank-Policy.pdf"
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    text = extract_text(pdf_path)
    chunks = chunk_text(text)

    if not chunks:
        return 0

    metadatas = [{"source": os.path.basename(pdf_path), "chunk": i} for i in range(len(chunks))]

  
    try:
        vector_store.add_texts(chunks, metadatas=metadatas)
    except Exception:
        try:
            # Some wrappers expect Document objects or add_documents
            docs = []
            for i, chunk in enumerate(chunks):
                docs.append({"page_content": chunk, "metadata": metadatas[i]})
            vector_store.add_documents(docs)
        except Exception as e:
            embs = embeddings.embed_documents(chunks)

            if hasattr(vector_store, "persist"):
                try:
                    vector_store.persist()
                except Exception:
                    pass
            raise e

 
    try:
        if hasattr(vector_store, "persist"):
            vector_store.persist()
    except Exception:
        pass

    return len(chunks)


if __name__ == "__main__":
    count = store_pdf_embeddings()
    print(f"Indexed {count} chunks from PDF into vector store")