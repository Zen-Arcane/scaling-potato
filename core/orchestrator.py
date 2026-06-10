from langchain_core.tools import tool
from utils.decorators import log_execution
from utils.embeddings import vector_store
from config.wrapperConfig import LLMFactory
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel


class Reference(BaseModel):
    document: str
    page: int


class FinalResponse(BaseModel):
    response: str
    references: list[Reference]


@tool
@log_execution
def handle_fetch(query: str):
    """
    Retrieve relevant information from the knowledge base and answer the user's question.
    """

    try:


        retriever = vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={
                "k": 4
            }
        )

        docs = retriever.invoke(query)

        if not docs:
            return {
                "response": "No relevant information found.",
                "references": []
            }

        print(f"Retrieved {len(docs)} chunks")


        context_parts = []

        page_map = {}

        for doc in docs:

            source = doc.metadata.get("source", "unknown")
            page = doc.metadata.get("page", "unknown")

            page_key = f"{source}|{page}"

            page_map[page_key] = {
                "document": source,
                "page": page
            }

            context_parts.append(
                f"""
                    SOURCE: {source}
                    PAGE: {page}

                    CONTENT:
                    {doc.page_content}
                """
            )

        context = "\n\n".join(context_parts)

        prompt = ChatPromptTemplate.from_template("""
                You are a document QA assistant.

                Answer ONLY from the supplied context.

                Rules:

                1. Give a direct answer.
                2. Do not say:
                - "According to the document"
                - "The provided context"
                - "The text states"
                3. If information is unavailable, say so.
                4. references MUST contain ONLY pages actually used.
                5. Use the minimum number of references required.
                6. Never cite more than 3 pages.
                7. Prefer the most relevant pages.
                8. Do not invent page numbers.

                Context:
                {context}

                Question:
                {question}
    """)

        llm = (
            LLMFactory.get_llm()
            .with_structured_output(FinalResponse)
        )

        chain = prompt | llm

        result = chain.invoke({
            "context": context,
            "question": query
        })


        valid_refs = []
        seen = set()

        for ref in result.references:

            key = (ref.document, ref.page)

            if key in seen:
                continue

            if not any(
                doc.metadata.get("source") == ref.document
                and doc.metadata.get("page") == ref.page
                for doc in docs
            ):
                continue

            valid_refs.append({
                "document": ref.document,
                "page": ref.page
            })

            seen.add(key)

        if not valid_refs:

            top_doc = docs[0]

            valid_refs = [{
                "document": top_doc.metadata.get("source"),
                "page": top_doc.metadata.get("page")
            }]

        valid_refs = valid_refs[:3]

        return {
            "response": result.response,
            "references": valid_refs
        }

    except Exception as e:

        return {
            "response": f"Error in RAG pipeline: {str(e)}",
            "references": []
        }


tools = [handle_fetch]