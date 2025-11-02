from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager
import os
from datetime import datetime
import asyncpg
from sentence_transformers import SentenceTransformer
import httpx
import PyPDF2
from io import BytesIO
from typing import List, Optional

# Config - ดึงค่าจาก Environment Variables ที่กำหนดใน docker-compose.yml
# ภายใน Docker: postgresql://admin:admin123@postgres:5432/ragdb
DATABASE_URL = os.getenv("DATABASE_URL")
# ภายใน Docker: http://ollama:11434
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434") 

# Check for environment variables (Optional: for running outside Docker)
if not DATABASE_URL:
    print("⚠️ DATABASE_URL not found in environment. Using fallback (check docker-compose.yml).")
    DATABASE_URL = "postgresql://admin:admin123@postgres:5432/ragdb" # ใช้ชื่อ service เป็น fallback

# Models
embedding_model = None
db_pool = None

# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global embedding_model, db_pool
    
    # Load embedding model
    print("=" * 60)
    print("🔄 Loading embedding model...")
    embedding_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
    print(f"✅ Embedding model loaded (dimension: {embedding_model.get_sentence_embedding_dimension()})")
    
    # Connect to DB
    print("🔄 Connecting to PostgreSQL...")
    try:
        db_pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=1,
            max_size=10,
            command_timeout=60
        )
        print("✅ Database connected successfully!")
    except Exception as e:
        print(f"❌ Database connection failed: {str(e)}")
        print("💡 Make sure PostgreSQL is running: docker-compose up -d")
        # ไม่ต้อง raise เพื่อให้ API รันต่อได้แม้ DB จะล้มเหลวชั่วคราว
    
    # Create tables (เฉพาะเมื่อเชื่อมต่อ DB ได้)
    if db_pool:
        print("🔄 Setting up database tables...")
        try:
            async with db_pool.acquire() as conn:
                # Create pgvector extension
                await conn.execute('CREATE EXTENSION IF NOT EXISTS vector')
                
                # Documents table with embeddings (384 dimensions for all-MiniLM-L6-v2)
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS documents (
                        id SERIAL PRIMARY KEY,
                        filename TEXT NOT NULL,
                        content TEXT NOT NULL,
                        embedding vector(384),
                        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Chat history table
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS chat_history (
                        id SERIAL PRIMARY KEY,
                        question TEXT NOT NULL,
                        answer TEXT NOT NULL,
                        sources TEXT[],
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Create index for vector search
                try:
                    await conn.execute('''
                        CREATE INDEX IF NOT EXISTS documents_embedding_idx 
                        ON documents USING ivfflat (embedding vector_cosine_ops)
                        WITH (lists = 100)
                    ''')
                except Exception as e:
                    print(f"⚠️  Index creation skipped (needs data): {str(e)}")
            
            print("✅ Database tables ready!")
        except Exception as e:
            print(f"❌ Error during table setup: {str(e)}")

    print("=" * 60)
    print("🚀 RAG System is ready!")
    print("=" * 60)
    print(f"📊 API Docs: http://localhost:8000/docs")
    if DATABASE_URL:
        print(f"💾 Database: {DATABASE_URL.split('@')[-1]}")
    print(f"🧠 Ollama URL: {OLLAMA_URL}")
    print("=" * 60)
    
    yield  # Application is running
    
    # Shutdown
    if db_pool:
        await db_pool.close()
        print("\n👋 Database connection closed")

# Create FastAPI app with lifespan
app = FastAPI(title="RAG AI System", lifespan=lifespan)

# --- ตั้งค่า CORS ---
# ให้รวม Port 3000 และ 5173 ตามที่เลือกไว้
origins = [
    # เพิ่ม Port ที่ Frontend กำลังใช้งานอยู่ (3000)
    "http://localhost:3000", 
    "http://127.0.0.1:3000",
    
    # Port เดิม (5173)
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    
    # Backend เอง
    "http://localhost:8000",
]

# CORS Middleware (ใช้ชุดการตั้งค่าที่ระบุชัดเจน)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, # ใช้รายการที่กำหนดไว้ด้านบน
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"], 
)

class QuestionRequest(BaseModel):
    question: str
    top_k: int = 3

# ... (ส่วนอื่น ๆ ของโค้ดที่เหลือ)
# (โค้ดส่วนอื่น ๆ ที่เหลือตั้งแต่ class QuestionResponse(BaseModel): เป็นต้นไป ไม่ได้ถูกเปลี่ยนแปลง)

class QuestionResponse(BaseModel):
    answer: str
    sources: List[str]
    timestamp: str

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract text from PDF"""
    pdf_file = BytesIO(pdf_bytes)
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text() + "\n"
    return text

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """Split text into chunks"""
    words = text.split()
    chunks = []
    
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
    
    return chunks

@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload and process document"""
    try:
        print(f"\n📄 Processing: {file.filename}")
        
        # Read file
        content_bytes = await file.read()
        print(f"✓ Read {len(content_bytes)} bytes")
        
        # Extract text
        if file.filename.endswith('.pdf'):
            print("📖 Extracting PDF text...")
            text = extract_text_from_pdf(content_bytes)
        elif file.filename.endswith('.txt'):
            print("📖 Extracting TXT text...")
            text = content_bytes.decode('utf-8')
        else:
            raise HTTPException(400, "Only PDF and TXT files supported")
        
        print(f"✓ Extracted {len(text)} characters")
        
        if not text.strip():
            raise HTTPException(400, "File is empty or contains no readable text")
        
        # Chunk text
        print("✂️  Chunking text...")
        chunks = chunk_text(text)
        print(f"✓ Split into {len(chunks)} chunks")
        
        if not chunks:
            raise HTTPException(400, "No chunks created from document")
        
        # Generate embeddings and save
        print("🔢 Generating embeddings...")
        async with db_pool.acquire() as conn:
            for i, chunk in enumerate(chunks, 1):
                try:
                    embedding = embedding_model.encode(chunk).tolist()
                    await conn.execute('''
                        INSERT INTO documents (filename, content, embedding)
                        VALUES ($1, $2, $3)
                    ''', file.filename, chunk, embedding)
                    
                    if i % 10 == 0 or i == len(chunks):
                        print(f"  💾 Saved {i}/{len(chunks)} chunks")
                except Exception as chunk_error:
                    print(f"⚠️  Error saving chunk {i}: {chunk_error}")
                    raise
        
        print(f"✅ Successfully uploaded: {file.filename}\n")
        
        return {
            "status": "success",
            "filename": file.filename,
            "chunks": len(chunks),
            "message": "Document uploaded and processed"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ Error details:\n{error_trace}\n")
        raise HTTPException(500, f"Error processing document: {str(e)}")

@app.post("/ask", response_model=QuestionResponse)
async def ask_question(request: QuestionRequest):
    """Ask question and get answer from RAG"""
    try:
        print(f"\n❓ Question: {request.question}")
        
        # Check if DB is available
        if not db_pool:
            raise HTTPException(503, "Database not connected")
        
        # Check if embedding model is loaded
        if not embedding_model:
            raise HTTPException(503, "Embedding model not loaded")
        
        # Generate question embedding
        question_embedding = embedding_model.encode(request.question).tolist()
        
        # Search similar documents
        async with db_pool.acquire() as conn:
            rows = await conn.fetch('''
                SELECT content, filename, 
                        1 - (embedding <=> $1::vector) as similarity
                FROM documents
                ORDER BY embedding <=> $1::vector
                LIMIT $2
            ''', question_embedding, request.top_k)
        
        if not rows:
            raise HTTPException(404, "No documents found. Please upload documents first.")
        
        print(f"✓ Found {len(rows)} relevant chunks (similarity: {rows[0]['similarity']:.3f})")
        
        # Build context
        context = "\n\n".join([row['content'] for row in rows])
        sources = list(set([row['filename'] for row in rows]))
        
        # Generate answer with Ollama
        prompt = f"""ตอบคำถามต่อไปนี้โดยอิงจากข้อมูลที่ให้มาเท่านั้น ถ้าไม่มีข้อมูลให้ตอบว่า "ไม่พบข้อมูล"

ข้อมูล:
{context}

คำถาม: {request.question}

คำตอบ:"""

        print("🤖 Generating answer with Ollama...")
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{OLLAMA_URL}/api/generate",
                    json={
                        "model": "llama3",
                        "prompt": prompt,
                        "stream": False
                    }
                )
                result = response.json()
                answer = result.get('response', 'ไม่สามารถสร้างคำตอบได้')
        except httpx.ConnectError:
            print("⚠️  Ollama not available, using context-based answer")
            answer = f"ตามข้อมูลที่พบ: {context[:200]}..."
        
        # Save to history
        async with db_pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO chat_history (question, answer, sources)
                VALUES ($1, $2, $3)
            ''', request.question, answer, sources)
        
        print(f"✅ Answer generated from sources: {', '.join(sources)}\n")
        
        return QuestionResponse(
            answer=answer,
            sources=sources,
            timestamp=datetime.now().isoformat()
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error: {str(e)}\n")
        raise HTTPException(500, f"Error generating answer: {str(e)}")

@app.get("/history")
async def get_history(limit: int = 10):
    """Get chat history"""
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch('''
                SELECT id, question, answer, sources, created_at
                FROM chat_history
                ORDER BY created_at DESC
                LIMIT $1
            ''', limit)
        
        return [dict(row) for row in rows]
    
    except Exception as e:
        raise HTTPException(500, f"Error fetching history: {str(e)}")

@app.get("/documents")
async def get_documents():
    """Get list of uploaded documents"""
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch('''
                SELECT filename, COUNT(*) as chunks, MAX(uploaded_at) as uploaded_at
                FROM documents
                GROUP BY filename
                ORDER BY uploaded_at DESC
            ''')
        
        return [dict(row) for row in rows]
    
    except Exception as e:
        raise HTTPException(500, f"Error fetching documents: {str(e)}")

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "RAG AI System API",
        "docs": "/docs",
        "health": "/health"
    }

@app.get("/health")
def health_check_sync():
    """Health check endpoint (sync version)"""
    return {
        "status": "healthy",
        "database": "connected" if db_pool else "disconnected",
        "embedding_model": "loaded" if embedding_model else "not loaded",
        "ollama": "not checked",
        "timestamp": datetime.now().isoformat()
    }
