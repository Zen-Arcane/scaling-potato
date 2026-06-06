import os
from langchain.chat_models import BaseChatModel
from sentence_transformers import SentenceTransformer
from langchain_core.embeddings import Embeddings
from langchain_openai import ChatOpenAI

class MiniLMEmbeddings(Embeddings):

    def __init__(self):
        self.model = SentenceTransformer(
            "sentence-transformers/all-MiniLM-L6-v2"
        )

    def embed_documents(self, texts):
        return self.model.encode(texts).tolist()

    def embed_query(self, text):
        return self.model.encode(text).tolist()

class LLMFactory:

    @staticmethod
    def get_llm():
        return ChatOpenAI(
            model="google/gemini-2.5-flash",
            temperature=0,
            max_tokens=2048,
            timeout=30,
            max_retries=3,
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1"
        )