from pypdf import PdfReader
from typing import List
import os

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from utils.embeddings import vector_store


def extract_text(pdf_path: str = "data-source/Bank-Policy.pdf") -> str:
    reader = PdfReader(pdf_path)

    text = ""

    for page in reader.pages:
        page_text = page.extract_text()

        if page_text:
            text += page_text + "\n"

    return text


def chunk_text(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200
) -> List[str]:

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )

    return splitter.split_text(text)


def store_pdf_embeddings(
    pdf_path: str = "data-source/Bank-Policy.pdf"
) -> int:

    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    text = extract_text(pdf_path)

    if not text.strip():
        return 0

    chunks = chunk_text(text)

    documents = [
        Document(
            page_content=chunk,
            metadata={
                "source": os.path.basename(pdf_path),
                "chunk": index
            }
        )
        for index, chunk in enumerate(chunks)
    ]

    # Optional: clear existing collection before re-indexing
    # Uncomment if you don't want duplicate embeddings
    #
    # vector_store.delete_collection()
    # from utils.embeddings import embeddings
    # vector_store = Chroma(
    #     collection_name="pdf_docs",
    #     embedding_function=embeddings,
    #     persist_directory="./chroma_db"
    # )

    vector_store.add_documents(documents)

    return len(documents)


if __name__ == "__main__":
    count = store_pdf_embeddings()
    print(f"Indexed {count} chunks into Chroma")