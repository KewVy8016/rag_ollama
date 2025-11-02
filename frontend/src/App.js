import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

const API_URL = 'http://localhost:8000';

function App() {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState(null);
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [activeTab, setActiveTab] = useState('chat');

  useEffect(() => {
    fetchHistory();
    fetchDocuments();
  }, []);

  const fetchHistory = async () => {
    try {
      const response = await axios.get(`${API_URL}/history`);
      setHistory(response.data);
    } catch (error) {
      console.error('Error fetching history:', error);
    }
  };

  const fetchDocuments = async () => {
    try {
      const response = await axios.get(`${API_URL}/documents`);
      setDocuments(response.data);
    } catch (error) {
      console.error('Error fetching documents:', error);
    }
  };

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
  };

  const handleUpload = async () => {
    if (!file) {
      alert('กรุณาเลือกไฟล์');
      return;
    }

    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post(`${API_URL}/upload`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      alert(`อัปโหลดสำเร็จ! ประมวลผล ${response.data.chunks} ส่วน`);
      setFile(null);
      fetchDocuments();
    } catch (error) {
      alert('เกิดข้อผิดพลาด: ' + error.response?.data?.detail || error.message);
    } finally {
      setUploading(false);
    }
  };

  const handleAsk = async () => {
    if (!question.trim()) {
      alert('กรุณาพิมพ์คำถาม');
      return;
    }

    setLoading(true);
    setAnswer(null);

    try {
      const response = await axios.post(`${API_URL}/ask`, {
        question: question,
        top_k: 3,
      });
      setAnswer(response.data);
      setQuestion('');
      fetchHistory();
    } catch (error) {
      alert('เกิดข้อผิดพลาด: ' + error.response?.data?.detail || error.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app">
      <header className="header">
        <h1>🧠 ระบบ AI ตอบคำถามจากเอกสารองค์กร</h1>
        <p>อัปโหลดเอกสารและถามคำถามได้เลย</p>
      </header>

      <div className="tabs">
        <button
          className={activeTab === 'chat' ? 'tab active' : 'tab'}
          onClick={() => setActiveTab('chat')}
        >
          💬 ถามคำถาม
        </button>
        <button
          className={activeTab === 'upload' ? 'tab active' : 'tab'}
          onClick={() => setActiveTab('upload')}
        >
          📤 อัปโหลดเอกสาร
        </button>
        <button
          className={activeTab === 'history' ? 'tab active' : 'tab'}
          onClick={() => setActiveTab('history')}
        >
          📜 ประวัติ
        </button>
        <button
          className={activeTab === 'documents' ? 'tab active' : 'tab'}
          onClick={() => setActiveTab('documents')}
        >
          📁 เอกสาร
        </button>
      </div>

      <div className="content">
        {activeTab === 'chat' && (
          <div className="chat-section">
            <div className="question-box">
              <textarea
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="พิมพ์คำถามของคุณที่นี่..."
                rows="4"
              />
              <button onClick={handleAsk} disabled={loading}>
                {loading ? '⏳ กำลังคิด...' : '🚀 ถาม'}
              </button>
            </div>

            {answer && (
              <div className="answer-box">
                <h3>💡 คำตอบ:</h3>
                <p>{answer.answer}</p>
                <div className="sources">
                  <strong>📚 แหล่งข้อมูล:</strong>
                  <ul>
                    {answer.sources.map((source, idx) => (
                      <li key={idx}>{source}</li>
                    ))}
                  </ul>
                </div>
                <small className="timestamp">
                  เวลา: {new Date(answer.timestamp).toLocaleString('th-TH')}
                </small>
              </div>
            )}
          </div>
        )}

        {activeTab === 'upload' && (
          <div className="upload-section">
            <div className="upload-box">
              <h3>📤 อัปโหลดเอกสาร</h3>
              <p>รองรับไฟล์ PDF และ TXT</p>
              <input type="file" onChange={handleFileChange} accept=".pdf,.txt" />
              {file && (
                <div className="file-info">
                  <strong>ไฟล์ที่เลือก:</strong> {file.name}
                </div>
              )}
              <button onClick={handleUpload} disabled={uploading || !file}>
                {uploading ? '⏳ กำลังอัปโหลด...' : '📤 อัปโหลด'}
              </button>
            </div>
          </div>
        )}

        {activeTab === 'history' && (
          <div className="history-section">
            <h3>📜 ประวัติการสนทนา</h3>
            {history.length === 0 ? (
              <p className="empty">ยังไม่มีประวัติ</p>
            ) : (
              <div className="history-list">
                {history.map((item) => (
                  <div key={item.id} className="history-item">
                    <div className="history-question">
                      <strong>❓ คำถาม:</strong> {item.question}
                    </div>
                    <div className="history-answer">
                      <strong>💡 คำตอบ:</strong> {item.answer}
                    </div>
                    <small className="timestamp">
                      {new Date(item.created_at).toLocaleString('th-TH')}
                    </small>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'documents' && (
          <div className="documents-section">
            <h3>📁 เอกสารที่อัปโหลด</h3>
            {documents.length === 0 ? (
              <p className="empty">ยังไม่มีเอกสาร</p>
            ) : (
              <div className="documents-list">
                {documents.map((doc, idx) => (
                  <div key={idx} className="document-item">
                    <div className="doc-name">📄 {doc.filename}</div>
                    <div className="doc-info">
                      ส่วนข้อความ: {doc.chunks} | อัปโหลด:{' '}
                      {new Date(doc.uploaded_at).toLocaleString('th-TH')}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default App;