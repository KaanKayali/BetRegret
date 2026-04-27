import React, { useState } from "react";
import styles from "./Chatfield.module.scss";
import arrow from "../../assets/arrow-white.png";

export default function Chatfield() {
  const [text, setText] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);

  async function sendMessage() {
    if (!text.trim()) return;

    const userMessage = { role: "user", text };
    setMessages((prev) => [...prev, userMessage]);
    setLoading(true);

    try {
      const response = await fetch("http://localhost:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });

      if (!response.ok) {
        throw new Error("Network response was not ok");
      }

      const data = await response.json();
      setMessages((prev) => [...prev, { role: "bot", text: data.reply }]);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        { role: "bot", text: "Fehler beim Verbinden mit dem Server." },
      ]);
    } finally {
      setLoading(false);
      setText("");
    }
  }

  return (
    <div className={styles.container}>
      <div className={styles.chatfield}>
        <input
          type="text"
          value={text}
          placeholder="Ask a question"
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") sendMessage();
          }}
          disabled={loading}
        />
        <button
          className={styles.button}
          onClick={sendMessage}
          disabled={loading}
          type="button"
        >
          <img src={arrow} alt="Send" />
        </button>
      </div>

      <div className={styles.messageArea}>
        {messages.map((msg, index) => (
          <div
            key={index}
            className={
              msg.role === "bot" ? styles.botMessage : styles.userMessage
            }
          >
            {msg.text}
          </div>
        ))}
      </div>
    </div>
  );
}
