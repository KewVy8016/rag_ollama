import asyncio
import os
import asyncpg
from datetime import datetime

# ดึงค่า URL จาก Environment Variable
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:admin123@postgres:5432/ragdb")

async def test_db_connection():
    print("=" * 60)
    print(f"[{datetime.now().isoformat()}] 🧪 STARTING DATABASE CONNECTION TEST")
    print(f"🔗 Attempting to connect to: {DATABASE_URL.split('@')[1]}")
    
    conn = None
    try:
        # พยายามสร้าง Pool
        pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=1,
            max_size=1,
            command_timeout=10, # ลด timeout เพื่อให้รู้ผลเร็วขึ้น
        )
        print(f"[{datetime.now().isoformat()}] ✅ Connection Pool created successfully!")
        
        # ดึง Connection และทดสอบ Query ง่ายๆ
        async with pool.acquire() as conn:
            print(f"[{datetime.now().isoformat()}] ➡️ Testing simple query...")
            result = await conn.fetchval("SELECT 1 + 1")
            
            if result == 2:
                print(f"[{datetime.now().isoformat()}] 🎉 SUCCESS: Query executed (Result: {result})")
                
                # ทดสอบว่า pgvector extension มีอยู่หรือไม่
                ext = await conn.fetchval("SELECT extname FROM pg_extension WHERE extname = 'vector'")
                print(f"[{datetime.now().isoformat()}] 🎯 pgvector extension: {'FOUND' if ext else 'NOT FOUND'}")
                
            else:
                print(f"[{datetime.now().isoformat()}] ⚠️ WARNING: Query result was not 2.")
                
        # ปิด Pool
        await pool.close()
        print(f"[{datetime.now().isoformat()}] 🚪 Connection Pool closed.")
        
    except Exception as e:
        # ถ้าเกิด Error getaddrinfo failed จะมาที่นี่
        print(f"[{datetime.now().isoformat()}] ❌ FATAL ERROR: Database connection failed!")
        print(f"   [Error Type]: {type(e).__name__}")
        print(f"   [Error Msg]: {str(e)}")
        print("\n   [GUIDE] Error 11001/getaddrinfo failed หมายความว่า Hostname 'postgres' ไม่ถูกพบใน Docker Network")
        print("   โปรดตรวจสอบว่า Service 'postgres' และ 'backend' อยู่ในไฟล์ docker-compose.yml เดียวกัน และมีการระบุ networks ที่ถูกต้อง")
        
    finally:
        print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_db_connection())
