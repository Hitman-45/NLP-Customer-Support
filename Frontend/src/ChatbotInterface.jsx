import React, { useState } from 'react';
import './ChatbotInterface.css';

export default function ChatbotInterface() {
  const [chatHistory, setChatHistory] = useState([]);
  const [userInput, setUserInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSend = async () => {
    if (!userInput.trim()) return;
    const updatedHistory = [...chatHistory, { role: 'user', message: userInput }];
    setChatHistory(updatedHistory);
    setUserInput('');
    setIsLoading(true);

    try {
      const response = await fetch('http://localhost:5000/api/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userInput, history: updatedHistory }),
      });
      const data = await response.json();
      setChatHistory(prev => [...prev, { role: 'bot', message: data.reply }]);
    } catch (error) {
      setChatHistory(prev => [...prev, { role: 'bot', message: 'Error: Unable to connect to server.' }]);
    }

    setIsLoading(false);
  };

  return (
    <div className="chatbot-container">
      <div className="chatbot-header">
         Smart Customer Support Chatbot 🤖
      </div>

      <div className="chatbox-wrapper">
        <div className="chat-history">
          {chatHistory.map((msg, index) => (
            <div
              key={index}
              className={`message-wrapper ${msg.role === 'user' ? 'right' : 'left'}`}
            >
              <div className={`message ${msg.role}`}>
                <strong>{msg.role === 'user' ? 'You' : 'Bot'}:</strong> {msg.message}
              </div>
            </div>
          ))}
          {isLoading && <div className="typing">Bot is typing...</div>}
        </div>

        <div className="input-area">
          <input
            type="text"
            placeholder="Type your message..."
            value={userInput}
            onChange={e => setUserInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSend()}
          />
          <button onClick={handleSend} disabled={isLoading}>Send</button>
        </div>
      </div>
    </div>
  );
}
