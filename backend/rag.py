import logging
import pandas as pd
from datetime import datetime
from fastapi import APIRouter, HTTPException
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.prompts import PromptTemplate
from langchain_community.vectorstores import FAISS
from langchain_ollama import OllamaEmbeddings, OllamaLLM
from data_gen import engine

router = APIRouter()
logger = logging.getLogger(__name__)


conversation_history = []

# Global variables for vector store and QA chain
vector_store = None
qa_chain = None

def update_insights():
    """
    Loads hotel booking data, computes insights, updates the FAISS vector store,
    and rebuilds the retrieval-augmented QA chain.
    """
    global vector_store, qa_chain
    try:
        logger.info("Updating insights based on latest data...")
        df = pd.read_sql("SELECT * FROM hotel_bookings", con=engine)
        if 'revenue' not in df.columns:
            df['revenue'] = df['adr'] * (df['stays_in_week_nights'] + df['stays_in_weekend_nights'])
        
        # Revenue Trends Insight
        revenue_df = df.groupby(['arrival_date_year', 'arrival_date_month'])['revenue'] \
                       .sum().reset_index().rename(columns={'revenue': 'total_revenue'})
        revenue_texts = []
        for _, row in revenue_df.iterrows():
            month_abbr = datetime.strptime(row['arrival_date_month'], '%B').strftime('%b')
            revenue_texts.append(f"Date: {month_abbr}1 {int(row['arrival_date_year'])} - Total revenue is {row['total_revenue']:.2f}.")
        
        # Cancellation Rate Insight
        cancel_df = df.groupby(['arrival_date_year', 'arrival_date_month']) \
                      .agg(total_bookings=('is_canceled', 'count'),
                           cancellations=('is_canceled', 'sum')).reset_index()
        cancel_df['cancellation_rate'] = (cancel_df['cancellations'] / cancel_df['total_bookings']) * 100
        cancel_texts = []
        for _, row in cancel_df.iterrows():
            month_abbr = datetime.strptime(row['arrival_date_month'], '%B').strftime('%b')
            cancel_texts.append(f"On {month_abbr}1 {int(row['arrival_date_year'])}, cancellation rate was {row['cancellation_rate']:.2f}%.")
        
        # Geographical Distribution Insight
        geo_series = df['country'].value_counts().nlargest(10)
        geo_texts = [f"Country {country} had {count} bookings." for country, count in geo_series.items()]
        
        # Booking Lead Time Insight
        lead_df = df.groupby(['arrival_date_year', 'arrival_date_month'])['lead_time'] \
                    .mean().reset_index().rename(columns={'lead_time': 'avg_lead_time'})
        lead_texts = []
        for _, row in lead_df.iterrows():
            month_abbr = datetime.strptime(row['arrival_date_month'], '%B').strftime('%b')
            lead_texts.append(f"On {month_abbr}1 {int(row['arrival_date_year'])}, average lead time was {row['avg_lead_time']:.2f} days.")
        
        # ADR Distribution Insight (summary)
        adr_df = df.groupby("hotel")['adr'].describe().reset_index()
        adr_texts = [f"Hotel type {row['hotel']} has ADR mean {row['mean']:.2f}." for _, row in adr_df.iterrows()]
        
        # Average Stay Duration Insight
        df['total_stay'] = df['stays_in_week_nights'] + df['stays_in_weekend_nights']
        stay_df = df.groupby("hotel")['total_stay'].mean().reset_index().rename(columns={'total_stay': 'avg_stay'})
        stay_texts = [f"Hotel type {row['hotel']} average stay is {row['avg_stay']:.2f} nights." for _, row in stay_df.iterrows()]
        
        # Monthly Booking Trends Insight
        month_order = ['January', 'February', 'March', 'April', 'May', 'June', 
                       'July', 'August', 'September', 'October', 'November', 'December']
        monthly_bookings = df.groupby('arrival_date_month').size().reindex(month_order, fill_value=0)
        monthly_texts = [f"In {month}, total bookings was {monthly_bookings.get(month, 0)}." for month in month_order]
        
        # Combine all insights
        insight_texts = revenue_texts + cancel_texts + geo_texts + lead_texts + adr_texts + stay_texts + monthly_texts
        logger.info(f"Generated {len(insight_texts)} insights.")
        
        # Update FAISS vector store with insights
        embeddings = OllamaEmbeddings(model="nomic-embed-text:latest")
        vector_store = FAISS.from_texts(
            texts=insight_texts,
            embedding=embeddings,
            metadatas=[{"type": "insight"}] * len(insight_texts)
        )
        vector_store.save_local("faiss_index")
        logger.info("FAISS vector store updated.")
        
        # Build the QA chain using an LLM
        llm = OllamaLLM(model="phi4:latest")
        prompt_template = PromptTemplate(
            template="""You're a Hotel Booking Assistant, who will answer the question with following conversation history and  context,
            Answer the Question with the context, If you're facing a very non relevant question apart from knowledge , response with
            "Sorry, Context is insufficient. Please try asking a different analytics question. I'm here to help."
            Conversation History:
            {chat_history}
            Context:
            {context}
            Question:
            {input}
            Answer:""",
            input_variables=["chat_history", "context", "input"]
        )
        retriever_chain = create_history_aware_retriever(llm, vector_store.as_retriever(), prompt_template)
        document_chain = create_stuff_documents_chain(llm, prompt_template)
        qa_chain = create_retrieval_chain(retriever_chain, document_chain)
        logger.info("QA chain updated.")
    except Exception as e:
        logger.error(f"Error updating insights: {e}")

@router.post("/ask")
async def answer_question(question: dict):
    try:
        if not qa_chain:
            raise HTTPException(status_code=503, detail="Service not initialized")
        user_query = question.get("question", "")
        conversation_history.append({"role": "user", "content": user_query})
        chat_history_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation_history])
        
        retrieved_docs = vector_store.similarity_search(user_query)
        insights_text = "\n".join([doc.page_content for doc in retrieved_docs])
        
        result = qa_chain.invoke({
            "input": user_query,
            "chat_history": chat_history_str,
            "context": insights_text
        })
        conversation_history.append({"role": "ai", "content": result["answer"]})
        return {"answer": result["answer"]}
    except Exception as e:
        logger.error(f"Q&A error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process question: {e}")


