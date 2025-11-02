# RAG Chatbot Project

โปรเจคนี้คือการทดลองทำ RAG (Retrieval-Augmented Generation) chatbot เพื่อตอบคำถามจากเอกสารขององค์กร โดยรันแบบ local/on-premise (ไม่ใช้ cloud) โดยใช้ Ollama model llama3

## ปัญหาที่พบ

ปัจจุบันเกิดปัญหาที่ backend ไม่สามารถเชื่อมต่อไปยัง PostgreSQL ได้ น่าจะเกิดจากการตั้งค่า Docker ที่ยังไม่ถูกต้อง

**สถานะ:** จะกลับมาทำใหม่ตอนที่มีความรู้เพิ่มขึ้น ไม่ใส่ gitignore เพราะเป็นโปรเจคทดลอง

## Stack ที่ใช้

ดูรายละเอียด stack ที่ใช้ในโปรเจคได้ที่ [rag_system_doc.md](./rag_system_doc.md)