from pypdf import PdfReader
from typing import List
import os

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from utils.embeddings import vector_store


# def extract_text(pdf_path: str = "data-source/Bank-Policy.pdf") -> str:
#     reader = PdfReader(pdf_path)

#     text = ""

#     for page in reader.pages:
#         page_text = page.extract_text()

#         if page_text:
#             text += page_text + "\n"

#     return text


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

    reader = PdfReader(pdf_path)

    page_documents = []

    for page_num, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text()

        if not page_text:
            continue

        page_documents.append(
            Document(
                page_content=page_text,
                metadata={
                    "source": os.path.basename(pdf_path),
                    "page": page_num
                }
            )
        )

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1500,
        chunk_overlap=300
    )

    documents = splitter.split_documents(page_documents)

    for idx, doc in enumerate(documents):
        doc.metadata["chunk"] = idx

    vector_store.add_documents(documents)

    return len(documents)


if __name__ == "__main__":
    count = store_pdf_embeddings()
    print(f"Indexed {count} chunks into Chroma")