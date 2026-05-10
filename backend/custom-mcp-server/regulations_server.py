import os
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from langchain_openai.embeddings import OpenAIEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.vectorstores import InMemoryVectorStore, VectorStore
load_dotenv()
mcp: FastMCP = FastMCP("custom_server")

@mcp.tool()
def get_regulation(query: str) -> str:
    base_path = os.path.dirname(__file__)
    pdf_path = os.path.join(base_path, "bet_regulations.pdf")
    
        # Lazy imports to avoid import-time failures when running under MCP
        

    loader = PyPDFLoader(pdf_path)
    documents: list[Document] = loader.load()

    text_splitter: RecursiveCharacterTextSplitter = RecursiveCharacterTextSplitter(chunk_size=100, chunk_overlap=0)
    split_docs: list[Document] = text_splitter.split_documents(documents)

        

    embedding: OpenAIEmbeddings = OpenAIEmbeddings(model="text-embedding-3-large", api_key=os.getenv("OPENAI_API_KEY"))

    vector_db: VectorStore = InMemoryVectorStore(embedding=embedding)
    vector_db.add_texts(texts=split_docs)

    vector_db_search: list[Document] = vector_db.similarity_search(query)

    res: str = "\\n".join([doc.page_content for doc in vector_db_search])
    return res
    

    



 