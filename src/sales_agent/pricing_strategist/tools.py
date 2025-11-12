import numpy as np
import plotly.graph_objects as go
from PyPDF2 import PdfReader
from langchain.text_splitter import CharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS


def get_raw_text(files: list[str]) -> str:
    """
    Get raw text from all files provided as a list and turn as a single string.
    :param files: names of files to be processed
    :return: raw_text
    """
    text = ""
    for file in files:
        pdf_reader = PdfReader(file)
        for page in pdf_reader.pages:
            text += page.extract_text()

    return text


def get_text_chunks(raw_text: str) -> list:
    """
    Convert raw text provided as a string argument to text chunks (list of strings).
    :param raw_text: complete text as a string
    :return: chunks
    """

    text_splitter = CharacterTextSplitter(
        separator="\n",
        chunk_size=1000,
        chunk_overlap=200
    )

    chunks = text_splitter.split_text(raw_text)

    return chunks


def get_doc_retriever(file: str):
    """
    Convert the test chunks provided as an argument to a vector store with embeddings.
    :param file: path of the file
    :return: vectorstore
    """
    raw_text = get_raw_text(file)
    text_chunks = get_text_chunks(raw_text)
    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
    vectorstore = FAISS.from_texts(texts=text_chunks, embedding=embeddings)
    doc_retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

    return doc_retriever


def price_prediction():
    # Generate data
    np.random.seed(42)
    volume = np.random.exponential(scale=50, size=200)  # Most points in lower volume range
    volume = np.clip(volume, 0, 500)  # Limit volume to 500 units

    # Exponential decreasing curve
    price = 100 * np.exp(-volume / 100) + 30

    # Scatter points around the curve with higher noise at the beginning, increased by a factor of 3
    noise = np.random.normal(loc=0, scale=30 * np.exp(-volume / 50), size=volume.shape)  # Noise factor increased by 3
    price_noisy = price + noise

    # Create Plotly scatter plot
    scatter = go.Scatter(
        x=volume,
        y=price_noisy,
        mode='markers',
        marker=dict(size=6, color='blue', opacity=0.6),
        name='Scatter Points'
    )

    # Create the curve line
    curve_x = np.linspace(0, 500, 1000)
    curve_y = 100 * np.exp(-curve_x / 100) + 30
    curve = go.Scatter(
        x=curve_x,
        y=curve_y,
        mode='lines',
        line=dict(color='red', width=2),
        name='Exponential Curve'
    )

    # Randomly generate the vertical line position between 100 and 200
    random_x_for_vertical = np.random.uniform(75, 150)
    random_y_for_intersection = 100 * np.exp(-random_x_for_vertical / 100) + 30

    # Create horizontal and vertical lines
    horizontal_line = go.Scatter(
        x=[0, 250],  # Span across the visible x-axis
        y=[random_y_for_intersection, random_y_for_intersection],  # Constant y at intersection
        mode='lines',
        line=dict(color='green', width=1, dash='dash'),
        name='Predicted Price'
    )

    vertical_line = go.Scatter(
        x=[random_x_for_vertical, random_x_for_vertical],  # Constant x at intersection
        y=[0, max(price_noisy) + 10],  # Extend the vertical line across the entire y-axis range
        mode='lines',
        line=dict(color='orange', width=1, dash='dash'),
        name='Contracted Volume'
    )

    # Layout with x-axis limited to 250 units and y-axis starting from 0
    layout = go.Layout(
        title='Pricing forecast',
        xaxis=dict(title='Volume', range=[0, 250], zeroline=True),
        yaxis=dict(title='Price', range=[0, max(price_noisy) + 10], zeroline=True),
        showlegend=True,
        template='plotly_white'
    )

    # Create the figure
    fig = go.Figure(data=[scatter, curve, horizontal_line, vertical_line], layout=layout)

    return fig


def market_forecast():
    # Data for the automotive market forecast
    years = [2024, 2025, 2026, 2027, 2028]
    market_size = [2800, 3000, 3300, 3600, 4000]  # in USD Billion
    ev_market_share = [15, 20, 25, 30, 35]  # in percentage

    # Create a figure
    fig = go.Figure()

    # Add Global Market Size line on the primary y-axis
    fig.add_trace(go.Scatter(x=years, y=market_size, mode='lines+markers', name='Market Size (Billion USD)',
                             line=dict(color='royalblue', width=3)))

    # Add EV Market Share line on the secondary y-axis
    fig.add_trace(go.Scatter(x=years, y=ev_market_share, mode='lines+markers', name='EV Market Share (%)',
                             line=dict(color='firebrick', width=3, dash='dash'),
                             yaxis='y2'))

    # Update layout to add a secondary y-axis
    fig.update_layout(
        title='Automotive Market Forecast',
        xaxis_title='Year',
        yaxis=dict(
            title='Market Size (Billion USD)',
            titlefont=dict(color='royalblue'),
            tickfont=dict(color='royalblue'),
            range=[0, max(market_size) + 500]  # Start from 0
        ),
        yaxis2=dict(
            title='EV Market Share (%)',
            titlefont=dict(color='firebrick'),
            tickfont=dict(color='firebrick'),
            overlaying='y',
            side='right',
            range=[0, max(ev_market_share) + 5]  # Start from 0
        ),
        legend=dict(x=0.01, y=0.99)
    )

    # Save the plot as an image file
    fig.write_image("src/automotive_market_forecast.png")