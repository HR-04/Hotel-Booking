from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import create_engine
from datetime import datetime
import logging
from langchain_community.vectorstores import FAISS
from langchain_ollama import OllamaEmbeddings
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain_ollama import OllamaLLM
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Database configuration
DB_CONFIG = {
    "dbname": "hotel_db",
    "user": "postgres",
    "password": "admin",
    "host": "localhost",
    "port": "5432"
}

# Create SQLAlchemy engine
DATABASE_URL = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@" \
               f"{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}"
engine = create_engine(DATABASE_URL)

# Initialize components
vector_store = None
qa_chain = None

@app.on_event("startup")
async def initialize_services():
    global vector_store, qa_chain
    try:
        # Initialize Vector DB
        if not os.path.exists("faiss_index"):
            logger.info("Creating vector database...")
            df = pd.read_sql("SELECT * FROM hotel_bookings", con=engine)
            
            df["raw_data"] = df.apply(lambda row: "\n".join(
                [f"{col}: {row[col]}" for col in df.columns]
            ), axis=1)

            embeddings = OllamaEmbeddings(model="nomic-embed-text:latest")
            vector_store = FAISS.from_texts(
                texts=df["raw_data"].tolist(),
                embedding=embeddings,
                metadatas=df.to_dict('records')
            )
            vector_store.save_local("faiss_index")
            logger.info(f"Vector DB created with {len(df)} records")
        else:
            logger.info("Loading existing vector database...")
            embeddings = OllamaEmbeddings(model="nomic-embed-text:latest")
            vector_store = FAISS.load_local("faiss_index", embeddings)

        # Initialize LLM Chain
        llm = OllamaLLM(model="phi4:latest")
        prompt_template = """Use the following context to answer the question. 
        If you don't know the answer, say you don't know. Keep it concise.
        
        Context: {context}
        Question: {question}
        Answer:"""
        
        qa_chain = RetrievalQA.from_chain_type(
            llm=llm,
            chain_type="stuff",
            retriever=vector_store.as_retriever(),
            chain_type_kwargs={
                "prompt": PromptTemplate(
                    template=prompt_template,
                    input_variables=["context", "question"]
                )
            }
        )
        logger.info("RAG pipeline initialized successfully")

    except Exception as e:
        logger.error(f"Initialization failed: {str(e)}")
        raise

@app.post("/analytics")
async def generate_analytics():
    try:
        logger.info("Connecting to database...")
        # Read data using SQLAlchemy connection
        df = pd.read_sql("SELECT * FROM hotel_bookings", con=engine)
        
        if df.empty:
            logger.warning("No data found in database")
            return JSONResponse(content={"error": "No data found"}, status_code=404)

        logger.info("Generating visualizations...")

        # 1. Revenue Trends Over Time (Line Chart)
        revenue_df = df.groupby(['arrival_date_year', 'arrival_date_month'])['revenue'].sum().reset_index()
        revenue_df['date'] = revenue_df.apply(lambda x: datetime(
            x['arrival_date_year'],
            datetime.strptime(x['arrival_date_month'], '%B').month,
            1
        ), axis=1)
        revenue_df = revenue_df.sort_values('date')
        fig1 = px.line(
            revenue_df, 
            x='date', 
            y='revenue', 
            markers=True,
            title="Revenue Trends Over Time",
            labels={"date": "Date", "revenue": "Total Revenue (€)"}
        )

        # 2. Cancellation Rate - Gauge Chart
        cancel_rate = (df['is_canceled'].mean() * 100).round(2)
        fig2 = go.Figure(go.Indicator(
            mode="gauge+number",
            value=cancel_rate,
            title={"text": "Cancellation Rate (%)"},
            gauge={"axis": {"range": [0, 100]}} 
        ))
        fig2.update_layout(title="Cancellation Rate", margin=dict(l=20, r=20, t=50, b=20))

        # 3. Geographical Distribution - Horizontal Bar Chart
        country_dist = df['country'].value_counts().nlargest(10)
        geo_df = pd.DataFrame({
            'country': country_dist.index,
            'bookings': country_dist.values
        })
        fig3 = px.bar(
            geo_df, 
            x='bookings', 
            y='country', 
            orientation='h',
            title="Top 10 Countries by Bookings",
            labels={'bookings': 'Number of Bookings', 'country': 'Country Code'}
        )

        # 4. Booking Lead Time Distribution - Box Plot
        fig4 = px.box(
            df, 
            y="lead_time", 
            points="all",
            title="Booking Lead Time Distribution",
            labels={'lead_time': 'Lead Time (Days)'}
        )

        # 5. Stay Duration Analysis (Stacked Bar Chart)
        stay_duration = df.groupby('hotel')[['stays_in_week_nights', 'stays_in_weekend_nights']].mean().reset_index()
        fig5 = px.bar(
            stay_duration, 
            x='hotel', 
            y=['stays_in_week_nights', 'stays_in_weekend_nights'],
            title="Average Stay Duration by Hotel Type",
            labels={'value': 'Average Nights', 'hotel': 'Hotel Type'},
            barmode='stack'
        )

        # 6. ADR Distribution by Hotel Type (Box Plot)
        fig6 = px.box(
            df, 
            x='hotel', 
            y='adr', 
            title="Average Daily Rate Distribution by Hotel Type",
            labels={'hotel': 'Hotel Type', 'adr': 'Average Daily Rate (€)'},
            color='hotel'
        )

        # 7. Monthly Booking Trends (Ordered Bar Chart)
        month_order = ['January', 'February', 'March', 'April', 'May', 'June', 
                       'July', 'August', 'September', 'October', 'November', 'December']
        monthly_bookings = df.groupby('arrival_date_month').size().reindex(month_order, fill_value=0).reset_index()
        monthly_bookings.columns = ['month', 'bookings']
        fig7 = px.bar(
            monthly_bookings,
            x='month',
            y='bookings',
            title="Monthly Booking Trends",
            labels={'month': 'Month', 'bookings': 'Number of Bookings'}
        )

        logger.info("Analytics generated successfully")
        return {
            "revenue_trend": fig1.to_json(),
            "cancellation_rate": fig2.to_json(),
            "geographical_dist": fig3.to_json(),
            "lead_time_dist": fig4.to_json(),
            "stay_duration": fig5.to_json(),
            "adr_distribution": fig6.to_json(),
            "monthly_trends": fig7.to_json()
        }

    except Exception as e:
        logger.error(f"Error generating analytics: {str(e)}")
        return JSONResponse(content={"error": f"Internal server error: {str(e)}"}, status_code=500)
    
@app.post("/ask")
async def answer_question(question: dict):
    try:
        if not qa_chain:
            raise HTTPException(status_code=503, detail="Service not initialized")
        
        result = qa_chain.invoke({"query": question.get("question", "")})
        return {"answer": result["result"]}
    
    except Exception as e:
        logger.error(f"Q&A error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to process question: {str(e)}"}
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
