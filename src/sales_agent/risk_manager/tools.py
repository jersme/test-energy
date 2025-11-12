from typing import Iterable, Optional

from langchain.document_loaders import UnstructuredURLLoader
from langchain.docstore.document import Document
from langchain.chains.summarize import load_summarize_chain
from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.documents import Document
from langchain_core.tools import BaseTool
from requests.exceptions import HTTPError, ReadTimeout
from urllib3.exceptions import ConnectionError
from unstructured.cleaners.core import remove_punctuation, clean, clean_extra_whitespace

from langchain_openai import ChatOpenAI

from langchain.chains.summarize import load_summarize_chain

class YahooFinanceNewsTool(BaseTool):
    """Tool that searches financial news on Yahoo Finance."""

    name: str = "yahoo_finance_news"
    description: str = (
        "Useful for when you need to find financial news "
        "about a public company. "
        "Input should be a company ticker. "
        "For example, AAPL for Apple, MSFT for Microsoft."
    )
    top_k: int = 5
    """The number of results to return."""

    def _run(
        self,
        query: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the Yahoo Finance News tool."""
        try:
            import yfinance
        except ImportError:
            raise ImportError(
                "Could not import yfinance python package. "
                "Please install it with `pip install yfinance`."
            )
        company = yfinance.Ticker(query)
        try:
            if company.isin is None:
                return f"Company ticker {query} not found."
        except (HTTPError, ReadTimeout, ConnectionError):
            return f"Company ticker {query} not found."

        links = []
        try:
            links = [n['content']["canonicalUrl"]['url'] for n in company.news if n['content']['contentType'] == "STORY"]
        except (HTTPError, ReadTimeout, ConnectionError):
            if not links:
                return f"No news found for company that searched with {query} ticker."
        if not links:
            return f"No news found for company that searched with {query} ticker."
        
        docs = self._generate_document(links)
        summary = self._summarize_results(docs)

        return summary
    
    @staticmethod
    def _generate_document(urls: Iterable[str]) -> Document:
        "Given an URL, return a langchain Document to futher processing"
        loader = UnstructuredURLLoader(urls=urls,
                                       mode="elements",
                                       post_processors=[clean,
                                                        remove_punctuation,
                                                        clean_extra_whitespace])

        elements = loader.load()
        selected_elements = [e for e in elements if e.metadata['category']=="NarrativeText"]
        full_clean = " ".join([e.page_content for e in selected_elements])

        return Document(page_content=full_clean, metadata={"source":urls})

    @staticmethod
    def _format_results(docs: Iterable[Document]) -> str:
        doc_strings = [
            "\nTitle:".join([doc.metadata["title"], doc.page_content])
            for doc in docs
        ]
        return "\n\n".join(doc_strings)
    
    @staticmethod
    def _summarize_results(docs: str) -> str:
        """Summarize the results of documents.
        """
        llm = ChatOpenAI(temperature=0.0)
        chain = load_summarize_chain(llm, chain_type="stuff")
        summary = chain.run([docs])
        return clean_extra_whitespace(summary)
