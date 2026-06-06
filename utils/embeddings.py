from langchain_chroma import Chroma
from config.wrapperConfig import MiniLMEmbeddings

embeddings = MiniLMEmbeddings()

vector_store = Chroma(
    collection_name="pdf_docs",
    embedding_function=embeddings,
    persist_directory="./chroma_db"
)